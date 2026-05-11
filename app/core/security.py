"""Webhook security and signature verification."""
import hashlib
import hmac
from typing import Optional

from structlog.stdlib import BoundLogger

from app.core.config import get_settings


def verify_signature(
    payload: bytes, signature: str, secret: str, header_name: str
) -> bool:
    """
    Verify HMAC-SHA256 webhook signature.

    TradingView typically sends the signature as: timestamp:v signature
    where v = HMAC-SHA256(secret, timestamp + '.' + body)

    Args:
        payload: Raw request body bytes
        signature: Signature value from header
        secret: Shared secret for HMAC
        header_name: Header name for logging context

    Returns:
        True if signature is valid
    """
    if not signature or not secret:
        return False

    try:
        # TradingView sends: timestamp=XXXXX,v_signature=YYYYY
        # Parse the signature part
        if "=" in signature:
            parts = dict(p.split("=") for p in signature.split(","))
            timestamp = parts.get("timestamp", "")
            received_sig = parts.get("v_signature", "")
        else:
            # Older format: just the raw signature
            timestamp = ""
            received_sig = signature

        # Build the signed message: timestamp.body
        message = f"{timestamp}.{payload.decode('utf-8')}" if timestamp else payload

        # Compute expected signature
        expected = hmac.new(
            secret.encode("utf-8"),
            message.encode("utf-8") if isinstance(message, str) else message,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(received_sig.strip(), expected.strip())
    except Exception:
        return False


def verify_tradingview_signature(
    payload: bytes,
    signature_header: str,
    secret: str,
    logger: Optional[BoundLogger] = None,
) -> bool:
    """
    Verify a TradingView-specific webhook signature.

    Args:
        payload: Raw request body
        signature_header: Raw signature header value
        secret: Shared webhook secret
        logger: Optional logger for audit trail

    Returns:
        True if signature is valid
    """
    settings = get_settings()
    is_valid = verify_signature(payload, signature_header, secret, settings.webhook_signature_header)

    if logger:
        logger.debug(
            "signature_verification",
            signature_header=signature_header[:20] + "..." if signature_header else None,
            valid=is_valid,
        )

    return is_valid
