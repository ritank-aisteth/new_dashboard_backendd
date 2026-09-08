"""Verified Cognito authentication and DynamoDB-backed dashboard authorization."""

import logging
import os
from functools import lru_cache
from ipaddress import ip_address
from typing import Annotated

import boto3
import jwt
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from pydantic import BaseModel, ConfigDict, Field


logger = logging.getLogger(__name__)


def _exception_type(error: BaseException) -> str:
    return f"{type(error).__module__}.{type(error).__name__}"



class AuthenticationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    region: str = Field(min_length=1)
    user_pool_id: str = Field(min_length=1)
    app_client_id: str = Field(min_length=1)
    user_roles_table: str = Field(min_length=1)

    @property
    def issuer(self) -> str:
        return f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}"


class AuthenticatedDashboardUser(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: str
    login: str
    name: str
    role: str
    tenant_id: str
    tenant_name: str | None = None


bearer_scheme = HTTPBearer(auto_error=False, scheme_name="CognitoAccessToken")


def _required_environment(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or "CHANGE_ME" in value:
        raise RuntimeError(f"{name} is not configured")
    return value


@lru_cache(maxsize=1)
def authentication_settings() -> AuthenticationSettings:
    return AuthenticationSettings(
        region=_required_environment("COGNITO_REGION"),
        user_pool_id=_required_environment("COGNITO_USER_POOL_ID"),
        app_client_id=_required_environment("COGNITO_APP_CLIENT_ID"),
        user_roles_table=_required_environment("DASHBOARD_USER_ROLES_TABLE"),
    )


@lru_cache(maxsize=1)
def jwks_client() -> PyJWKClient:
    settings = authentication_settings()
    return PyJWKClient(f"{settings.issuer}/.well-known/jwks.json", cache_keys=True, lifespan=3600, timeout=10)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication is required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def verified_claims(credentials: HTTPAuthorizationCredentials | None) -> dict[str, object]:
    if credentials is None or credentials.scheme.casefold() != "bearer" or not credentials.credentials:
        raise _unauthorized()
    try:
        settings = authentication_settings()
    except RuntimeError as error:
        logger.exception(
            "Cognito authentication configuration failed: exception_type=%s message=%s",
            _exception_type(error),
            str(error),
        )
        raise
    token = credentials.credentials
    try:
        key = jwks_client().get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=settings.issuer,
            audience=settings.app_client_id,
            options={"require": ["exp", "iat", "iss", "sub", "token_use", "aud"]},
        )
    except jwt.PyJWTError as error:
        logger.warning(
            "Cognito token validation failed: exception_type=%s message=%s",
            _exception_type(error),
            str(error),
        )
        raise _unauthorized() from error
    if claims.get("token_use") != "id":
        raise _unauthorized()
    return {str(key): value for key, value in claims.items()}


def _claim_string(claims: dict[str, object], key: str) -> str:
    value = claims.get(key)
    return value.strip() if isinstance(value, str) else ""


def _is_loopback_request(request: Request) -> bool:
    if request.client is None:
        return False
    try:
        return ip_address(request.client.host).is_loopback
    except ValueError:
        return False


def _role_record(login: str, settings: AuthenticationSettings) -> dict[str, object]:
    try:
        table = boto3.resource("dynamodb", region_name=settings.region).Table(settings.user_roles_table)
        response = table.query(
            KeyConditionExpression=Key("user_id").eq(login),
            FilterExpression=Attr("record_status").eq("active"),
            Limit=2,
            ConsistentRead=True,
        )
    except (BotoCoreError, ClientError) as error:
        if isinstance(error, ClientError):
            error_details = error.response.get("Error", {})
            logger.exception(
                "DynamoDB role lookup failed: exception_type=%s error_code=%s message=%s table=%s region=%s",
                _exception_type(error),
                error_details.get("Code", "unknown"),
                error_details.get("Message", "unknown"),
                settings.user_roles_table,
                settings.region,
            )
        else:
            logger.exception(
                "DynamoDB role lookup failed: exception_type=%s message=%s table=%s region=%s",
                _exception_type(error),
                str(error),
                settings.user_roles_table,
                settings.region,
            )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authorization service is temporarily unavailable") from error
    records = response.get("Items", [])
    if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], dict):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dashboard access is denied")
    return {str(key): value for key, value in records[0].items()}


def require_dashboard_access(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
) -> AuthenticatedDashboardUser:
    claims = verified_claims(credentials)
    login = _claim_string(claims, "email") or _claim_string(claims, "phone_number") or _claim_string(claims, "cognito:username")
    if not login:
        raise _unauthorized()
    local_cognito = os.getenv("DASHBOARD_AUTHORIZATION_MODE", "dynamodb").casefold() == "cognito-local"
    if local_cognito and _is_loopback_request(request):
        return AuthenticatedDashboardUser(
            subject=_claim_string(claims, "sub"),
            login=login,
            name=_claim_string(claims, "name") or login,
            role="superadmin",
            tenant_id="all",
        )
    settings = authentication_settings()
    role_record = _role_record(login, settings)
    role = str(role_record.get("role", "")).casefold()
    tenant_id = str(role_record.get("tenant_id", ""))
    allowed_roles = {"superadmin", "admin", "tenantadmin", "tenant_admin"}
    superadmin_scope_is_valid = role == "superadmin" and tenant_id == "all"
    tenant_scope_is_valid = role in {"admin", "tenantadmin", "tenant_admin"} and bool(tenant_id) and tenant_id != "all"
    if role not in allowed_roles or not (superadmin_scope_is_valid or tenant_scope_is_valid):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dashboard access is denied")
    return AuthenticatedDashboardUser(
        subject=_claim_string(claims, "sub"),
        login=login,
        name=_claim_string(claims, "name") or login,
        role=role,
        tenant_id=tenant_id,
        tenant_name=str(role_record.get("tenant_name")) if role_record.get("tenant_name") else None,
    )
