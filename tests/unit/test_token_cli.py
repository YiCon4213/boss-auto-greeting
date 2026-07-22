from io import StringIO

from agent_app.cli import main
from agent_app.config import Settings
from agent_app.infrastructure.secrets import FileSecretStore


def test_show_browser_token_prints_only_browser_token(tmp_path):
    store = FileSecretStore(tmp_path / "secrets.json")
    store.set("browser_token", "browser-secret")
    store.set("app_token", "app-secret")
    store.set("openai_api_key", "model-secret")
    output = StringIO()
    exit_code = main(
        ["show-browser-token"],
        settings=Settings(data_dir=tmp_path),
        secret_store=store,
        stdout=output,
    )
    assert exit_code == 0
    assert output.getvalue() == "browser-secret\n"
    assert "app-secret" not in output.getvalue()
    assert "model-secret" not in output.getvalue()


def test_unknown_cli_command_returns_nonzero(tmp_path):
    output = StringIO()
    exit_code = main(
        ["unknown"],
        settings=Settings(data_dir=tmp_path),
        secret_store=FileSecretStore(tmp_path / "secrets.json"),
        stdout=output,
    )
    assert exit_code != 0
