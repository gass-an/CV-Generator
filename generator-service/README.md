# Generator Service

Backend de génération asynchrone du projet HackAVP. Les demandes de documents
sont enregistrées comme jobs persistants dans PostgreSQL, puis traitées par un
worker séparé de l'API.

Le processor actuel génère uniquement un placeholder AsciiDoc. Il sera remplacé
par la récupération réelle de l'AVP, les prompts et l'appel à llama.cpp.

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

Dans un autre terminal, avec le même venv activé :

```bash
python -m app.workers.document_worker
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

## Worker

Le worker réserve le plus ancien job `PENDING` avec
`FOR UPDATE SKIP LOCKED`. La réservation et le passage à `PROCESSING` sont
commités immédiatement. Le traitement du document s'effectue ensuite sans
transaction ni session SQLAlchemy ouverte, puis une nouvelle transaction courte
enregistre `COMPLETED` ou `FAILED`.

Ce découpage permet de lancer plusieurs workers concurrents sans qu'ils
réservent le même job :

```text
PENDING -> PROCESSING -> COMPLETED
                      -> FAILED
```

Au démarrage puis périodiquement, le worker remet à `PENDING` les jobs restés
`PROCESSING` au-delà de `WORKER_STALE_JOB_TIMEOUT_SECONDS`. Leur `started_at` et
leurs éventuels résultats ou erreurs temporaires sont réinitialisés. Cette
stratégie volontairement simple permet de récupérer les jobs après le crash
d'un worker ; elle sera enrichie seulement si le projet nécessite une politique
de retry plus avancée.

Le worker accepte `SIGINT` et `SIGTERM` et termine proprement entre deux jobs.

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

Variables propres au worker :

```env
WORKER_POLL_INTERVAL_SECONDS=1
WORKER_STALE_JOB_TIMEOUT_SECONDS=600
```

L'intervalle de polling évite une boucle consommant inutilement le CPU. Le
timeout stale définit après combien de secondes un job `PROCESSING` est remis en
attente.

Le JSON Resume contient des données personnelles. Il n'est ni exposé par
l'endpoint de statut, ni destiné à être journalisé. Une politique de rétention
sera ajoutée dans une étape ultérieure.
