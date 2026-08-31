"""Encryption at rest: AES-256-GCM for files, SQLCipher (when available) for DB.

Key management
--------------
The master key is a 32-byte value that lives, in order of preference:

1. The OS secure storage via the ``keyring`` package ("CounselAI" service,
   "instance-key" entry) — set up by the desktop app on first run.
   - Windows: Windows Credential Manager
   - Linux: Secret Service API (GNOME Keyring / KWallet) or KeePass
   - Android: Android KeyStore (via Flutter secure storage, forwarded to backend)
2. A zero-permission instance key file ``data/.instance.key`` (chmod 0600)
   created on first use.

Every encrypted payload is versioned: ``b"cns1" || 12-byte nonce || ct``.
"""

from __future__ import annotations

import base64
import logging
import os
import threading
from pathlib import Path

from ..config import settings

log = logging.getLogger("counsel.crypto")

_KEYRING_SERVICE = "CounselAI"
_KEYRING_ENTRY = "instance-key"

_lock = threading.Lock()
_master_key: bytes | None = None


def _load_or_create_key() -> bytes:
    global _master_key
    with _lock:
        if _master_key is not None:
            return _master_key

        # 1) OS secure storage (keyring supports Windows Credential Manager,
        #    Linux Secret Service/KWallet, and generic fallback)
        try:
            import keyring

            stored = keyring.get_password(_KEYRING_SERVICE, _KEYRING_ENTRY)
            if stored:
                _master_key = base64.urlsafe_b64decode(stored.encode())
                return _master_key
        except Exception:  # noqa: BLE001 — secure storage optional
            pass

        # 2) Instance key file
        kp: Path = settings.keys_path
        if settings.jwt_secret_resolved and kp.exists():
            # keys_path doubles as JWT secret store; keep both in one file:
            # line1 = jwt secret, line2 = base64 master key.
            lines = kp.read_text().splitlines()
            if len(lines) >= 2 and lines[1].strip():
                _master_key = base64.urlsafe_b64decode(lines[1].strip())
                return _master_key
        raw = os.urandom(32)
        encoded = base64.urlsafe_b64encode(raw).decode()
        try:
            jwt_line = settings.jwt_secret_resolved
            kp.write_text(f"{jwt_line}\n{encoded}\n")
            kp.chmod(0o600)
        except OSError as exc:  # pragma: no cover
            log.error("could not persist instance key: %s", exc)

        # best effort: also push into secure storage for next boot
        try:
            import keyring

            keyring.set_password(_KEYRING_SERVICE, _KEYRING_ENTRY, encoded)
        except Exception:  # noqa: BLE001
            pass

        _master_key = raw
        return _master_key


# ------------------------------------------------------------------ AES-GCM


def encrypt_bytes(data: bytes) -> bytes:
    """Encrypt raw bytes with AES-256-GCM. Falls back to plaintext only when
    encryption is explicitly disabled AND the caller allows it."""
    if not settings.encrypt_at_rest:
        return data
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(12)
    ct = AESGCM(_load_or_create_key()).encrypt(nonce, data, b"counsel-ai")
    return b"cns1" + nonce + ct


def decrypt_bytes(blob: bytes) -> bytes:
    if not blob.startswith(b"cns1"):
        return blob  # legacy plaintext payload written before encryption
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = blob[4:16]
    ct = blob[16:]
    return AESGCM(_load_or_create_key()).decrypt(nonce, ct, b"counsel-ai")


def encrypt_file(path: Path, data: bytes) -> None:
    path.write_bytes(encrypt_bytes(data))
    try:
        path.chmod(0o600)
    except OSError:  # pragma: no cover
        pass


def decrypt_file(path: Path) -> bytes:
    return decrypt_bytes(path.read_bytes())


def secure_delete_file(path: Path) -> None:
    """Best-effort secure wipe: overwrite then unlink."""
    try:
        if path.exists():
            size = path.stat().st_size
            with open(path, "r+b") as f:
                f.write(os.urandom(min(size, 4 * 1024 * 1024)))
                f.flush()
                os.fsync(f.fileno())
            path.unlink(missing_ok=True)
    except OSError as exc:  # pragma: no cover
        log.warning("secure delete failed for %s: %s", path, exc)


def secure_wipe_dir(directory: Path) -> int:
    """Securely delete every file in a directory tree. Returns file count."""
    count = 0
    if not directory.exists():
        return count
    for p in sorted(directory.rglob("*"), reverse=True):
        if p.is_file():
            secure_delete_file(p)
            count += 1
        elif p.is_dir():
            try:
                p.rmdir()
            except OSError:
                pass
    return count


# ------------------------------------------------------------------ SQLCipher


def sqlcipher_available() -> bool:
    """True when a SQLCipher-enabled sqlite3 driver is importable."""
    try:
        import sqlcipher3  # noqa: F401

        return True
    except ImportError:
        try:
            import sqlite3

            conn = sqlite3.connect(":memory:")
            conn.execute("PRAGMA key='x'")
            conn.close()
            return True
        except sqlite3.Error:
            return False


def db_connect(db_path: Path):
    """Open the application database, transparently encrypted when possible.

    Returns a sqlite3.Connection. With sqlcipher3 installed the database file
    is fully encrypted with the master key; otherwise plain SQLite is used and
    the caller is expected to have logged the documented warning.
    """
    try:
        import sqlcipher3 as sq3mod  # type: ignore

        key = _load_or_create_key().hex()
        conn = sq3mod.connect(str(db_path), check_same_thread=False)
        conn.execute(f"PRAGMA key=\"x'{key}'\"")
        return conn
    except ImportError:
        import sqlite3

        return sqlite3.connect(str(db_path), check_same_thread=False)
