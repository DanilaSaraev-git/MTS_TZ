from __future__ import annotations

import os
from pathlib import Path

from review_core.application.platform import ReviewPlatform
from review_runtime.fakes.review_executor import TrustedFixtureReviewExecutor
from review_runtime.postgres.durable import DurableReviewPlatform


def build_platform(composition: str = "fixture") -> ReviewPlatform:
    root = Path(__file__).resolve().parents[4]
    executor = TrustedFixtureReviewExecutor(root)
    if composition == "durable" or os.environ.get("REVIEW_COMPOSITION") == "durable":
        return DurableReviewPlatform(
            executor,
            database_url=os.environ["REVIEW_DATABASE_URL"],
            artifact_root=Path(os.environ["REVIEW_ARTIFACT_ROOT"]),
        )
    return ReviewPlatform(executor)
