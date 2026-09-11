FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=5 \
    PIP_RESUME_RETRIES=5 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# Older pip in the base image cannot resume interrupted downloads, including its own upgrade.
RUN --mount=type=cache,target=/root/.cache/pip \
    for attempt in 1 2 3; do \
        python -m pip install --upgrade pip==26.2.1 && break; \
        if [ "$attempt" = 3 ]; then exit 1; fi; \
        sleep 3; \
    done

COPY requirements.lock ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install -r requirements.lock
COPY pyproject.toml ./
COPY app ./app
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --no-deps . \
    && useradd --create-home appuser
USER appuser
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
