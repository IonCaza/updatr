import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

_KEY_BYTES = 32
_NONCE_BYTES = 12


def _get_key() -> bytes:
    raw = settings.ENCRYPTION_KEY
    try:
        key = bytes.fromhex(raw)
        if len(key) >= _KEY_BYTES:
            return key[:_KEY_BYTES]
    except ValueError:
        pass
    return hashlib.sha256(raw.encode()).digest()


def encrypt(plaintext: str) -> bytes:
    key = _get_key()
    nonce = os.urandom(_NONCE_BYTES)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return nonce + ciphertext


def decrypt(data: bytes) -> str:
    key = _get_key()
    nonce = data[:_NONCE_BYTES]
    ciphertext = data[_NONCE_BYTES:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None).decode()
