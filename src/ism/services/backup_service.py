from __future__ import annotations

import hashlib
import hmac
import sqlite3
from datetime import datetime
from pathlib import Path
import secrets


class BackupService:
    def __init__(self, db_path: Path | str, backup_dir: Path | str):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)

    def create_backup(self) -> Path:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = self.backup_dir / f"sales_backup_{ts}.db.enc"
        key_path = self.backup_dir / ".backup.key"

        key = self._get_or_create_key(key_path)

        src = sqlite3.connect(str(self.db_path))
        dst = sqlite3.connect(":memory:")
        try:
            src.backup(dst)
            payload = "\n".join(dst.iterdump()).encode("utf-8")
            encrypted = self._encrypt_payload(payload, key)
            target.write_bytes(encrypted)
            self._enforce_retention(max_backups=30)
        finally:
            dst.close()
            src.close()
        return target

    def restore_backup(self, backup_file: Path | str) -> Path:
        backup_path = Path(backup_file)
        key = self._get_or_create_key(self.backup_dir / ".backup.key")

        encrypted = backup_path.read_bytes()
        payload = self._decrypt_payload(encrypted, key).decode("utf-8")

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.close()
            self.db_path.unlink(missing_ok=True)
            conn = sqlite3.connect(str(self.db_path))
            conn.executescript(payload)
            conn.commit()
        finally:
            conn.close()
        return self.db_path

    def _get_or_create_key(self, key_path: Path) -> bytes:
        if key_path.exists():
            return key_path.read_bytes().strip()
        key = secrets.token_bytes(32)
        key_path.write_bytes(key)
        try:
            key_path.chmod(0o600)
        except Exception:
            pass
        return key

    def _enforce_retention(self, max_backups: int) -> None:
        files = sorted(self.backup_dir.glob("sales_backup_*.db.enc"))
        if len(files) <= max_backups:
            return
        for old in files[: len(files) - max_backups]:
            old.unlink(missing_ok=True)

    def _encrypt_payload(self, payload: bytes, key: bytes) -> bytes:
        nonce = secrets.token_bytes(16)
        keystream = self._keystream(key, nonce, len(payload))
        cipher = bytes(a ^ b for a, b in zip(payload, keystream))
        tag = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
        return nonce + tag + cipher

    def _decrypt_payload(self, blob: bytes, key: bytes) -> bytes:
        if len(blob) < 48:
            raise ValueError("Invalid encrypted backup format")
        nonce = blob[:16]
        tag = blob[16:48]
        cipher = blob[48:]
        expected = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected):
            raise ValueError("Backup integrity check failed")
        keystream = self._keystream(key, nonce, len(cipher))
        return bytes(a ^ b for a, b in zip(cipher, keystream))

    def _keystream(self, key: bytes, nonce: bytes, length: int) -> bytes:
        out = bytearray()
        counter = 0
        while len(out) < length:
            block = hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest()
            out.extend(block)
            counter += 1
        return bytes(out[:length])