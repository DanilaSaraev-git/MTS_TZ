FROM ghcr.io/astral-sh/uv:0.12.9 AS uv
FROM python:3.14.7-slim
COPY --from=uv /uv /uvx /bin/
ENV UV_LINK_MODE=copy UV_NO_SYNC=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN addgroup --system review && adduser --system --ingroup review review
COPY pyproject.toml uv.lock uv.toml .python-version ./
COPY packages ./packages
COPY apps/api ./apps/api
COPY apps/worker ./apps/worker
COPY apps/cli ./apps/cli
COPY contracts ./contracts
COPY specs/003-backend-implementation/contracts ./specs/003-backend-implementation/contracts
COPY tests/fixtures ./tests/fixtures
COPY skills ./skills
RUN uv sync --locked --no-dev
RUN mkdir -p /var/lib/review && chown -R review:review /var/lib/review /app
USER review
ENV PATH=/app/.venv/bin:$PATH
