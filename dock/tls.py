"""HTTPS for everything that leaves this computer: a self-signed certificate made once and kept in data/tls.

No certificate authority can vouch for a device on a home network, so the app remembers the certificate's
fingerprint when it is paired (the QR code carries it) and refuses any other. Browsers warn once.
"""
import hashlib
import os
import secrets
import shutil
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


# ---------------- without openssl (Windows): a self-signed RSA certificate written in pure Python ----------------
def _is_prime(n, rounds=40):
    if n < 2:
        return False
    for p in SMALL_PRIMES:
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(rounds):
        x = pow(secrets.randbelow(n - 3) + 2, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


SMALL_PRIMES = [p for p in range(3, 2000, 2) if all(p % q for q in range(3, int(p ** 0.5) + 1, 2))]


def _prime(bits, e):
    while True:
        n = secrets.randbits(bits) | (3 << (bits - 2)) | 1      # top two bits set: the product has the full size
        if _is_prime(n) and (n - 1) % e:
            return n


def _len(n):
    if n < 0x80:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(b)]) + b


def _tlv(tag, body):
    return bytes([tag]) + _len(len(body)) + body


def _int(n):
    b = n.to_bytes(max(1, (n.bit_length() + 8) // 8), "big")      # room for the sign bit
    return _tlv(0x02, b)


def _seq(*items):
    return _tlv(0x30, b"".join(items))


def _oid(dotted):
    parts = [int(x) for x in dotted.split(".")]
    body = bytes([40 * parts[0] + parts[1]])
    for p in parts[2:]:
        enc = [p & 0x7F]
        p >>= 7
        while p:
            enc.append(0x80 | (p & 0x7F))
            p >>= 7
        body += bytes(reversed(enc))
    return _tlv(0x06, body)


def _bits(b, unused=0):
    return _tlv(0x03, bytes([unused]) + b)


def _name(cn):
    return _seq(_tlv(0x31, _seq(_oid("2.5.4.3"), _tlv(0x0C, cn.encode()))),
                _tlv(0x31, _seq(_oid("2.5.4.10"), _tlv(0x0C, b"TabDock"))))


def _ext(oid, value, critical=False):
    return _seq(_oid(oid), *([_tlv(0x01, b"\xff")] if critical else []), _tlv(0x04, value))


def _pem(kind, der):
    import base64
    b = base64.b64encode(der).decode()
    return "-----BEGIN %s-----\n%s\n-----END %s-----\n" % (kind, "\n".join(b[i:i + 64] for i in range(0, len(b), 64)), kind)


def make_certificate_python(cert, key, days=3650):
    import datetime
    e = 65537
    while True:
        p, q = _prime(1024, e), _prime(1024, e)
        if p != q:
            break
    n, phi = p * q, (p - 1) * (q - 1)
    d = pow(e, -1, phi)
    sha_rsa = _seq(_oid("1.2.840.113549.1.1.11"), _tlv(0x05, b""))
    spki = _seq(_seq(_oid("1.2.840.113549.1.1.1"), _tlv(0x05, b"")), _bits(_seq(_int(n), _int(e))))
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    t = lambda x: _tlv(0x17, x.strftime("%y%m%d%H%M%SZ").encode())       # UTCTime (valid until 2049)
    exts = _seq(
        _ext("2.5.29.17", _seq(_tlv(0x82, b"localhost"), _tlv(0x87, bytes([127, 0, 0, 1])))),   # subjectAltName
        _ext("2.5.29.19", _seq(), critical=True),                                                    # basicConstraints: not a CA
        _ext("2.5.29.15", _bits(b"\xa0", 5), critical=True),                                        # digitalSignature, keyEncipherment
        _ext("2.5.29.37", _seq(_oid("1.3.6.1.5.5.7.3.1"))))                                          # serverAuth
    tbs = _seq(_tlv(0xA0, _int(2)), _int(secrets.randbits(63) | 1), sha_rsa, _name("TabDock"),
               _seq(t(now - datetime.timedelta(days=1)), t(now + datetime.timedelta(days=days))), _name("TabDock"), spki,
               _tlv(0xA3, exts))
    digest_info = bytes.fromhex("3031300d060960864801650304020105000420") + hashlib.sha256(tbs).digest()
    k = (n.bit_length() + 7) // 8
    em = b"\x00\x01" + b"\xff" * (k - len(digest_info) - 3) + b"\x00" + digest_info       # EMSA-PKCS1-v1_5
    sig = pow(int.from_bytes(em, "big"), d, n).to_bytes(k, "big")
    der = _seq(tbs, sha_rsa, _bits(sig))
    rsa = _seq(_int(0), _int(n), _int(e), _int(d), _int(p), _int(q), _int(d % (p - 1)), _int(d % (q - 1)), _int(pow(q, -1, p)))
    os.makedirs(os.path.dirname(cert), exist_ok=True)
    with open(key, "w", encoding="utf-8") as f:
        f.write(_pem("RSA PRIVATE KEY", rsa))
    os.chmod(key, 0o600)
    with open(cert, "w", encoding="utf-8") as f:
        f.write(_pem("CERTIFICATE", der))


def fingerprint(cert):
    with open(cert, encoding="utf-8") as f:
        return hashlib.sha256(ssl.PEM_cert_to_DER_cert(f.read())).hexdigest()


def setup(data_dir):
    """(SSL context, sha-256 fingerprint), or (None, "") when no certificate can be made."""
    cert, key = os.path.join(data_dir, "tls", "cert.pem"), os.path.join(data_dir, "tls", "key.pem")
    try:
        if not (os.path.exists(cert) and os.path.exists(key)):
            if shutil.which("openssl"):
                make_certificate(cert, key)
            else:          # Windows has no openssl command
                make_certificate_python(cert, key)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(cert, key)
        return ctx, fingerprint(cert)
    except (OSError, ssl.SSLError, subprocess.SubprocessError) as e:
        print("TabDock: не удалось создать сертификат HTTPS (нужна команда openssl): %s" % e, flush=True)
        return None, ""
