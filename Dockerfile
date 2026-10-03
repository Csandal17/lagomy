# Lagomy demo API (demo_api.py). Keys come from the environment at run time:
# NEBIUS_API_KEY, NEBIUS_BASE_URL, TAVILY_API_KEY, optionally DEMO_DAILY_RUN_LIMIT.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.23 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    CREWAI_TELEMETRY_OPTOUT=true \
    OTEL_SDK_DISABLED=true

WORKDIR /app

# Dependencies first, so a code change does not reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

COPY demo_api.py demo_page.html guardrails.py check_citations.py ./

# The search tool appends to logs/; give the runtime user somewhere to write.
RUN useradd --create-home lagomy && mkdir logs && chown lagomy logs
USER lagomy

ENV PATH="/app/.venv/bin:$PATH" \
    PORT=8000
CMD ["sh", "-c", "exec uvicorn demo_api:app --host 0.0.0.0 --port \"$PORT\""]
