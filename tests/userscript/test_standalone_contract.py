from pathlib import Path


SCRIPT = Path("zhipin-auto-greeting.user.js")


def test_agent_mode_defaults_off_and_preserves_standalone_start():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "agentModeEnabled: false" in source
    assert "const StandaloneAutomation = Automation" in source
    assert "if (!config.agentModeEnabled)" in source
    assert "StandaloneAutomation.start()" in source


def test_standalone_mode_does_not_start_the_agent_bridge():
    source = SCRIPT.read_text(encoding="utf-8")
    route_start = source[source.index("function startSelectedMode()") :]
    route_start = route_start[: route_start.index("\n  }") + 4]
    assert "if (!config.agentModeEnabled)" in route_start
    assert route_start.index("StandaloneAutomation.start()") < route_start.index(
        "AgentBridge.start()"
    )
