from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest
from review_core.application.platform import ReviewPlatform
from review_runtime.config.settings import OperatorSettings
from review_runtime.fakes.review_executor import TrustedFixtureReviewExecutor


@pytest.fixture(scope="session")
def database_url() -> str:
    value = os.environ.get(
        "REVIEW_TEST_DATABASE_URL",
        "postgresql+psycopg://v.enbaev@127.0.0.1:55439/review",
    )
    try:
        with psycopg.connect(value.replace("postgresql+psycopg://", "postgresql://", 1), connect_timeout=1):
            pass
    except psycopg.Error:
        pytest.fail("real PostgreSQL 18 integration database is required")
    return value


@pytest.fixture
def operator_settings(database_url: str, tmp_path: Path) -> OperatorSettings:
    return OperatorSettings(
        deployment_id="60000000-0000-4000-8000-000000000001",
        organization_id="30000000-0000-4000-8000-000000000001",
        organization_name="Synthetic Organization",
        workspace_id="20000000-0000-4000-8000-000000000001",
        workspace_name="Synthetic Workspace",
        actor_id="10000000-0000-4000-8000-000000000001",
        actor_display_name="Synthetic Analyst",
        artifact_root=tmp_path / "artifacts",
        database_url=database_url,
        queue_database_url=database_url.replace("postgresql+psycopg://", "postgresql://", 1),
        runtime_config_path=Path("deploy/compose/config/runtime-config.synthetic.v1.json"),
        system_profile_id="50000000-0000-4000-8000-000000000001",
        model_profile_id="deterministic-v1",
        dialogue_policy_id="default-dialogue",
        skill_id="review-data-spec",
        skill_package_sha256="dda6f8e1dbbabb94132ee4530e0f592ec3164347a567999d97a6f613a3ea78e5",
    )


@pytest.fixture
def client_platform():  # type: ignore[no-untyped-def]
    root = Path(__file__).parents[2]
    platform = ReviewPlatform(TrustedFixtureReviewExecutor(root))
    document = platform.upload(
        platform.workspace_id,
        "synthetic-spec.md",
        "text/markdown",
        (root / "tests/fixtures/synthetic-review/synthetic-spec.md").read_bytes(),
    )
    profile = platform.system_profile
    run = platform.create_run(
        platform.workspace_id,
        {
            "document_id": document["id"],
            "context_document_ids": [],
            "profile": {"id": profile.id, "version": profile.version},
            "model_profile": {"id": "deterministic-v1", "version": "1.0.0"},
            "locale": "en-US",
        },
        "cancellation-test",
    )
    return platform, run["id"]
