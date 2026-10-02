FROM python:3.12-slim

# Évite la création de fichiers .pyc et force l'affichage immédiat des logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Exécute l'application avec un utilisateur non privilégié.
RUN groupadd --system generator \
    && useradd --system --gid generator --uid 10001 generator

# Le contexte de build est la racine afin d'inclure le package partagé.
COPY shared/pyproject.toml shared/README.md ./shared/
COPY shared/src ./shared/src
RUN python -m pip install --no-cache-dir ./shared

COPY generator-service/pyproject.toml generator-service/README.md ./generator-service/
COPY generator-service/app ./generator-service/app

# Installe le service et ses dépendances Python.
RUN python -m pip install --no-cache-dir ./generator-service

# Ajoute la configuration et les migrations Alembic utilisées au démarrage.
COPY generator-service/alembic.ini ./
COPY generator-service/alembic ./alembic

USER generator

# Port HTTP exposé par l'API FastAPI.
EXPOSE 8000

# Commande par défaut de l'image ; le worker et les migrations la remplacent
# dans Docker Compose lorsqu'ils utilisent cette même image.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
