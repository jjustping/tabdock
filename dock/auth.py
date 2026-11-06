"""Server password (PBKDF2) + simple brute-force protection."""
import hashlib
import hmac
import secrets
import threading
import time

ITER = 200_000
_fail = {}
_lock = threading.Lock()


def hash_password(pw):
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), ITER)
    return "pbkdf2$%d$%s$%s" % (ITER, salt, dk.hex())


def check_password(pw, stored):
    try:
        _, it, salt, h = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), int(it))
        return hmac.compare_digest(dk.hex(), h)
    except Exception:
        return False


def allowed(ip):
    """Max 5 wrong attempts per 5 minutes per IP and 20 overall (slows down distributed guessing)."""
    with _lock:
        now = time.time()
        for k in list(_fail):
            _fail[k] = [t for t in _fail[k] if now - t < 300]
        total = sum(len(v) for v in _fail.values())
        return len(_fail.get(ip, [])) < 5 and total < 20


def failed(ip):
    with _lock:
        _fail.setdefault(ip, []).append(time.time())
