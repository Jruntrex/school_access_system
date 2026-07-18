"""RFID UID normalization/hashing and ESP32 request-signature verification.

Ported from Mentorly's `_verify_device_hmac` (main/views.py) and the
`rfid_uid` handling in its RFID endpoints, adapted to never touch a raw
UID once it reaches storage — see spec section 3.3.
"""

import hashlib
import hmac
import time

from django.conf import settings

SIGNATURE_WINDOW_SECONDS = 30


def normalize_uid(raw_uid: str) -> str:
    return raw_uid.strip().upper()


def compute_card_uid_hash(normalized_uid: str) -> str:
    """HMAC_SHA256(CARD_UID_HASH_SECRET, normalized_uid) — the only form of
    the UID that is ever written to the database."""
    secret = settings.CARD_UID_HASH_SECRET
    return hmac.new(
        secret.encode(), normalized_uid.encode(), hashlib.sha256
    ).hexdigest()


def verify_device_signature(uid: str, timestamp_str: str, signature: str) -> bool:
    """Verifies the HMAC-SHA256 signature an ESP32 reader attaches to a scan
    request. Signed message is "UID:timestamp"; a +/-30s window guards
    against replay attacks. Mirrors the firmware in firmware/rfid-moodle.ino.
    """
    secret = settings.CARD_SCAN_API_KEY
    if not secret:
        return False
    if not timestamp_str or not signature:
        return False

    try:
        ts = int(timestamp_str)
    except ValueError:
        return False

    if abs(time.time() - ts) > SIGNATURE_WINDOW_SECONDS:
        return False

    message = f"{uid}:{timestamp_str}".encode()
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.lower())
