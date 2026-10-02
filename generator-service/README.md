# Service de génération

Backend de génération asynchrone du projet HackAVP. Les demandes de documents
sont enregistrées comme jobs persistants dans PostgreSQL, puis traitées par un
worker séparé de l'API.

Le worker génère un CV ou une lettre de motivation AsciiDoc adapté à un numéro
d'AVP exact. Il résout la fiche dans le sitemap de données ouvertes officiel de
l'OPT, récupère son Markdown, puis envoie ce contexte et le JSON Resume à une
API llama.cpp compatible OpenAI.

## Prérequis

- Python 3.12
- Docker avec Docker Compose

## Installation

```bash
cd CV-Generator
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e shared -e 'generator-service[dev]'
cp generator-service/.env.example generator-service/.env
```

Le fichier `.env.example` contient des valeurs locales de développement. Ne
jamais committer de secret réel dans `.env`.

## Démarrage local

Depuis `generator-service/`, après avoir activé le venv et installé les
dépendances :

```bash
docker compose --env-file .env -f docker/docker-compose.dev.yml up -d
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

L'API est disponible sur `http://127.0.0.1:8000` et son contrôle de santé sur
`GET /api/v1/health`.

Swagger UI :
http://127.0.0.1:8000/docs

OpenAPI JSON :
http://127.0.0.1:8000/openapi.json

Endpoints de génération disponibles :

- `POST /api/v1/documents/cv`
- `POST /api/v1/documents/cover-letter`
- `GET /api/v1/documents/{id}/status`
- `GET /api/v1/documents/{id}`
- `GET /api/v1/documents/{id}/download`

Toutes ces routes documentaires exigent l'en-tête `X-API-Key`. Swagger reste
public et son bouton **Authorize** permet de renseigner cette clé. Une clé
absente ou invalide produit `401 Unauthorized`. Un document inexistant,
appartenant à un autre client ou créé avant l'introduction de la propriété
produit `404 Not Found`, sans révéler son existence ni son contenu.

Les documents appartiennent au client d'API et non à une clé particulière. Une
nouvelle clé valide du même client conserve donc l'accès à ses anciens
documents. Les documents historiques sont conservés en base avec
`client_id = NULL`, mais ne sont accessibles à aucun étudiant via l'API
publique. Les clés seront distribuées par le service d'administration prévu
pour la PR 3 ; aucune route publique de gestion des clés n'est exposée ici.

Une fois la génération terminée, le document peut être téléchargé au format DOCX :

```bash
curl -OJ \
  -H "X-API-Key: ${API_KEY}" \
  http://127.0.0.1:8000/api/v1/documents/<ID>/download
```

Le fichier `.docx` est généré à la demande à partir de l'AsciiDoc stocké. Il
n'est pas persisté séparément en base de données.

Des commandes complètes utilisant des données fictives sont disponibles dans
[`demo/curl-examples.md`](demo/curl-examples.md).

## Worker de génération

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
Ses deux clients HTTP asynchrones sont créés une seule fois au démarrage et
fermés lors de l'arrêt, avant la fermeture du moteur SQLAlchemy.

Chaîne de génération :

```text
numéro AVP exact -> sitemap OPT -> fiche Markdown officielle
                 -> prompt dédié -> llama.cpp -> CV ou lettre AsciiDoc
```

Le JSON Resume et le Markdown sont délimités séparément dans le prompt et
traités comme des données non fiables. Le modèle reçoit l'instruction de ne
jamais transformer une exigence de l'AVP en compétence du candidat.

Pour arrêter PostgreSQL :

```bash
docker compose --env-file .env -f docker/docker-compose.dev.yml down
```

Pour arrêter PostgreSQL **et supprimer définitivement les données locales** :

```bash
docker compose --env-file .env -f docker/docker-compose.dev.yml down -v
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

Configuration locale attendue :

```env
DATABASE_URL=postgresql+asyncpg://cv_generator:cv_generator@localhost:5432/cv_generator
OPT_AVP_BASE_URL=https://opt-nc.github.io/odata-avps
LLM_BASE_URL=http://127.0.0.1:8080
LLM_MODEL=nom-du-modele-charge
LLM_TIMEOUT_SECONDS=120
WORKER_POLL_INTERVAL_SECONDS=1
WORKER_STALE_JOB_TIMEOUT_SECONDS=600
```

L'intervalle de polling évite une boucle consommant inutilement le CPU. Le
timeout stale définit après combien de secondes un job `PROCESSING` est remis en
attente.

Le JSON Resume contient des données personnelles. Il n'est ni exposé par
l'endpoint de statut, ni destiné à être journalisé. Une politique de rétention
sera ajoutée dans une étape ultérieure.

## Test manuel de génération

Terminal 1 :

```bash
cd generator-service
docker compose --env-file .env -f docker/docker-compose.dev.yml up -d
alembic upgrade head
uvicorn app.main:app --reload
```

Terminal 2 :

```bash
cd generator-service
python -m app.workers.document_worker
```

Demander une génération via `POST /api/v1/documents/cv` ou
`POST /api/v1/documents/cover-letter` avec un JSON Resume fictif et, par
exemple, `"avp_number": "3134-26-1382/SR"`. Consulter ensuite
`GET /api/v1/documents/{id}/status`, puis `GET /api/v1/documents/{id}`. La
génération doit passer de `PENDING` à `PROCESSING`, puis `COMPLETED`, et
retourner un contenu `asciidoc`. Un AVP absent, une source OPT ou un LLM
inaccessible, ou une réponse LLM invalide termine la génération en `FAILED`
avec un code contrôlé.
