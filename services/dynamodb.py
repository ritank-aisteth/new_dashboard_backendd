"""DynamoDB write gateway for legacy dashboard records."""

from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from settings import DashboardSettings

from .elasticsearch import ExternalServiceError


def _dynamo_value(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _dynamo_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_dynamo_value(item) for item in value]
    return value


class DynamoDBGateway:
    """Writes to the source-of-truth tables used by the legacy backend."""

    def __init__(self, settings: DashboardSettings) -> None:
        environment = settings.environment
        self.tenant_table = f"{environment.THIS_ENV}_tenant"
        self.provider_table = f"{environment.THIS_ENV}_provider_registration"
        self.subscription_table = f"{environment.THIS_ENV}_subscription_transaction"
        self._resource = boto3.resource(
            "dynamodb",
            region_name=environment.DYNAMODB_REGION,
            aws_access_key_id=environment.ACCESS_KEY.get_secret_value(),
            aws_secret_access_key=environment.SECRET_KEY.get_secret_value(),
        )

    def put_item(self, table_name: str, item: dict[str, Any]) -> None:
        try:
            self._resource.Table(table_name).put_item(Item=_dynamo_value(item))
        except (BotoCoreError, ClientError, ValueError, TypeError) as error:
            raise ExternalServiceError("DynamoDB write failed") from error

    def put_provider_with_subscription(self, provider: dict[str, Any], subscription: dict[str, Any]) -> None:
        try:
            self._resource.meta.client.transact_write_items(
                TransactItems=[
                    {"Put": {"TableName": self.provider_table, "Item": self._serialize(provider)}},
                    {"Put": {"TableName": self.subscription_table, "Item": self._serialize(subscription)}},
                ]
            )
        except (BotoCoreError, ClientError, ValueError, TypeError) as error:
            raise ExternalServiceError("DynamoDB transaction failed") from error

    @staticmethod
    def _serialize(item: dict[str, Any]) -> dict[str, Any]:
        from boto3.dynamodb.types import TypeSerializer

        serializer = TypeSerializer()
        return {key: serializer.serialize(_dynamo_value(value)) for key, value in item.items()}
