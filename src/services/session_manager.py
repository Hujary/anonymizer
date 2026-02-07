from __future__ import annotations

import time
from typing import Dict, Any, List
from uuid import uuid4

# Standard-Session-TTL: 24h
SESSION_TTL_SECONDS = 24 * 60 * 60


class SessionManager:
    def __init__(self, ttl_seconds: int = SESSION_TTL_SECONDS):
        self.ttl_seconds = int(ttl_seconds)
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._active_session_id: str | None = None

    def _now(self) -> float:
        return time.time()

    def _cleanup_expired(self) -> None:
        if not self._sessions:
            return
        now = self._now()
        to_delete: List[str] = []
        for sid, sess in self._sessions.items():
            closed_at = sess.get("closed_at")
            if not closed_at:
                continue
            if now - closed_at >= self.ttl_seconds:
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
        return sess

    def add_mapping(self, mapping: Dict[str, str]) -> None:
        if not mapping:
            return
        sess = self._ensure_active_session()
        sess_map: Dict[str, str] = sess.get("mapping") or {}
        for k, v in mapping.items():
            if not k:
                continue
            sess_map[k] = v
        sess["mapping"] = sess_map

    # >>> NEU: Token aus aktiver Session löschen
    def remove_from_active_mapping(self, token: str) -> None:
        """
        Entfernt einen Token-Key aus dem Mapping der aktiven Session,
        falls vorhanden. Wird beim Löschen im UI verwendet, damit der
        Token nicht beim nächsten Maskieren wieder auftaucht.
        """
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

    def close_active_session(self) -> None:
        if not self._active_session_id:
            return
        sid = self._active_session_id
        sess = self._sessions.get(sid)
        if not sess:
            self._active_session_id = None
            return
        if not sess.get("closed_at"):
            sess["closed_at"] = self._now()
        self._active_session_id = None
        self._cleanup_expired()

    def list_sessions(self) -> List[Dict[str, Any]]:
        self._cleanup_expired()
        return list(self._sessions.values())

    def delete_session(self, session_id: str) -> None:
        if not session_id:
            return
        if session_id in self._sessions:
            self._sessions.pop(session_id, None)
        if self._active_session_id == session_id:
            self._active_session_id = None

    def remove_session(self, session_id: str) -> None:
        self.delete_session(session_id)

    def clear_all(self) -> None:
        self._sessions.clear()
        self._active_session_id = None