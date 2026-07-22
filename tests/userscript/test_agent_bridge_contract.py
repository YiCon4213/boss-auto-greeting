from pathlib import Path


SCRIPT = Path("zhipin-auto-greeting.user.js")


def test_browser_bridge_is_local_and_whitelisted():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "const AgentBridge =" in source
    assert "http://127.0.0.1:8765" in source
    assert "new Set(['collect_batch', 'execute_delivery', 'pause'])" in source
    assert "unsupported_task_type" in source
    assert "eval(" not in source


def test_agent_endpoint_rejects_non_loopback_or_wrong_port():
    source = SCRIPT.read_text(encoding="utf-8")
    bridge = source[source.index("const AgentBridge =") :]
    assert "['127.0.0.1', 'localhost'].includes(url.hostname)" in bridge
    assert "url.port !== '8765'" in bridge
    assert "GM_xmlhttpRequest" in bridge


def test_agent_controls_are_visible_and_token_is_never_fetched_from_api():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "本地 Agent" in source
    assert 'data-field="agentModeEnabled"' in source
    assert 'data-field="agentBaseUrl"' in source
    assert 'data-field="agentBrowserToken"' in source
    assert 'data-action="checkAgentConnection"' in source
    assert "show-browser-token" in source
    assert "/show-browser-token" not in source
