#!/usr/bin/env python3
"""Generate a secure webhook secret."""
import secrets
import sys

def generate_secret(length: int = 32) -> str:
    """Generate a URL-safe base64-encoded secret."""
    return secrets.token_urlsafe(length)

if __name__ == "__main__":
    length = int(sys.argv[1]) if len(sys.argv) > 1 else 32
    secret = generate_secret(length)
    print(f"WEBHOOK_SECRET={secret}")
