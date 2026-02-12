###     SessionManager (Persistente Masking-Sessions mit TTL)
### __________________________________________________________________________
#
#  - Verwaltet Sessions für reversible Maskierung (token -> original)
#  - Persistiert Sessions auf Disk als JSON (<data>/sessions.json)
#  - TTL gilt ab closed_at (aktive Sessions laufen unbegrenzt bis close_active_session())
#  - Cleanup wird beim Laden (Startup) und vor Operationen durchgeführt
#  - Atomisches Schreiben über *.tmp + replace()
#  - API passt zu UI: add_mapping(), get_active_mapping(), remove_from_active_mapping(),
#    close_active_session(), list_sessions(), delete_session(), clear_all()


from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from uuid import uuid4

from core.paths import data_dir


SESSION_TTL_SECONDS = 24 * 60 * 60


class SessionManager:
    def __init__(
        self,
        ttl_seconds: int = SESSION_TTL_SECONDS,
        *,
        storage_path: Optional[Path] = None,
    ):
        self.ttl_seconds = int(ttl_seconds)
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._active_session_id: str | None = None

        self._storage_path = storage_path or (data_dir() / "sessions.json")

        self._load_from_disk()
        self._cleanup_expired()
        self._save_to_disk()

    def _now(self) -> float:
        return time.time()

    def _write_atomic(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)

    def _save_to_disk(self) -> None:
        payload = {
            "version": 1,
            "ttl_seconds": self.ttl_seconds,
            "active_session_id": self._active_session_id,
            "sessions": list(self._sessions.values()),
        }
        self._write_atomic(
            self._storage_path,
            json.dumps(payload, ensure_ascii=False, indent=2),
        )

    def _load_from_disk(self) -> None:
        self._sessions = {}
        self._active_session_id = None

        p = self._storage_path
        if not p.exists():
            return

        raw = p.read_text(encoding="utf-8").strip()
        if not raw:
            return

        try:
            data = json.loads(raw)
        except Exception:
            return

        if not isinstance(data, dict):
            return

        active = data.get("active_session_id")
        if isinstance(active, str) and active.strip():
            self._active_session_id = active.strip()

        sessions = data.get("sessions")
        if not isinstance(sessions, list):
            sessions = []

        for s in sessions:
            if not isinstance(s, dict):
                continue

            sid = s.get("session_id")
            if not isinstance(sid, str) or not sid.strip():
                continue

            created_at = s.get("created_at")
            closed_at = s.get("closed_at")
            mapping = s.get("mapping")

            if not isinstance(created_at, (int, float)):
                created_at = self._now()

            if closed_at is not None and not isinstance(closed_at, (int, float)):
                closed_at = None

            if not isinstance(mapping, dict):
                mapping = {}

            norm_map: Dict[str, str] = {}
            for k, v in mapping.items():
                if not isinstance(k, str) or not k:
                    continue
                if v is None:
                    continue
                norm_map[k] = str(v)

            self._sessions[sid] = {
                "session_id": sid,
                "created_at": float(created_at),
                "closed_at": float(closed_at) if isinstance(closed_at, (int, float)) else None,
                "mapping": norm_map,
            }

        if self._active_session_id and self._active_session_id not in self._sessions:
            self._active_session_id = None

    def _cleanup_expired(self) -> None:
        if not self._sessions:
            return

        now = self._now()
        to_delete: List[str] = []

        for sid, sess in self._sessions.items():
            closed_at = sess.get("closed_at")
            if not closed_at:
                continue
            if now - float(closed_at) >= self.ttl_seconds:
                to_delete.append(sid)

        for sid in to_delete:
            if sid == self._active_session_id:
                self._active_session_id = None
            self._sessions.pop(sid, None)

    def _ensure_active_session(self) -> Dict[str, Any]:
        self._cleanup_expired()

        if self._active_session_id and self._active_session_id in self._sessions:
            return self._sessions[self._active_session_id]

        sid = uuid4().hex
        now = self._now()

        sess = {
            "session_id": sid,
            "created_at": now,
            "closed_at": None,
            "mapping": {},
        }

        self._sessions[sid] = sess
        self._active_session_id = sid
        self._save_to_disk()
        return sess

    def get_active_mapping(self) -> Dict[str, str]:
        self._cleanup_expired()
        if not self._active_session_id:
            return {}
        sess = self._sessions.get(self._active_session_id)
        if not sess:
            return {}
        m = sess.get("mapping")
        if not isinstance(m, dict):
            return {}
        return dict(m)

    def add_mapping(self, mapping: Dict[str, str]) -> None:
        if not mapping:
            return

        sess = self._ensure_active_session()
        sess_map: Dict[str, str] = sess.get("mapping") or {}

        changed = False

        for k, v in mapping.items():
            if not k:
                continue
            if v is None:
                continue
            sv = str(v)
            if sess_map.get(k) != sv:
                sess_map[k] = sv
                changed = True

        sess["mapping"] = sess_map

        if changed:
            self._save_to_disk()

    def remove_from_active_mapping(self, token: str) -> None:
        self._cleanup_expired()

        if not self._active_session_id:
            return

        sess = self._sessions.get(self._active_session_id)
        if not sess:
            return

        mapping: Dict[str, str] = sess.get("mapping") or {}
        if token in mapping:
            mapping.pop(token, None)
            sess["mapping"] = mapping
            self._save_to_disk()

    def close_active_session(self) -> None:
        self._cleanup_expired()

        if not self._active_session_id:
            return

        sid = self._active_session_id
        sess = self._sessions.get(sid)

        if not sess:
            self._active_session_id = None
            self._save_to_disk()
            return

        if not sess.get("closed_at"):
            sess["closed_at"] = self._now()

        self._active_session_id = None
        self._cleanup_expired()
        self._save_to_disk()

    def list_sessions(self) -> List[Dict[str, Any]]:
        self._cleanup_expired()
        return list(self._sessions.values())

    def delete_session(self, session_id: str) -> None:
        self._cleanup_expired()

        if not session_id:
            return

        if session_id in self._sessions:
            self._sessions.pop(session_id, None)

        if self._active_session_id == session_id:
            self._active_session_id = None

        self._save_to_disk()

    def remove_session(self, session_id: str) -> None:
        self.delete_session(session_id)

    def clear_all(self) -> None:
        self._sessions.clear()
        self._active_session_id = None
        self._save_to_disk()