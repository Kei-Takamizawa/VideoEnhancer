"""Local CA and renewable 397-day HTTPS identity, without changing trust roots."""

from __future__ import annotations

import ipaddress
import plistlib
import socket
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from videoenhancer.remote.security import private_ipv4, private_write


@dataclass(frozen=True)
class CertificateInfo:
    names: tuple[str, ...]
    addresses: tuple[str, ...]
    expires: str


def local_addresses() -> list[str]:
    import psutil

    found = {
        address.address
        for entries in psutil.net_if_addrs().values()
        for address in entries
        if address.family == socket.AF_INET and private_ipv4(address.address)
    }
    return sorted(found)


def ensure_certificates(
    home: Path,
    pc_name: str,
    addresses: list[str],
    *,
    now: datetime | None = None,
) -> CertificateInfo:
    home.mkdir(parents=True, exist_ok=True)
    now = now or datetime.now(UTC)
    names = (f"{pc_name}.local", pc_name)
    addresses = sorted(set(addresses))
    ca_path, ca_key_path = home / "ca.crt", home / "ca.key"
    if ca_path.exists() or ca_key_path.exists():
        # Never silently replace a partial or damaged trust root.
        ca = x509.load_pem_x509_certificate(ca_path.read_bytes())
        ca_key = serialization.load_pem_private_key(ca_key_path.read_bytes(), password=None)
        if not isinstance(ca_key, rsa.RSAPrivateKey):
            raise ValueError("The existing VideoEnhancer CA key must be an RSA private key.")
    else:
        ca_key = rsa.generate_private_key(65537, 2048)
        subject = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, f"VideoEnhancer Local CA ({pc_name})")]
        )
        ca = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(
                x509.KeyUsage(False, False, False, False, False, True, True, False, False),
                critical=True,
            )
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), False)
            .sign(ca_key, hashes.SHA256())
        )
        # iPadOS name-constraint compatibility was not verified by the spike.
        private_write(
            ca_key_path,
            ca_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
        )
        private_write(ca_path, ca.public_bytes(serialization.Encoding.PEM))
    leaf_path, key_path = home / "server.crt", home / "server.key"
    desired = {
        *(x509.DNSName(name) for name in names),
        *(x509.IPAddress(ipaddress.ip_address(address)) for address in addresses),
    }
    leaf = None
    if leaf_path.exists() and key_path.exists():
        try:
            leaf = x509.load_pem_x509_certificate(leaf_path.read_bytes())
            existing = set(
                leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
            )
            if existing != desired or leaf.not_valid_after_utc <= now + timedelta(days=30):
                leaf = None
        except (ValueError, x509.ExtensionNotFound):
            leaf = None
    if leaf is None:
        key = rsa.generate_private_key(65537, 2048)
        leaf = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, names[0])]))
            .issuer_name(ca.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=397))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
            .add_extension(x509.SubjectAlternativeName(sorted(desired, key=str)), False)
            .add_extension(
                x509.KeyUsage(True, False, True, False, False, False, False, False, False), True
            )
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False)
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), False
            )
            .sign(ca_key, hashes.SHA256())
        )
        private_write(
            key_path,
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
        )
        private_write(leaf_path, leaf.public_bytes(serialization.Encoding.PEM))
    der = ca.public_bytes(serialization.Encoding.DER)
    (home / "ca.cer").write_bytes(der)
    identifier = "local.videoenhancer.ca"
    profile = {
        "PayloadType": "Configuration",
        "PayloadVersion": 1,
        "PayloadIdentifier": identifier,
        "PayloadUUID": str(uuid.uuid5(uuid.NAMESPACE_DNS, pc_name)),
        "PayloadDisplayName": f"VideoEnhancer Local CA ({pc_name})",
        "PayloadContent": [
            {
                "PayloadType": "com.apple.security.root",
                "PayloadVersion": 1,
                "PayloadIdentifier": identifier + ".root",
                "PayloadUUID": str(uuid.uuid5(uuid.NAMESPACE_DNS, pc_name + ".root")),
                "PayloadDisplayName": f"VideoEnhancer Local CA ({pc_name})",
                "PayloadContent": der,
            }
        ],
    }
    (home / "ca.mobileconfig").write_bytes(plistlib.dumps(profile))
    return CertificateInfo(names, tuple(addresses), leaf.not_valid_after_utc.isoformat())
