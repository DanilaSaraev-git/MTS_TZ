from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from review_runtime.fakes.review_executor import TrustedFixtureReviewExecutor
from review_runtime.postgres.durable import DurableReviewPlatform


def test_report_and_artifacts_survive_new_process_composition(tmp_path: Path) -> None:
    database_url = os.environ.get(
        "REVIEW_TEST_DATABASE_URL",
        "postgresql://v.enbaev@127.0.0.1:55439/review",
    ).replace("postgresql+psycopg://", "postgresql://", 1)
    try:
        connection = psycopg.connect(database_url, connect_timeout=1)
    except psycopg.Error:
        pytest.fail("real PostgreSQL 18 integration database is required")
    with connection:
        connection.execute("DELETE FROM runtime_state")
    root = Path(__file__).parents[2]
    first = DurableReviewPlatform(
        TrustedFixtureReviewExecutor(root),
        database_url=database_url,
        artifact_root=tmp_path / "artifacts",
    )
    document = first.upload(
        first.workspace_id,
        "synthetic-spec.md",
        "text/markdown",
        (root / "tests/fixtures/synthetic-review/synthetic-spec.md").read_bytes(),
    )
    profile = first.system_profile
    run = first.create_run(
        first.workspace_id,
        {
            "document_id": document["id"],
            "context_document_ids": [],
            "profile": {"id": profile.id, "version": profile.version},
            "model_profile": {"id": "deterministic-v1", "version": "1.0.0"},
            "locale": "en-US",
        },
        str(uuid4()),
    )
    report, etag = first.report(first.workspace_id, run["id"])
    second = DurableReviewPlatform(
        TrustedFixtureReviewExecutor(root),
        database_url=database_url,
        artifact_root=tmp_path / "artifacts",
    )
    assert second.report(second.workspace_id, run["id"]) == (report, etag)
    assert second.get_document(second.workspace_id, document["id"]).content
