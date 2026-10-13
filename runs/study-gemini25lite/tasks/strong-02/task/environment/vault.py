import os
import yaml
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

CONFIG_PATH = "/etc/vault/config.yaml"

def get_config():
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)

def derive_iv(master_iv, sequence_n, salt):
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=12,
        salt=salt,
        iterations=1000,
    )
    return kdf.derive(master_iv + sequence_n.to_bytes(4, 'big'))

class LogVault:
    def __init__(self, key, salt):
        self.aesgcm = AESGCM(key)
        self.salt = salt

    def encrypt_block(self, data, master_iv, sequence_n):
        iv = derive_iv(master_iv, sequence_n, self.salt)
        return self.aesgcm.encrypt(iv, data, None)

    def decrypt_block(self, ciphertext, master_iv, sequence_n):
        iv = derive_iv(master_iv, sequence_n, self.salt)
        return self.aesgcm.decrypt(iv, ciphertext, None)
