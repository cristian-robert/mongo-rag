"""Unit tests for the HMAC signature scheme used by outbound webhooks."""

from datetime import datetime, timezone

import pytest

from src.services.webhook_delivery import (
    SIGNATURE_TOLERANCE_SECONDS,
    compute_signature,
    verify_signature,
)


@pytest.mark.unit
def test_signature_roundtrip_succeeds():
    secret = "whsec_testsecret"
    body = b'{"event":"document.ingested","data":{"id":"d1"}}'
    ts = str(int(datetime.now(timezone.utc).timestamp()))
    sig = compute_signature(secret=secret, timestamp=ts, body=body)

    assert verify_signature(secret=secret, header=sig, body=body)


@pytest.mark.unit
def test_signature_rejects_wrong_secret():
    body = b"{}"
    ts = str(int(datetime.now(timezone.utc).timestamp()))
    sig = compute_signature(secret="whsec_a", timestamp=ts, body=body)

    assert not verify_signature(secret="whsec_b", header=sig, body=body)


@pytest.mark.unit
def test_signature_rejects_tampered_body():
    secret = "whsec_x"
    ts = str(int(datetime.now(timezone.utc).timestamp()))
    sig = compute_signature(secret=secret, timestamp=ts, body=b"original")

    assert not verify_signature(secret=secret, header=sig, body=b"tampered")


@pytest.mark.unit
def test_signature_rejects_old_timestamp_replay():
    secret = "whsec_x"
    body = b"{}"
    # Forge a timestamp older than tolerance.
    old_ts = str(int(datetime.now(timezone.utc).timestamp()) - SIGNATURE_TOLERANCE_SECONDS - 60)
    sig = compute_signature(secret=secret, timestamp=old_ts, body=body)

    assert not verify_signature(secret=secret, header=sig, body=body)


@pytest.mark.unit
def test_signature_rejects_malformed_header():
    assert not verify_signature(secret="x", header="garbage", body=b"{}")
    assert not verify_signature(secret="x", header="t=abc,v1=def", body=b"{}")
