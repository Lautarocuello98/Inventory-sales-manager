from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UpdateInfo:
    latest_version: str
    download_url: str
    notes: str


class UpdateService:
    def __init__(self, current_version: str, source: str | Path):
        self.current_version = current_version
        self.source = str(source)

    def _read_manifest(self) -> dict:
        src = self.source.strip()
        if src.startswith("http://") or src.startswith("https://"):
            with urllib.request.urlopen(src, timeout=5) as r:  # nosec B310
                return json.loads(r.read().decode("utf-8"))
        path = Path(src)
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _to_tuple(v: str) -> tuple[int, int, int]:
        cleaned = v.strip().lower()
        if cleaned.startswith("v"):
            cleaned = cleaned[1:]

        nums = [int(n) for n in re.findall(r"\d+", cleaned)[:3]]
        while len(nums) < 3:
            nums.append(0)
        return tuple(nums)

    def check_for_update(self) -> UpdateInfo | None:
        manifest = self._read_manifest()
        latest = str(manifest.get("version", "0.0.0"))
        if self._to_tuple(latest) <= self._to_tuple(self.current_version):
            return None
        return UpdateInfo(
            latest_version=latest,
            download_url=str(manifest.get("download_url", "")),
            notes=str(manifest.get("notes", "")),
        )