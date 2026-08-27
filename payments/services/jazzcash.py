"""JazzCash payment portal helpers (HTTP POST checkout + §14.2 SHA256-HMAC)."""

from __future__ import annotations

import hmac
import hashlib
import re
from decimal import Decimal
from typing import Any, Mapping


def _include_in_hash(field_name: str) -> bool:
    name = field_name.lower()
    if name == 'pp_securehash':
        return False
    return name.startswith('pp_')


def build_secure_hash_hmac_hex(fields: Mapping[str, Any], integrity_salt: str) -> str:
    """
    §14.2 (PG Integration Guide): order PP* keys ascending; concatenate VALUES using '&';
    prepend `<SharedSecret>&` …; HMAC-SHA256 keyed by Shared Secret (Integrity Salt).

    Omit empty values (common implementations; aligns with sandbox samples excluding unused fields).
    """
    salt = (integrity_salt or '').strip()
    if not salt:
        raise ValueError('JazzCash Integrity Salt is required.')

    sorted_keys = sorted(
        [str(k) for k in fields.keys() if _include_in_hash(str(k))],
        key=lambda k: k,
    )

    values: list[str] = []
    for k in sorted_keys:
        raw = fields.get(k)
        if raw is None:
            continue
        s = str(raw).strip()
        if not s:
            continue
        values.append(s)

    middle = '&'.join(values)
    to_sign = f'{salt}&{middle}' if middle else salt

    key_bytes = salt.encode('utf-8')
    msg_bytes = to_sign.encode('utf-8')
    return hmac.new(key_bytes, msg_bytes, hashlib.sha256).hexdigest().upper()


def verify_secure_hash_hmac(fields: Mapping[str, Any], integrity_salt: str, incoming_hash: str | None) -> bool:
    if not incoming_hash:
        return False
    try:
        expected = build_secure_hash_hmac_hex(fields, integrity_salt).lower()
        return hmac.compare_digest(expected, incoming_hash.strip().lower())
    except ValueError:
        return False


def redact_sensitive_payload(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    for key in list(out.keys()):
        if str(key).lower() == 'pp_password':
            out[key] = '***REDACTED***'
    return out


def jazzcash_minor_amount(amount_pkr: Decimal) -> int:
    quantized = Decimal(amount_pkr).quantize(Decimal('0.01'))
    if quantized <= 0:
        raise ValueError('Amount must be positive.')
    return int(quantized * 100)


def sanitize_txn_ref(ref: str) -> str:
    ref = ''.join(ref.split()).replace('/', '').replace('.', '')
    ref = ref[:24]
    if len(ref) < 6:
        raise ValueError('TxnRefNo too short.')
    return ref


_MOBILE_CLEAN = re.compile(r'\D+')


def clean_mobile_digits(mobile: str | None, max_len: int = 11) -> str:
    if not mobile:
        return ''
    return _MOBILE_CLEAN.sub('', str(mobile))[-max_len:]
