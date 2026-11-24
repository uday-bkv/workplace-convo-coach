"""Encrypted, short-retention storage for practice records.

* Records (and optional audio) are encrypted with Fernet (AES-128-CBC + HMAC).
* The key lives in a separate file with owner-only permissions. Deleting the key
  makes all stored data unreadable.
* Records older than the retention window are purged on every open.
* The participant can delete everything at any time with `delete_all()`.
"""

from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

DEFAULT_RETENTION_DAYS = 14


@dataclass
class PracticeRecord:
    id: str
    created_at: float
    scenario_id: str
    response_text: str
    input_mode: str  # "text" or "speech"
    criteria_met: dict[str, bool]
    has_audio: bool = False


class PracticeStore:
    def __init__(self, root: str | Path, retention_days: int = DEFAULT_RETENTION_DAYS):
        self.root = Path(root)
        self.retention_seconds = retention_days * 86400
        self.records_dir = self.root / "records"
        self.audio_dir = self.root / "audio"
        self.key_path = self.root / "key"
        self.records_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self._fernet = Fernet(self._load_or_create_key())
        self.purge_expired()

    # -- key handling -------------------------------------------------------
    def _load_or_create_key(self) -> bytes:
        if self.key_path.exists():
            return self.key_path.read_bytes()
        key = Fernet.generate_key()
        fd = os.open(self.key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(key)
        return key

    # -- write / read -------------------------------------------------------
    def save(self, record: PracticeRecord, audio_bytes: bytes | None = None) -> str:
        if audio_bytes is not None:
            (self.audio_dir / f"{record.id}.bin").write_bytes(self._fernet.encrypt(audio_bytes))
            record.has_audio = True
        payload = json.dumps(asdict(record)).encode("utf-8")
        (self.records_dir / f"{record.id}.bin").write_bytes(self._fernet.encrypt(payload))
        return record.id

    def list_records(self) -> list[PracticeRecord]:
        out = []
        for path in self.records_dir.glob("*.bin"):
            try:
                data = json.loads(self._fernet.decrypt(path.read_bytes()))
            except (InvalidToken, json.JSONDecodeError):
                continue
            out.append(PracticeRecord(**data))
        return sorted(out, key=lambda r: r.created_at)

    def load_audio(self, record_id: str) -> bytes | None:
        path = self.audio_dir / f"{record_id}.bin"
        if not path.exists():
            return None
        return self._fernet.decrypt(path.read_bytes())

    # -- deletion -----------------------------------------------------------
    def delete(self, record_id: str) -> bool:
        removed = False
        for path in (self.records_dir / f"{record_id}.bin", self.audio_dir / f"{record_id}.bin"):
            if path.exists():
                path.unlink()
                removed = True
        return removed

    def delete_audio_only(self) -> int:
        count = 0
        for path in self.audio_dir.glob("*.bin"):
            path.unlink()
            count += 1
        return count

    def purge_expired(self, now: float | None = None) -> int:
        now = time.time() if now is None else now
        purged = 0
        for rec in self.list_records():
            if now - rec.created_at > self.retention_seconds:
                self.delete(rec.id)
                purged += 1
        return purged

    def delete_all(self) -> None:
        """Remove every record, every audio clip and the key."""
        if self.root.exists():
            shutil.rmtree(self.root)


def new_record(scenario_id: str, response_text: str, input_mode: str, criteria_met: dict[str, bool]) -> PracticeRecord:
    return PracticeRecord(
        id=uuid.uuid4().hex,
        created_at=time.time(),
        scenario_id=scenario_id,
        response_text=response_text,
        input_mode=input_mode,
        criteria_met=criteria_met,
    )
