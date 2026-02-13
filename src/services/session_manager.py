###     SessionManager (Persistente Masking-Sessions mit TTL)
### __________________________________________________________________________
#
#  - Verwaltet Sessions für reversible Maskierung (token -> original)
#  - Persistiert Sessions auf Disk als JSON (<data>/sessions.json)
#  - TTL gilt ab closed_at (aktive Sessions laufen unbegrenzt bis close_active_session())
#  - Cleanup wird beim Laden (Startup) und vor Operationen durchgeführt
#  - Atomisches Schreiben über *.tmp + replace()
#
#  Erweiterung (wichtig für stabile Tokens):
#    - Pro Session zusätzlich ein Index: (LABEL, ORIGINAL) -> TOKEN
#    - Damit kann die Pipeline beim Maskieren denselben Token wiederverwenden,
#      ohne dass Session-Mapping als "Detektor" missbraucht wird.
#
#  Datei-Format (pro Session):
#    {
#      "session_id": "...",
#      "created_at": ...,
#      "closed_at": ... | null,
#      "mapping": { "[PER_xxx]": "Max", ... },
#      "index": { "PER\u0000max": "[PER_xxx]", ... }
#    }
#


from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
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
            "version": 2,
            "ttl_seconds": self.ttl_seconds,
            "active_session_id": self._active_session_id,
            "sessions": list(self._sessions.values()),
        }
        self._write_atomic(
            self._storage_path,
            json.dumps(payload, ensure_ascii=False, indent=2),
        )

    def _make_index_key(self, label: str, original: str) -> str:
        return f"{label.upper()}\u0000{str(original).strip().lower()}"

    def _rebuild_index(self, mapping: Dict[str, str]) -> Dict[str, str]:
        idx: Dict[str, str] = {}
        for token, original in mapping.items():
            if not isinstance(token, str) or not token:
                continue
            if original is None:
                continue
            if "_" not in token:
                continue
            label = token.split("_", 1)[0].upper()
            key = self._make_index_key(label, str(original))
            if key not in idx:
                idx[key] = token
        return idx

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
            index = s.get("index")

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

            norm_idx: Dict[str, str] = {}
            if isinstance(index, dict):
                for k, v in index.items():
                    if not isinstance(k, str) or not k:
                        continue
                    if not isinstance(v, str) or not v:
                        continue
                    norm_idx[k] = v

            if not norm_idx:
                norm_idx = self._rebuild_index(norm_map)

            self._sessions[sid] = {
                "session_id": sid,
                "created_at": float(created_at),
                "closed_at": float(closed_at) if isinstance(closed_at, (int, float)) else None,
                "mapping": norm_map,
                "index": norm_idx,
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
            "index": {},
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

    def get_active_index(self) -> Dict[str, str]:
        self._cleanup_expired()
        if not self._active_session_id:
            return {}
        sess = self._sessions.get(self._active_session_id)
        if not sess:
            return {}
        idx = sess.get("index")
        if not isinstance(idx, dict):
            return {}
        return dict(idx)

    def find_existing_token(self, label: str, original: str) -> Optional[str]:
        self._cleanup_expired()
        if not self._active_session_id:
            return None
        sess = self._sessions.get(self._active_session_id)
        if not sess:
            return None

        idx = sess.get("index")
        if not isinstance(idx, dict):
            return None

        key = self._make_index_key(label, original)
        tok = idx.get(key)
        if not isinstance(tok, str) or not tok:
            return None

        mp = sess.get("mapping")
        if not isinstance(mp, dict):
            return None
        if tok not in mp:
            return None

        if str(mp.get(tok, "")).strip() != str(original).strip():
            return None

        return tok

    def add_mapping(self, mapping: Dict[str, str]) -> None:
        if not mapping:
            return

        sess = self._ensure_active_session()
        sess_map: Dict[str, str] = sess.get("mapping") or {}
        sess_idx: Dict[str, str] = sess.get("index") or {}

        changed = False

        for token, original in mapping.items():
            if not token:
                continue
            if original is None:
                continue

            sv = str(original)

            if sess_map.get(token) != sv:
                sess_map[token] = sv
                changed = True

            if "_" in token:
                label = token.split("_", 1)[0].upper()
                idx_key = self._make_index_key(label, sv)
                if sess_idx.get(idx_key) != token:
                    sess_idx[idx_key] = token
                    changed = True

        sess["mapping"] = sess_map
        sess["index"] = sess_idx

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
        index: Dict[str, str] = sess.get("index") or {}

        if token in mapping:
            old_val = mapping.pop(token, None)
            if old_val is not None and "_" in token:
                label = token.split("_", 1)[0].upper()
                idx_key = self._make_index_key(label, str(old_val))
                if index.get(idx_key) == token:
                    index.pop(idx_key, None)

            sess["mapping"] = mapping
            sess["index"] = index
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