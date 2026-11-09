"""HTTPS for everything that leaves this computer: a self-signed certificate made once and kept in data/tls.

No certificate authority can vouch for a device on a home network, so the app remembers the certificate's
fingerprint when it is paired (the QR code carries it) and refuses any other. Browsers warn once.
"""
import hashlib
import os
import ssl
import subprocess
import tempfile

CONF = """[req]
distinguished_name = dn
x509_extensions = ext
prompt = no
[dn]
CN = TabDock
O = TabDock
[ext]
subjectAltName = DNS:localhost,IP:127.0.0.1
basicConstraints = critical,CA:false
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
"""


def make_certificate(cert, key):
    """Needs the openssl command (always there on macOS; install-linux.sh makes sure of it on Linux)."""
    os.makedirs(os.path.dirname(cert), exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".cnf", delete=False) as f:
        f.write(CONF)
    try:
        subprocess.run(["openssl", "req", "-x509", "-new", "-newkey", "rsa:2048", "-nodes", "-sha256", "-days", "3650",
                        "-keyout", key, "-out", cert, "-config", f.name],
                       check=True, capture_output=True, timeout=60)
    finally:
        os.remove(f.name)
    os.chmod(key, 0o600)


def fingerprint(cert):
    with open(cert) as f:
        return hashlib.sha256(ssl.PEM_cert_to_DER_cert(f.read())).hexdigest()


def setup(data_dir):
    """(SSL context, sha-256 fingerprint), or (None, "") when no certificate can be made."""
    cert, key = os.path.join(data_dir, "tls", "cert.pem"), os.path.join(data_dir, "tls", "key.pem")
    try:
        if not (os.path.exists(cert) and os.path.exists(key)):
            make_certificate(cert, key)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(cert, key)
        return ctx, fingerprint(cert)
    except (OSError, ssl.SSLError, subprocess.SubprocessError) as e:
        print("TabDock: не удалось создать сертификат HTTPS (нужна команда openssl): %s" % e, flush=True)
        return None, ""
