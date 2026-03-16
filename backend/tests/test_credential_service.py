from app.services.credential_service import encrypt, decrypt


def test_encrypt_decrypt_roundtrip():
    plaintext = "my-super-secret-password"
    ciphertext = encrypt(plaintext)
    assert decrypt(ciphertext) == plaintext


def test_encrypt_produces_different_outputs():
    ct1 = encrypt("same-value")
    ct2 = encrypt("same-value")
    assert ct1 != ct2


def test_encrypted_data_is_bytes():
    ct = encrypt("hello")
    assert isinstance(ct, bytes)
    assert len(ct) > len("hello")


def test_empty_string_roundtrip():
    ct = encrypt("")
    assert decrypt(ct) == ""


def test_unicode_roundtrip():
    plaintext = "p@ssw0rd_with_ünîcödé!"
    ct = encrypt(plaintext)
    assert decrypt(ct) == plaintext
