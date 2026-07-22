import json
import os
from pathlib import Path
from typing import Protocol

import keyring
from keyring.errors import KeyringError, NoKeyringError


class SecretStore(Protocol):
    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str) -> None: ...

    def delete(self, key: str) -> None: ...


class FileSecretStore:
    def __init__(self, path: Path):
        self.path = path

    def _read(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def set(self, key: str, value: str) -> None:
        values = self._read()
        values[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(values), encoding="utf-8")
        os.chmod(self.path, 0o600)

    def get(self, key: str) -> str | None:
        return self._read().get(key)

    def delete(self, key: str) -> None:
        values = self._read()
        values.pop(key, None)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(values), encoding="utf-8")
        os.chmod(self.path, 0o600)


class KeyringSecretStore:
    def __init__(self, service_name: str = "boss-resume-delivery-agent"):
        self.service_name = service_name

    def get(self, key: str) -> str | None:
        return keyring.get_password(self.service_name, key)

    def set(self, key: str, value: str) -> None:
        keyring.set_password(self.service_name, key, value)

    def delete(self, key: str) -> None:
        keyring.delete_password(self.service_name, key)


class KeyringFirstSecretStore:
    def __init__(self, fallback: FileSecretStore):
        self.primary = KeyringSecretStore()
        self.fallback = fallback

    def get(self, key: str) -> str | None:
        try:
            return self.primary.get(key)
        except (NoKeyringError, KeyringError):
            return self.fallback.get(key)

    def set(self, key: str, value: str) -> None:
        try:
            self.primary.set(key, value)
        except (NoKeyringError, KeyringError):
            self.fallback.set(key, value)

    def delete(self, key: str) -> None:
        try:
            self.primary.delete(key)
        except (NoKeyringError, KeyringError):
            self.fallback.delete(key)


def create_secret_store(data_dir: Path) -> SecretStore:
    return KeyringFirstSecretStore(
        FileSecretStore(data_dir / ".boss-agent-secrets.json")
    )
