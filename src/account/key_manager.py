"""EOA private key generation and secrets management."""

import boto3
import structlog
import json
from eth_account import Account
from typing import Optional

logger = structlog.get_logger(__name__)


class KeyManager:
    """Manages EOA key generation and storage in AWS Secrets Manager."""

    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.secrets_client = boto3.client("secretsmanager", region_name=region)

    def generate_eoa_key(self) -> str:
        """Generate a new EOA (Externally Owned Account) private key.

        Returns:
            Private key (hex string, without 0x prefix)
        """
        try:
            account = Account.create()
            private_key = account.key.hex()
            # Remove 0x prefix if present
            if private_key.startswith("0x"):
                private_key = private_key[2:]
            logger.info("eoa_key_generated")
            return private_key
        except Exception as e:
            logger.error("generate_eoa_key_failed", error=str(e))
            raise

    def store_eoa_key(self, secret_name: str, private_key: str) -> bool:
        """Store EOA private key in AWS Secrets Manager.

        Args:
            secret_name: secret name/ARN
            private_key: private key hex string

        Returns:
            True if successful
        """
        try:
            secret_value = {"eoa_private_key": private_key}
            self.secrets_client.create_secret(
                Name=secret_name,
                SecretString=json.dumps(secret_value),
                Description="Polymarket copy bot EOA private key",
                Tags=[{"Key": "Application", "Value": "polymarket-copy-bot"}],
            )
            logger.info("eoa_key_stored", secret_name=secret_name)
            return True
        except self.secrets_client.exceptions.ResourceExistsException:
            logger.warning("secret_already_exists", secret_name=secret_name)
            # Update instead
            try:
                secret_value = {"eoa_private_key": private_key}
                self.secrets_client.update_secret(
                    SecretId=secret_name, SecretString=json.dumps(secret_value)
                )
                logger.info("eoa_key_updated", secret_name=secret_name)
                return True
            except Exception as e:
                logger.error("update_secret_failed", error=str(e))
                return False
        except Exception as e:
            logger.error("store_eoa_key_failed", error=str(e))
            return False

    def load_eoa_key(self, secret_name: str) -> Optional[str]:
        """Load EOA private key from AWS Secrets Manager.

        Args:
            secret_name: secret name/ARN

        Returns:
            Private key hex string or None if not found
        """
        try:
            response = self.secrets_client.get_secret_value(SecretId=secret_name)
            secret = json.loads(response["SecretString"])
            private_key = secret.get("eoa_private_key")
            logger.info("eoa_key_loaded", secret_name=secret_name)
            return private_key
        except self.secrets_client.exceptions.ResourceNotFoundException:
            logger.warning("secret_not_found", secret_name=secret_name)
            return None
        except Exception as e:
            logger.error("load_eoa_key_failed", error=str(e))
            raise

    def derive_address_from_key(self, private_key: str) -> str:
        """Derive Ethereum address from private key.

        Args:
            private_key: private key hex (with or without 0x prefix)

        Returns:
            Ethereum address (checksummed, with 0x prefix)
        """
        try:
            if not private_key.startswith("0x"):
                private_key = "0x" + private_key
            account = Account.from_key(private_key)
            logger.debug("address_derived", address=account.address)
            return account.address
        except Exception as e:
            logger.error("derive_address_failed", error=str(e))
            raise

    def validate_key_format(self, private_key: str) -> bool:
        """Validate private key format and length.

        Args:
            private_key: private key hex string

        Returns:
            True if valid
        """
        try:
            # Remove 0x prefix for length check
            key_clean = private_key.replace("0x", "")
            # Should be 64 hex characters = 32 bytes
            if len(key_clean) != 64:
                logger.warning("invalid_key_length", length=len(key_clean))
                return False
            # Should be valid hex
            int(key_clean, 16)
            logger.debug("key_format_valid")
            return True
        except ValueError:
            logger.warning("invalid_key_hex")
            return False
