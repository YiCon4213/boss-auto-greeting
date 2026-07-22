from pathlib import Path


SCRIPT = Path("zhipin-auto-greeting.user.js")


def test_worker_id_persistence_does_not_replace_config_with_void_save_result():
    source = SCRIPT.read_text(encoding="utf-8")
    worker_id = source[source.index("    workerId() {") :]
    worker_id = worker_id[: worker_id.index("\n    },")]

    assert "config = saveConfig(" not in worker_id
    assert "saveConfig({ agentWorkerId:" in worker_id
