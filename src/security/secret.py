"""
加密/解密工具
"""
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def _derive_key(master_key: str, salt: bytes = None) -> tuple:
    """从 master_key 派生出 AES 密钥"""
    if salt is None:
        salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(master_key.encode('utf-8')))
    return key, salt


def encrypt_text(plain_text: str, master_key: str) -> str:
    """加密文本"""
    if not plain_text:
        return ""
    key, salt = _derive_key(master_key)
    f = Fernet(key)
    encrypted = f.encrypt(plain_text.encode('utf-8'))
    return base64.urlsafe_b64encode(salt + encrypted).decode('utf-8')


def decrypt_text(cipher_text: str, master_key: str) -> str:
    """解密文本"""
    if not cipher_text:
        return ""
    raw = base64.urlsafe_b64decode(cipher_text.encode('utf-8'))
    salt, encrypted = raw[:16], raw[16:]
    key, _ = _derive_key(master_key, salt)
    f = Fernet(key)
    return f.decrypt(encrypted).decode('utf-8')
