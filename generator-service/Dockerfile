FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system generator \
    && useradd --system --gid generator --uid 10001 generator

COPY pyproject.toml README.md ./
COPY app ./app

RUN python -m pip install --no-cache-dir .

COPY alembic.ini ./
COPY alembic ./alembic

USER generator

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
