"""HTTPS gateway certificate lifecycle and network boundary regression tests."""

import ipaddress
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from videoenhancer.remote.certificates import ensure_certificates
from videoenhancer.remote.security import private_ipv4


def test_private_source_allowlist_is_explicit():
    for address in ("10.0.0.1", "172.16.0.1", "192.168.1.1", "169.254.2.3", "127.0.0.1"):
        assert private_ipv4(address)
    for address in ("8.8.8.8", "100.64.0.1", "192.0.2.1", "::1", "0.0.0.0"):
        assert not private_ipv4(address)


def test_certificate_identity_validity_and_reissue(tmp_path):
    now = datetime.now(UTC)
    first = ensure_certificates(tmp_path, "TEST-PC", ["192.168.1.2"], now=now)
    ca_bytes = (tmp_path / "ca.crt").read_bytes()
    leaf_bytes = (tmp_path / "server.crt").read_bytes()
    ca = x509.load_pem_x509_certificate(ca_bytes)
    leaf = x509.load_pem_x509_certificate(leaf_bytes)
    assert "VideoEnhancer Local CA (TEST-PC)" in ca.subject.rfc4514_string()
    assert ca.not_valid_after_utc - now > timedelta(days=3649)
    assert timedelta(days=396) < leaf.not_valid_after_utc - now <= timedelta(days=397)
    san = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert set(san.get_values_for_type(x509.DNSName)) == {"TEST-PC", "TEST-PC.local"}
    assert san.get_values_for_type(x509.IPAddress) == [ipaddress.ip_address("192.168.1.2")]
    assert first.expires == leaf.not_valid_after_utc.isoformat()
    ensure_certificates(tmp_path, "TEST-PC", ["192.168.1.2"], now=now)
    assert (tmp_path / "server.crt").read_bytes() == leaf_bytes
    ensure_certificates(tmp_path, "TEST-PC", ["192.168.1.3"], now=now)
    assert (tmp_path / "server.crt").read_bytes() != leaf_bytes
    assert (tmp_path / "ca.crt").read_bytes() == ca_bytes
    second = (tmp_path / "server.crt").read_bytes()
    ensure_certificates(tmp_path, "TEST-PC", ["192.168.1.3"], now=now + timedelta(days=368))
    assert (tmp_path / "server.crt").read_bytes() != second
    assert (tmp_path / "ca.crt").read_bytes() == ca_bytes
    assert (tmp_path / "ca.cer").read_bytes() == ca.public_bytes(serialization.Encoding.DER)
    assert (tmp_path / "ca.mobileconfig").read_bytes().startswith(b"<?xml")


def test_invalid_existing_ca_key_is_not_replaced(tmp_path):
    ensure_certificates(tmp_path, "TEST-PC", ["192.168.1.2"])
    original_ca = (tmp_path / "ca.crt").read_bytes()
    key = ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    (tmp_path / "ca.key").write_bytes(key)
    with pytest.raises(ValueError, match="must be an RSA private key"):
        ensure_certificates(tmp_path, "TEST-PC", ["192.168.1.2"])
    assert (tmp_path / "ca.key").read_bytes() == key
    assert (tmp_path / "ca.crt").read_bytes() == original_ca
