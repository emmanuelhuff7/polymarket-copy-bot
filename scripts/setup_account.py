#!/usr/bin/env python3
"""One-time account setup script for initializing EOA key and API credentials."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import structlog
from src.config import get_settings
from src.account import KeyManager, CredManager

logger = structlog.get_logger(__name__)


def main():
    """Set up account: generate key, derive API creds, store both in Secrets Manager."""
    settings = get_settings()

    logger.info("account_setup_starting")

    # Step 1: Generate EOA key
    logger.info("generating_eoa_key")
    key_manager = KeyManager(region=settings.aws_region)

    try:
        private_key = key_manager.generate_eoa_key()
        logger.info("eoa_key_generated")
    except Exception as e:
        logger.error("failed_to_generate_key", error=str(e))
        return False

    # Step 2: Derive wallet address from key
    try:
        wallet_address = key_manager.derive_address_from_key(private_key)
        logger.info("wallet_address_derived", address=wallet_address)
    except Exception as e:
        logger.error("failed_to_derive_address", error=str(e))
        return False

    # Step 3: Store EOA key in Secrets Manager
    logger.info("storing_eoa_key_to_secrets_manager", secret=settings.secrets_manager_key_arn)
    if not key_manager.store_eoa_key(settings.secrets_manager_key_arn, private_key):
        logger.error("failed_to_store_eoa_key")
        return False

    # Step 4: Derive API credentials
    logger.info("deriving_api_credentials")
    cred_manager = CredManager(region=settings.aws_region)

    try:
        api_creds = cred_manager.derive_api_creds(private_key)
        if not api_creds or not cred_manager.validate_creds(api_creds):
            logger.error("failed_to_derive_valid_credentials")
            return False
        logger.info("api_credentials_derived")
    except Exception as e:
        logger.error("failed_to_derive_credentials", error=str(e))
        return False

    # Step 5: Store API credentials
    logger.info("storing_api_credentials", secret=settings.secrets_manager_creds_arn)
    if not cred_manager.store_api_creds(settings.secrets_manager_creds_arn, api_creds):
        logger.error("failed_to_store_api_credentials")
        return False

    # Step 6: Print summary
    print("\n" + "=" * 80)
    print("ACCOUNT SETUP COMPLETE")
    print("=" * 80)
    print(f"\nWallet Address (PROXY): {wallet_address}")
    print(f"\nEOA Private Key: Stored in AWS Secrets Manager")
    print(f"  Secret ARN: {settings.secrets_manager_key_arn}")
    print(f"\nAPI Credentials: Stored in AWS Secrets Manager")
    print(f"  Secret ARN: {settings.secrets_manager_creds_arn}")
    print("\nNEXT STEPS:")
    print(f"1. Fund the wallet address with USDC and MATIC on Polygon network:")
    print(f"   Address: {wallet_address}")
    print(f"   - Send $1,500 USDC (for trading)")
    print(f"   - Send ~$5-10 MATIC (for gas)")
    print(f"\n2. Verify funding by running:")
    print(f"   python scripts/smoke_test.py")
    print("\n3. Deploy infrastructure:")
    print(f"   cd infra && cdk deploy --all")
    print("\n4. Seed initial traders:")
    print(f"   python scripts/seed_traders.py --wallets 0xaddr1,0xaddr2,...")
    print("\n" + "=" * 80)

    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error("setup_script_error", error=str(e))
        sys.exit(1)
