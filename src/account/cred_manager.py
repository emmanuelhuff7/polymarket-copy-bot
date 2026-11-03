"""API credential management (L2 HMAC auth)."""

import boto3
import structlog
import json
from typing import Optional
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON

logger = structlog.get_logger(__name__)


class ApiCreds:
    """Container for API credentials."""

    def __init__(self, api_key: str, api_secret: str, api_passphrase: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase

    def to_dict(self) -> dict:
        """Convert to dict for storage."""
        return {
            "api_key": self.api_key,
            "api_secret": self.api_secret,
            "api_passphrase": self.api_passphrase,
        }

    @staticmethod
    def from_dict(data: dict) -> "ApiCreds":
        """Create from dict."""
        return ApiCreds(
            api_key=data.get("api_key", ""),
            api_secret=data.get("api_secret", ""),
            api_passphrase=data.get("api_passphrase", ""),
        )


class CredManager:
    """Manages API credential derivation and storage."""

    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.secrets_client = boto3.client("secretsmanager", region_name=region)

    def derive_api_creds(self, private_key: str) -> Optional[ApiCreds]:
        """Derive L2 API credentials from EOA private key.

        This creates a ClobClient with the key, which performs L1 auth
        to derive/create API credentials on the backend.

        Args:
            private_key: EOA private key (hex string, with or without 0x)

        Returns:
            ApiCreds object or None if derivation failed
        """
        try:
            # Ensure 0x prefix
            if not private_key.startswith("0x"):
                private_key = "0x" + private_key

            # Initialize ClobClient with the private key
            client = ClobClient(
                host="https://clob.polymarket.com",
                key=private_key,
                chain_id=POLYGON,
                signature_type=0,  # 0 = EOA
            )

            # This call performs L1 auth and returns API credentials
            creds_response = client.create_or_derive_api_creds()

            api_creds = ApiCreds(
                api_key=creds_response.get("api_key", ""),
                api_secret=creds_response.get("api_secret", ""),
                api_passphrase=creds_response.get("api_passphrase", ""),
            )

            logger.info("api_creds_derived")
            return api_creds

        except Exception as e:
            logger.error("derive_api_creds_failed", error=str(e))
            return None

    def store_api_creds(self, secret_name: str, creds: ApiCreds) -> bool:
        """Store API credentials in AWS Secrets Manager.

        Args:
            secret_name: secret name/ARN
            creds: ApiCreds object

        Returns:
            True if successful
        """
        try:
            secret_value = creds.to_dict()
            self.secrets_client.create_secret(
                Name=secret_name,
                SecretString=json.dumps(secret_value),
                Description="Polymarket copy bot L2 API credentials",
                Tags=[{"Key": "Application", "Value": "polymarket-copy-bot"}],
            )
            logger.info("api_creds_stored", secret_name=secret_name)
            return True
        except self.secrets_client.exceptions.ResourceExistsException:
            logger.warning("api_creds_secret_already_exists", secret_name=secret_name)
            try:
                secret_value = creds.to_dict()
                self.secrets_client.update_secret(
                    SecretId=secret_name, SecretString=json.dumps(secret_value)
                )
                logger.info("api_creds_updated", secret_name=secret_name)
                return True
            except Exception as e:
                logger.error("update_api_creds_failed", error=str(e))
                return False
        except Exception as e:
            logger.error("store_api_creds_failed", error=str(e))
            return False

    def load_api_creds(self, secret_name: str) -> Optional[ApiCreds]:
        """Load API credentials from AWS Secrets Manager.

        Args:
            secret_name: secret name/ARN

        Returns:
            ApiCreds object or None if not found
        """
        try:
            response = self.secrets_client.get_secret_value(SecretId=secret_name)
            secret = json.loads(response["SecretString"])
            creds = ApiCreds.from_dict(secret)
            logger.info("api_creds_loaded", secret_name=secret_name)
            return creds
        except self.secrets_client.exceptions.ResourceNotFoundException:
            logger.warning("api_creds_secret_not_found", secret_name=secret_name)
            return None
        except Exception as e:
            logger.error("load_api_creds_failed", error=str(e))
            raise

    def validate_creds(self, creds: ApiCreds) -> bool:
        """Validate that credentials are non-empty.

        Args:
            creds: ApiCreds object

        Returns:
            True if all fields present
        """
        is_valid = bool(creds.api_key and creds.api_secret and creds.api_passphrase)
        if not is_valid:
            logger.warning("invalid_creds", has_key=bool(creds.api_key),
                         has_secret=bool(creds.api_secret),
                         has_passphrase=bool(creds.api_passphrase))
        return is_valid
