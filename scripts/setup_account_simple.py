#!/usr/bin/env python3
"""Simplified account setup script - no external dependencies except requests."""

import json
import sys
import os
from datetime import datetime

# Try to use aws SDK, but don't fail if not available
try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

try:
    from eth_account import Account
    HAS_ETH = True
except ImportError:
    HAS_ETH = False


def generate_eoa_key():
    """Generate a new Ethereum private key."""
    if not HAS_ETH:
        print("ERROR: eth-account not installed. Run: pip install eth-account")
        return None

    try:
        account = Account.create()
        private_key = account.key.hex()
        if private_key.startswith("0x"):
            private_key = private_key[2:]
        return private_key, account.address
    except Exception as e:
        print(f"ERROR: Failed to generate key: {e}")
        return None


def store_in_secrets_manager(secret_name, secret_value, secret_type="eoa-key"):
    """Store secret in AWS Secrets Manager."""
    if not HAS_BOTO3:
        print("WARNING: boto3 not installed. Storing to local file instead.")
        return store_locally(secret_name, secret_value, secret_type)

    try:
        client = boto3.client("secretsmanager")

        data = {"private_key" if secret_type == "eoa-key" else "api_creds": secret_value}

        try:
            client.create_secret(
                Name=secret_name,
                SecretString=json.dumps(data),
                Description=f"Polymarket copy bot {secret_type}",
            )
            print(f"✓ Stored {secret_type} in AWS Secrets Manager: {secret_name}")
            return True
        except client.exceptions.ResourceExistsException:
            client.update_secret(
                SecretId=secret_name,
                SecretString=json.dumps(data),
            )
            print(f"✓ Updated {secret_type} in AWS Secrets Manager: {secret_name}")
            return True
    except Exception as e:
        print(f"ERROR: Failed to store in Secrets Manager: {e}")
        print("Falling back to local storage...")
        return store_locally(secret_name, secret_value, secret_type)


def store_locally(secret_name, secret_value, secret_type="eoa-key"):
    """Store secret to local .env file."""
    try:
        env_file = ".env.local"

        # Create backup
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                existing = f.read()
            with open(f"{env_file}.backup", 'w') as f:
                f.write(existing)

        # Append new secret
        with open(env_file, 'a') as f:
            if secret_type == "eoa-key":
                f.write(f"\n# Generated at {datetime.now().isoformat()}\n")
                f.write(f"EOA_PRIVATE_KEY={secret_value}\n")

        print(f"✓ Stored {secret_type} locally in {env_file}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to store locally: {e}")
        return False


def main():
    """Main setup flow."""
    print("\n" + "="*80)
    print("POLYMARKET COPY TRADING BOT - ACCOUNT SETUP")
    print("="*80 + "\n")

    # Step 1: Generate key
    print("Step 1: Generating EOA private key...")
    result = generate_eoa_key()
    if not result:
        print("\n❌ FAILED: Could not generate private key")
        print("Make sure eth-account is installed: pip install eth-account")
        return False

    private_key, wallet_address = result
    print(f"✓ Generated private key")
    print(f"✓ Wallet address: {wallet_address}\n")

    # Step 2: Store key
    print("Step 2: Storing private key...")
    secret_name = "polymarket-bot/eoa-key"
    if not store_in_secrets_manager(secret_name, private_key, "eoa-key"):
        print("❌ FAILED: Could not store private key")
        return False

    # Step 3: Print instructions
    print("\n" + "="*80)
    print("ACCOUNT SETUP COMPLETE")
    print("="*80)
    print(f"\nWallet Address (to fund): {wallet_address}")
    print(f"\nPrivate Key Storage:")
    print(f"  - AWS Secrets Manager: polymarket-bot/eoa-key")
    print(f"  - OR local file: .env.local")

    print("\n" + "="*80)
    print("NEXT STEPS:")
    print("="*80)
    print(f"\n1. Fund your wallet on Polygon network:")
    print(f"   Address: {wallet_address}")
    print(f"   Send: $1,500 USDC + $5-10 MATIC")
    print(f"\n   Options:")
    print(f"   - Polygon Bridge: https://bridge.polygon.technology")
    print(f"   - Coinbase (direct Polygon)")
    print(f"   - QuickSwap/Uniswap (swap USDC on Polygon)")

    print(f"\n2. Verify wallet is funded:")
    print(f"   - Check on Polygonscan: https://polygonscan.com/address/{wallet_address}")

    print(f"\n3. Seed top traders:")
    print(f"   python scripts/seed_traders.py --wallets 0xabc123,0xdef456,...")

    print(f"\n4. Run the bot locally:")
    print(f"   python -m src.entrypoints.monitor")

    print(f"\n5. Deploy to AWS (production):")
    print(f"   cd infra && cdk deploy --all")

    print("\n" + "="*80)

    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
