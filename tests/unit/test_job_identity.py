import pytest

from agent_app.application.snapshots import make_jd_fingerprint, make_job_identity_key


def test_identity_prefers_reliable_ids():
    assert make_job_identity_key(
        encrypt_job_id="job-123", security_id="sec-1", lid="lid-1"
    ) == "job:job-123|security:sec-1|lid:lid-1"


def test_snapshot_requires_a_reliable_identity():
    with pytest.raises(ValueError, match="reliable job identity"):
        make_job_identity_key(encrypt_job_id="", security_id="", lid="")


def test_jd_fingerprint_ignores_whitespace():
    assert make_jd_fingerprint("职责一\n\n职责二") == make_jd_fingerprint(
        "职责一 职责二"
    )
