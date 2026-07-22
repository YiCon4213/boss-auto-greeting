from pathlib import Path


WEB = Path("agent_app/web")


def test_workbench_assets_render_user_content_safely_without_remote_dependencies():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    script = (WEB / "app.js").read_text(encoding="utf-8")
    combined = html + script

    assert "innerHTML" not in combined
    assert "textContent" in script
    assert "http://" not in combined
    assert "https://" not in combined
    assert "api_key" not in combined.lower()
    assert "api key" not in combined.lower()
    assert "execute_delivery" not in combined
    assert "/execute" not in combined


def test_approval_button_requires_review_state_and_valid_selected_items():
    script = (WEB / "app.js").read_text(encoding="utf-8")

    assert 'state.batch.status === "awaiting_approval"' in script
    assert "item.selected && !item.approvable" in script
    assert "greeting.length < 20" in script
    assert "approveButton.disabled" in script
    assert "setInterval" in script
    assert "2000" in script
    assert "已批准，等待用户在 Phase 4 显式开始执行" in script


def test_workbench_has_narrow_screen_layout():
    styles = (WEB / "styles.css").read_text(encoding="utf-8")

    assert "@media" in styles
    assert "max-width: 760px" in styles
    assert "grid-template-columns: 1fr" in styles
