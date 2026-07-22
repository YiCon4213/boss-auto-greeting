from agent_app.infrastructure.secrets import FileSecretStore


def test_file_secret_store_never_returns_other_keys(tmp_path):
    store = FileSecretStore(tmp_path / "secrets.json")
    store.set("openai_api_key", "secret-value")
    assert store.get("openai_api_key") == "secret-value"
    assert store.get("missing") is None
