from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


class OpenClawSecretCipher:
    # Phase 1 不額外引入大型加密依賴，因此用標準庫提供對稱加密與完整性保護。
    def __init__(self, secret_key: str) -> None:
        self.secret_key = secret_key.strip().encode("utf-8")
        self._key_material = hashlib.sha256(self.secret_key).digest() if self.secret_key else b""

    @property
    def is_enabled(self) -> bool:
        return bool(self._key_material)

    def encrypt(self, plaintext: str) -> str:
        if not self.is_enabled:
            raise ValueError("尚未設定 OPENCLAW_SECRET_KEY，無法保存 Gateway token。")

        payload = plaintext.encode("utf-8")
        nonce = secrets.token_bytes(16)
        ciphertext = _xor_bytes(payload, self._expand_keystream(nonce, len(payload)))
        signature = hmac.new(self._key_material, nonce + ciphertext, hashlib.sha256).digest()
        packed = nonce + signature + ciphertext
        return base64.urlsafe_b64encode(packed).decode("utf-8")

    def decrypt(self, encrypted_text: str) -> str:
        if not self.is_enabled:
            raise ValueError("尚未設定 OPENCLAW_SECRET_KEY，無法讀取 Gateway token。")

        packed = base64.urlsafe_b64decode(encrypted_text.encode("utf-8"))
        nonce = packed[:16]
        signature = packed[16:48]
        ciphertext = packed[48:]
        expected = hmac.new(self._key_material, nonce + ciphertext, hashlib.sha256).digest()

        if not hmac.compare_digest(signature, expected):
            raise ValueError("OpenClaw token 驗證失敗，可能是密鑰不一致或資料已損壞。")

        plaintext = _xor_bytes(ciphertext, self._expand_keystream(nonce, len(ciphertext)))
        return plaintext.decode("utf-8")

    def _expand_keystream(self, nonce: bytes, payload_length: int) -> bytes:
        # 用 nonce + counter 展開 keystream，讓同一把密鑰也能安全重複加密多筆資料。
        blocks: list[bytes] = []
        counter = 0

        while sum(len(block) for block in blocks) < payload_length:
            blocks.append(
                hashlib.sha256(self._key_material + nonce + counter.to_bytes(4, "big")).digest()
            )
            counter += 1

        return b"".join(blocks)[:payload_length]


def _xor_bytes(left: bytes, right: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(left, right))
