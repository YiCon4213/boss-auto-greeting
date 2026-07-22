from sqlalchemy import inspect

from agent_app.config import Settings
from agent_app.infrastructure.database import create_engine_and_session
from agent_app.infrastructure.models import Base


def test_initial_schema_contains_agent_tables(tmp_path):
    engine, _ = create_engine_and_session(Settings(data_dir=tmp_path))
    Base.metadata.create_all(engine)
    assert set(inspect(engine).get_table_names()) == {
        "profiles",
        "base_greetings",
        "model_configs",
        "batches",
        "job_snapshots",
        "analyses",
        "greetings",
        "approval_versions",
        "delivery_items",
        "browser_tasks",
        "audit_events",
    }
