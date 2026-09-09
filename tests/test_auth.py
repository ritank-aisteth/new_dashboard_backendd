"""Focused status-code tests for dashboard authentication failures."""

import os
import unittest
from unittest.mock import Mock, patch

import jwt
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jwt.exceptions import PyJWKClientConnectionError

from auth import AuthenticationSettings, _role_record, authenticate_with_password, authentication_settings, verified_claims


SETTINGS = AuthenticationSettings(
    region="ap-south-1",
    user_pool_id="test-pool",
    app_client_id="test-client",
    user_roles_table="test-user-roles",
)


class AuthenticationFailureTests(unittest.TestCase):
    def tearDown(self) -> None:
        authentication_settings.cache_clear()

    def test_missing_token_is_unauthorized(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            verified_claims(None)
        self.assertEqual(raised.exception.status_code, 401)

    def test_missing_cognito_configuration_is_not_converted_to_503(self) -> None:
        authentication_settings.cache_clear()
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(RuntimeError):
            verified_claims(HTTPAuthorizationCredentials(scheme="Bearer", credentials="redacted"))

    def test_invalid_token_is_unauthorized(self) -> None:
        client = Mock()
        client.get_signing_key_from_jwt.side_effect = jwt.InvalidTokenError("invalid token")
        with patch("auth.authentication_settings", return_value=SETTINGS), patch("auth.jwks_client", return_value=client):
            with self.assertRaises(HTTPException) as raised:
                verified_claims(HTTPAuthorizationCredentials(scheme="Bearer", credentials="redacted"))
        self.assertEqual(raised.exception.status_code, 401)

    def test_jwks_connection_failure_is_currently_unauthorized(self) -> None:
        client = Mock()
        client.get_signing_key_from_jwt.side_effect = PyJWKClientConnectionError("JWKS unavailable")
        with patch("auth.authentication_settings", return_value=SETTINGS), patch("auth.jwks_client", return_value=client):
            with self.assertRaises(HTTPException) as raised:
                verified_claims(HTTPAuthorizationCredentials(scheme="Bearer", credentials="redacted"))
        self.assertEqual(raised.exception.status_code, 401)

    def test_password_authentication_returns_id_token_for_swagger(self) -> None:
        client = Mock()
        client.initiate_auth.return_value = {"AuthenticationResult": {"IdToken": "id-token", "ExpiresIn": 3600}}
        with patch("auth.authentication_settings", return_value=SETTINGS), patch("auth.boto3.client", return_value=client):
            token = authenticate_with_password("admin@example.invalid", "redacted-password")
        self.assertEqual(token.access_token, "id-token")
        self.assertEqual(token.token_type, "bearer")
        client.initiate_auth.assert_called_once_with(
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": "admin@example.invalid", "PASSWORD": "redacted-password"},
            ClientId="test-client",
        )

    def test_missing_aws_credentials_becomes_503(self) -> None:
        with patch("auth.boto3.resource", side_effect=NoCredentialsError()), self.assertRaises(HTTPException) as raised:
            _role_record("diagnostic-user", SETTINGS)
        self.assertEqual(raised.exception.status_code, 503)

    def test_dynamodb_client_error_becomes_503(self) -> None:
        resource = Mock()
        resource.Table.return_value.query.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Query is not permitted"}},
            "Query",
        )
        with patch("auth.boto3.resource", return_value=resource), self.assertRaises(HTTPException) as raised:
            _role_record("diagnostic-user", SETTINGS)
        self.assertEqual(raised.exception.status_code, 503)

    def test_missing_role_record_is_forbidden(self) -> None:
        resource = Mock()
        resource.Table.return_value.query.return_value = {"Items": []}
        with patch("auth.boto3.resource", return_value=resource), self.assertRaises(HTTPException) as raised:
            _role_record("diagnostic-user", SETTINGS)
        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
