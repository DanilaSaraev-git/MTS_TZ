from __future__ import annotations

import os
from pathlib import Path

import psycopg
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
def ready(request: Request):  # type: ignore[no-untyped-def]
    if not hasattr(request.app.state.platform, "database_url"):
        return {"status": "ready", "composition": "fixture"}
    checks: dict[str, bool] = {}
    try:
        with psycopg.connect(request.app.state.platform.database_url, connect_timeout=2) as connection:
            checks["database"] = connection.execute("SELECT 1").fetchone() == (1,)
            checks["business_schema"] = connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone() == ("20260905_0001",)
            checks["runtime_state"] = connection.execute("SELECT count(*) FROM runtime_state").fetchone() == (
                1,
            )
            checks["queue_schema"] = connection.execute(
                "SELECT to_regclass('public.procrastinate_jobs') IS NOT NULL"
            ).fetchone() == (True,)
        artifact_root = Path(os.environ["REVIEW_ARTIFACT_ROOT"])
        checks["artifact_store"] = artifact_root.is_dir() and os.access(artifact_root, os.W_OK)
    except Exception:
        checks["database"] = False
    if not all(checks.values()):
        return JSONResponse(status_code=503, content={"status": "not_ready", "checks": checks})
    return {"status": "ready", "composition": "durable", "checks": checks}
