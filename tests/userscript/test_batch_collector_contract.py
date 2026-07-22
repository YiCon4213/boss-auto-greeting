from pathlib import Path


SCRIPT = Path("zhipin-auto-greeting.user.js")


def collector_source():
    source = SCRIPT.read_text(encoding="utf-8")
    start = source.index("const BatchCollector =")
    end = source.index("const ApprovedQueueRunner =", start)
    return source[start:end]


def test_collector_uses_detail_repository_without_chat_send():
    collector = collector_source()
    assert "JobRepository.waitForJobDetail" in collector
    assert "waitForJobCommunicationDetail" in collector
    assert "postSnapshot" in collector
    assert "findChatButton" not in collector
    assert "GreetingService.sendCurrent" not in collector
    assert "clickElement(chatButton)" not in collector


def test_collector_has_isolated_resume_state_and_marks_only_accepted_jobs():
    source = SCRIPT.read_text(encoding="utf-8")
    collector = collector_source()
    assert "__zhipin_agent_task_state__" in source
    assert "APP.runKey" not in collector
    assert "processedKeys" in collector
    assert "outcome.accepted || outcome.duplicate" in collector
    assert "collectedCount" in collector


def test_collector_stops_at_limit_or_security_without_sending():
    collector = collector_source()
    assert "state.collectedCount >= state.limit" in collector
    assert "noProgressScrolls >= 3" in collector
    assert "detectAgentSecurityBlock" in collector
    assert "paused_security" in collector


def test_dispatch_only_routes_known_task_types():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "async function dispatchAgentTask(task)" in source
    assert "if (task.type === 'collect_batch') return BatchCollector.run(task);" in source
    assert "if (task.type === 'execute_delivery') return ApprovedQueueRunner.run(task);" in source
    assert "if (task.type === 'pause') return BatchCollector.pause(task);" in source
    assert "发送队列尚未实现" in source
