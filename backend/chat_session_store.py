"""
In-memory demo chat sessions (single-process). Survives for the lifetime of the server process.
For multi-worker deployments, move this to Redis or store messages in Postgres.
"""
from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field


@dataclass
class ChatDemoSession:
    session_secret: str
    """(role, content) with role in user|assistant — same shape as recruiter_chat."""
    transcript_turns: list[tuple[str, str]] = field(default_factory=list)
    ended: bool = False
    post_call_ran: bool = False


_lock = threading.Lock()
_by_chat_id: dict[str, ChatDemoSession] = {}


def create_session(chat_id: str) -> str:
    secret = secrets.token_urlsafe(32)
    with _lock:
        _by_chat_id[chat_id] = ChatDemoSession(session_secret=secret, transcript_turns=[])
    return secret


def get_session(chat_id: str) -> ChatDemoSession | None:
    with _lock:
        return _by_chat_id.get(chat_id)


def validate_secret(chat_id: str, secret: str | None) -> bool:
    if not secret:
        return False
    s = get_session(chat_id)
    return s is not None and secrets.compare_digest(s.session_secret, secret)


def set_opening_turns(chat_id: str, turns: list[tuple[str, str]]) -> None:
    with _lock:
        sess = _by_chat_id.get(chat_id)
        if sess:
            sess.transcript_turns = list(turns)


def append_user_and_assistant(chat_id: str, user_text: str, assistant_text: str) -> None:
    with _lock:
        sess = _by_chat_id.get(chat_id)
        if sess:
            sess.transcript_turns.append(("user", user_text))
            sess.transcript_turns.append(("assistant", assistant_text))


def set_ended(chat_id: str) -> None:
    with _lock:
        sess = _by_chat_id.get(chat_id)
        if sess:
            sess.ended = True


def mark_post_call_ran(chat_id: str) -> None:
    with _lock:
        sess = _by_chat_id.get(chat_id)
        if sess:
            sess.post_call_ran = True


def already_ended(chat_id: str) -> bool:
    s = get_session(chat_id)
    return bool(s and s.ended)
