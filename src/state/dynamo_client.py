"""Low-level DynamoDB client wrapper."""

import boto3
import structlog
from typing import Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal

logger = structlog.get_logger(__name__)


class DynamoClient:
    """Wrapper around boto3 DynamoDB client with error handling and logging."""

    def __init__(self, region: str = "us-east-1", table_prefix: str = "polymarket-bot"):
        """Initialize DynamoDB client.

        Args:
            region: AWS region
            table_prefix: prefix for all table names
        """
        self.region = region
        self.table_prefix = table_prefix
        self.dynamodb = boto3.resource("dynamodb", region_name=region)

    def _get_table(self, table_name: str) -> Any:
        """Get DynamoDB table resource with prefix applied."""
        full_name = table_name.format(prefix=self.table_prefix)
        return self.dynamodb.Table(full_name)

    def put_item(self, table_name: str, item: dict[str, Any], ttl_hours: Optional[int] = None) -> bool:
        """Put an item in DynamoDB.

        Args:
            table_name: table name (may include {prefix})
            item: item dict to store
            ttl_hours: optional TTL in hours

        Returns:
            True if successful
        """
        try:
            if ttl_hours is not None:
                item["expires_at"] = int((datetime.utcnow() + timedelta(hours=ttl_hours)).timestamp())

            table = self._get_table(table_name)
            table.put_item(Item=item)
            logger.debug("put_item", table=table_name, item_keys=list(item.keys()))
            return True
        except Exception as e:
            logger.error("put_item_failed", table=table_name, error=str(e))
            raise

    def get_item(self, table_name: str, key: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Get an item from DynamoDB.

        Args:
            table_name: table name
            key: primary key dict

        Returns:
            Item dict or None if not found
        """
        try:
            table = self._get_table(table_name)
            response = table.get_item(Key=key)
            item = response.get("Item")
            if item:
                logger.debug("get_item", table=table_name, found=True)
            return item
        except Exception as e:
            logger.error("get_item_failed", table=table_name, error=str(e))
            raise

    def query(
        self,
        table_name: str,
        key_condition_expression: str,
        expression_attribute_values: dict[str, Any],
        limit: int = 100,
        scan_index_forward: bool = True,
    ) -> list[dict[str, Any]]:
        """Query items from DynamoDB.

        Args:
            table_name: table name
            key_condition_expression: condition expression string
            expression_attribute_values: attribute values dict
            limit: max items to return
            scan_index_forward: sort order (True = ascending)

        Returns:
            List of items
        """
        try:
            table = self._get_table(table_name)
            response = table.query(
                KeyConditionExpression=key_condition_expression,
                ExpressionAttributeValues=expression_attribute_values,
                Limit=limit,
                ScanIndexForward=scan_index_forward,
            )
            items = response.get("Items", [])
            logger.debug("query", table=table_name, count=len(items))
            return items
        except Exception as e:
            logger.error("query_failed", table=table_name, error=str(e))
            raise

    def scan(
        self,
        table_name: str,
        filter_expression: Optional[str] = None,
        expression_attribute_values: Optional[dict[str, Any]] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Scan items from DynamoDB.

        Args:
            table_name: table name
            filter_expression: optional filter expression
            expression_attribute_values: optional attribute values
            limit: max items to return

        Returns:
            List of items
        """
        try:
            table = self._get_table(table_name)
            kwargs = {"Limit": limit}
            if filter_expression:
                kwargs["FilterExpression"] = filter_expression
            if expression_attribute_values:
                kwargs["ExpressionAttributeValues"] = expression_attribute_values

            response = table.scan(**kwargs)
            items = response.get("Items", [])
            logger.debug("scan", table=table_name, count=len(items))
            return items
        except Exception as e:
            logger.error("scan_failed", table=table_name, error=str(e))
            raise

    def update_item(
        self,
        table_name: str,
        key: dict[str, Any],
        update_expression: str,
        expression_attribute_values: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an item in DynamoDB.

        Args:
            table_name: table name
            key: primary key dict
            update_expression: update expression string
            expression_attribute_values: attribute values

        Returns:
            Updated item attributes
        """
        try:
            table = self._get_table(table_name)
            response = table.update_item(
                Key=key,
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues="ALL_NEW",
            )
            logger.debug("update_item", table=table_name)
            return response.get("Attributes", {})
        except Exception as e:
            logger.error("update_item_failed", table=table_name, error=str(e))
            raise

    def delete_item(self, table_name: str, key: dict[str, Any]) -> bool:
        """Delete an item from DynamoDB.

        Args:
            table_name: table name
            key: primary key dict

        Returns:
            True if successful
        """
        try:
            table = self._get_table(table_name)
            table.delete_item(Key=key)
            logger.debug("delete_item", table=table_name)
            return True
        except Exception as e:
            logger.error("delete_item_failed", table=table_name, error=str(e))
            raise

    @staticmethod
    def to_decimal(value: Any) -> Any:
        """Convert numeric values to Decimal for DynamoDB."""
        if isinstance(value, float):
            return Decimal(str(value))
        elif isinstance(value, dict):
            return {k: DynamoClient.to_decimal(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [DynamoClient.to_decimal(v) for v in value]
        return value

    @staticmethod
    def from_decimal(value: Any) -> Any:
        """Convert Decimal values back to float for Python."""
        if isinstance(value, Decimal):
            return float(value)
        elif isinstance(value, dict):
            return {k: DynamoClient.from_decimal(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [DynamoClient.from_decimal(v) for v in value]
        return value
