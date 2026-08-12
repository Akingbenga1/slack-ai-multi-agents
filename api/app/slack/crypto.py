"""Lightweight token wrapping for slack_installs.bot_token_encrypted."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from api.app.settings import Settings


def _encryption_secret(settings: Settings) -> str:
    explicit = (settings.token_encryption_key or "").strip()
    if explicit:
        return explicit
    return settings.jwt_secret


def _fernet(settings: Settings) -> Fernet:
    digest = hashlib.sha256(_encryption_secret(settings).encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_bot_token(token: str, settings: Settings) -> str:
    return _fernet(settings).encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_bot_token(token_encrypted: str, settings: Settings) -> str:
    try:
        return _fernet(settings).decrypt(token_encrypted.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt bot token") from exc
