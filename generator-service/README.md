# Generator Service

Backend de génération asynchrone du projet HackAVP. Les demandes de documents
sont enregistrées comme jobs persistants dans PostgreSQL, puis seront traitées
ultérieurement par un worker séparé.

Cette étape fournit l'API de création et de consultation des jobs. Elle ne
branche pas encore l'API AVP, llama.cpp, ni le worker de génération.

## Prérequis

- Python 3.12
- Docker avec Docker Compose

## Installation

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
cp .env.example .env
```

Le fichier `.env.example` contient des valeurs locales de développement. Ne
jamais committer de secret réel dans `.env`.

## Workflow local

Depuis `generator-service/`, après avoir activé le venv et installé les
dépendances :

```bash
cd docker
docker compose up -d
cd ..
alembic upgrade head
uvicorn app.main:app --reload
```

En développement, seul PostgreSQL tourne dans Docker. FastAPI s'exécute
directement depuis le venv et se connecte à PostgreSQL sur `localhost:5432` via
`DATABASE_URL`.

L'API est disponible sur `http://127.0.0.1:8000`, sa documentation OpenAPI sur
`/docs`, et son contrôle de santé sur `GET /api/v1/health`.

Endpoints de jobs disponibles :

- `POST /api/v1/documents/cv`
- `GET /api/v1/documents/{id}/status`
- `GET /api/v1/documents/{id}`

Pour arrêter PostgreSQL :

```bash
cd docker
docker compose down
```

Pour arrêter PostgreSQL **et supprimer définitivement les données locales** :

```bash
cd docker
docker compose down -v
```

## Migrations

La configuration Alembic utilise la même variable `DATABASE_URL` que
l'application, y compris avec le driver async `asyncpg`.

```bash
alembic upgrade head
alembic current
alembic history
```

## Qualité et tests

```bash
ruff format --check .
ruff check .
pytest
```

Pour appliquer automatiquement le formatage :

```bash
ruff format .
```

## Configuration

La configuration est lue depuis les variables d'environnement et, en local,
depuis un éventuel fichier `.env`. La différence entre développement et
production est exclusivement portée par ces variables, notamment
`DATABASE_URL`.

Le JSON Resume contient des données personnelles. Il n'est ni exposé par
l'endpoint de statut, ni destiné à être journalisé. Une politique de rétention
sera ajoutée dans une étape ultérieure.
