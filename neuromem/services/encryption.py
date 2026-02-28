"""Client-side envelope encryption for memory data.

Uses AES-256-GCM for data encryption and RSA-2048-OAEP for key wrapping.
Each encrypt() call generates a fresh AES key and nonce, ensuring
that the same plaintext produces different ciphertext every time.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class EncryptionService:
    """Envelope encryption: AES-256-GCM for data, RSA-2048-OAEP for key wrapping."""

    def __init__(
        self,
        public_key_path: str | None = None,
        private_key_path: str | None = None,
        passphrase: bytes | None = None,
    ):
        self._public_key = None
        self._private_key = None
        if public_key_path:
            self._public_key = self._load_public_key(public_key_path)
        if private_key_path:
            self._private_key = self._load_private_key(private_key_path, passphrase)

    @staticmethod
    def generate_keypair(
        private_key_path: str,
        public_key_path: str,
        passphrase: bytes | None = None,
    ) -> None:
        """Generate RSA-2048 keypair and save to PEM files.

        Private key file is chmod 0o600 (owner read/write only).
        """
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        enc = (
            serialization.BestAvailableEncryption(passphrase)
            if passphrase
            else serialization.NoEncryption()
        )

        priv_path = Path(private_key_path)
        priv_path.parent.mkdir(parents=True, exist_ok=True)
        priv_path.write_bytes(
            private_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                enc,
            )
        )
        os.chmod(private_key_path, 0o600)

        pub_path = Path(public_key_path)
        pub_path.parent.mkdir(parents=True, exist_ok=True)
        pub_path.write_bytes(
            private_key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )

    def encrypt(self, plaintext: str) -> dict:
        """Envelope encrypt a string.

        Returns dict with base64-encoded fields:
            encrypted_dek: RSA-wrapped AES key
            nonce: 12-byte GCM nonce
            ciphertext: AES-GCM encrypted data (includes 16-byte auth tag)
        """
        if not self._public_key:
            raise ValueError("Public key not loaded")

        data = plaintext.encode("utf-8")

        # Generate random AES-256 data encryption key
        dek = os.urandom(32)
        nonce = os.urandom(12)  # 96-bit nonce recommended for GCM

        # Encrypt data with AES-256-GCM
        ciphertext = AESGCM(dek).encrypt(nonce, data, None)

        # Wrap DEK with RSA-OAEP
        encrypted_dek = self._public_key.encrypt(
            dek,
            padding.OAEP(
                mgf=padding.MGF1(hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        return {
            "encrypted_dek": base64.b64encode(encrypted_dek).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "ciphertext": base64.b64encode(ciphertext).decode(),
        }

    def decrypt(self, envelope: dict) -> str:
        """Decrypt an envelope back to plaintext string.

        Args:
            envelope: Dict with encrypted_dek, nonce, ciphertext (base64).

        Returns:
            The original plaintext string.

        Raises:
            ValueError: If private key not loaded.
            cryptography exceptions: If decryption fails (wrong key, tampered data).
        """
        if not self._private_key:
            raise ValueError("Private key not loaded")

        # Unwrap DEK with RSA private key
        dek = self._private_key.decrypt(
            base64.b64decode(envelope["encrypted_dek"]),
            padding.OAEP(
                mgf=padding.MGF1(hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        # Decrypt data with AES-256-GCM
        plaintext = AESGCM(dek).decrypt(
            base64.b64decode(envelope["nonce"]),
            base64.b64decode(envelope["ciphertext"]),
            None,
        )

        return plaintext.decode("utf-8")

    @staticmethod
    def _load_public_key(path: str):
        return serialization.load_pem_public_key(Path(path).read_bytes())

    @staticmethod
    def _load_private_key(path: str, passphrase: bytes | None = None):
        return serialization.load_pem_private_key(
            Path(path).read_bytes(), password=passphrase,
        )
