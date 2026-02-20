from __future__ import annotations

import hashlib
import hmac
import secrets
import subprocess
from datetime import datetime
from pathlib import Path


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

        payload = self.db_path.read_bytes()
        encrypted = self._encrypt_payload(payload, key)
        target.write_bytes(encrypted)
        self._enforce_retention(max_backups=30)
        return target

    def restore_backup(self, backup_file: Path | str) -> Path:
        backup_path = Path(backup_file)
        key = self._get_or_create_key(self.backup_dir / ".backup.key")

        encrypted = backup_path.read_bytes()
        payload = self._decrypt_payload(encrypted, key)

        self.db_path.unlink(missing_ok=True)
        self.db_path.write_bytes(payload)
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
        cipher = self._openssl(payload, key, decrypt=False)
        tag = hmac.new(key, cipher, hashlib.sha256).digest()
        return b"OSSL1" + tag + cipher

    def _decrypt_payload(self, blob: bytes, key: bytes) -> bytes:
        if len(blob) < 37 or not blob.startswith(b"OSSL1"):
            raise ValueError("Invalid encrypted backup format")
        tag = blob[5:37]
        cipher = blob[37:]
        expected = hmac.new(key, cipher, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected):
            raise ValueError("Backup integrity check failed")
        return self._openssl(cipher, key, decrypt=True)

    def _openssl(self, data: bytes, key: bytes, *, decrypt: bool) -> bytes:
        cmd = [
            "openssl",
            "enc",
            "-aes-256-cbc",
            "-pbkdf2",
            "-iter",
            "200000",
            "-salt",
            "-pass",
            f"pass:{key.hex()}",
        ]
        if decrypt:
            cmd.insert(3, "-d")

        proc = subprocess.run(cmd, input=data, capture_output=True)
        if proc.returncode != 0:
            raise ValueError(f"Backup cipher operation failed: {proc.stderr.decode('utf-8', errors='ignore').strip()}")
        return proc.stdout