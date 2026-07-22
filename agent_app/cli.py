import sys
from collections.abc import Sequence
from secrets import token_urlsafe
from typing import TextIO

from agent_app.config import Settings
from agent_app.infrastructure.secrets import SecretStore, create_secret_store


def main(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    secret_store: SecretStore | None = None,
    stdout: TextIO | None = None,
) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    output = stdout or sys.stdout
    if arguments != ["show-browser-token"]:
        return 2
    resolved_settings = settings or Settings()
    store = secret_store or create_secret_store(resolved_settings.data_dir)
    token = store.get("browser_token")
    if token is None:
        token = token_urlsafe(32)
        store.set("browser_token", token)
    print(token, file=output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
