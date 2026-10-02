FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Package commun
COPY shared/pyproject.toml shared/README.md /opt/shared/
COPY shared/src /opt/shared/src

RUN python -m pip install --no-cache-dir /opt/shared

# Administration
COPY generator-admin-service/pyproject.toml \
     generator-admin-service/README.md /opt/admin/
COPY generator-admin-service/app /opt/admin/app

RUN python -m pip install --no-cache-dir /opt/admin

# Exécution sans privilèges root
RUN groupadd --system generator \
    && useradd --system --gid generator --uid 10001 generator

USER generator

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
