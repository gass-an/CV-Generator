# Service de génération

Backend de génération asynchrone du projet HackAVP. Les demandes de documents
sont enregistrées comme jobs persistants dans PostgreSQL, puis traitées par un
worker séparé de l'API.

Le worker génère un CV, une lettre de motivation ou un guide de préparation à
l'entretien au format AsciiDoc, adapté à un numéro d'AVP exact. Il résout la
fiche dans le sitemap de données ouvertes officiel de l'OPT, récupère son
Markdown, puis envoie ce contexte et le JSON Resume à une API llama.cpp
compatible OpenAI.

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
cp deploy/.env.example deploy/.env.local
```

Le fichier réel contient les sections de configuration locale et les secrets
administrateur. Il ne doit jamais être commité. Renseignez `LLM_BASE_URL` avec
l'URL réellement vérifiée du serveur Windows accessible via Tailscale ;
`host.docker.internal` ne représente pas cette machine distante.

## Démarrage local

Depuis la racine, l'ensemble local peut être lancé avec rechargement automatique :

```bash
docker compose --env-file deploy/.env.local -f deploy/docker-compose.local.yml up --build
```

Le worker facultatif est activé avec le profil `generation` :

```bash
docker compose --env-file deploy/.env.local -f deploy/docker-compose.local.yml --profile generation up --build
```

PostgreSQL, les migrations, l'API et l'administration tournent alors dans
Docker. Les sources Python sont montées dans les conteneurs de développement.

L'API est disponible sur `http://127.0.0.1:8000` et son contrôle de santé sur
`GET /api/v1/health`.

Redoc :
http://127.0.0.1:8000/docs

OpenAPI JSON :
http://127.0.0.1:8000/openapi.json

Endpoints de génération disponibles :

- `POST /api/v1/documents/cv`
- `POST /api/v1/documents/cover-letter`
- `POST /api/v1/documents/interview-prep`
- `GET /api/v1/documents`
- `GET /api/v1/documents/{id}/status`
- `GET /api/v1/documents/{id}`
- `GET /api/v1/documents/{id}/docx`
- `GET /api/v1/documents/{id}/pdf`
- `GET /api/v1/documents/{id}/adoc`
- `GET /api/v1/documents/{id}/md`

Toutes ces routes documentaires exigent l'en-tête `X-API-Key`. Redoc et le
schéma OpenAPI restent publics ; Redoc décrit ce mécanisme d'authentification,
mais n'exécute pas les requêtes métier. Une clé absente ou invalide produit
`401 Unauthorized`. Un document inexistant,
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
  http://127.0.0.1:8000/api/v1/documents/<ID>/docx
```

Le fichier `.docx` est généré à la demande à partir de l'AsciiDoc stocké. Il
n'est pas persisté séparément en base de données.

### Historique des générations

L'historique est limité au client associé à la clé API. Deux clés valides du
même client voient donc les mêmes documents. La réponse contient une projection
non sensible (`id`, type, statut, AVP, nom du candidat et horodatages), sans le
JSON Resume ni le contenu AsciiDoc.

```bash
curl -sS \
  -H "X-API-Key: ${API_KEY}" \
  'http://127.0.0.1:8000/api/v1/documents?limit=20&offset=0' \
  | jq
```

Les filtres `document_type` (`cv`, `cover_letter`, `interview_prep`) et `status`
(`pending`, `processing`, `completed`, `failed`) sont optionnels :

```bash
curl -sS \
  -H "X-API-Key: ${API_KEY}" \
  'http://127.0.0.1:8000/api/v1/documents?document_type=cv&status=completed&limit=10' \
  | jq
```

La réponse contient `items`, `total`, `limit` et `offset`. Une pagination ou un
filtre invalide produit une réponse `422`.

### Prévisualisation PDF

Un document terminé peut être converti à la demande en PDF :

```bash
curl -sS \
  -H "X-API-Key: ${API_KEY}" \
  -H 'Accept: application/pdf' \
  -o document.pdf \
  http://127.0.0.1:8000/api/v1/documents/<ID>/pdf
```

La réponse utilise `Content-Type: application/pdf`, une disposition `inline` et
`Cache-Control: private, no-store`. Les erreurs d'accès restent `401` ou `404`,
un document indisponible produit `409`, et un échec de conversion produit `500`
avec un code métier stable.

La conversion réutilise le DOCX et LibreOffice Writer en mode headless. L'image
Docker backend installe LibreOffice et les polices DejaVu/Liberation. Les
paramètres `LIBREOFFICE_EXECUTABLE`, `PDF_CONVERSION_TIMEOUT_SECONDS` et
`PDF_CONVERSION_MAX_CONCURRENT` permettent de configurer respectivement le
binaire, le délai maximal et la limite de conversions simultanées.

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
                 -> prompt dédié -> llama.cpp -> document AsciiDoc
```

Le JSON Resume et le Markdown sont délimités séparément dans le prompt et
traités comme des données non fiables. Le modèle reçoit l'instruction de ne
jamais transformer une exigence de l'AVP en compétence du candidat.

Pour arrêter PostgreSQL :

```bash
docker compose --env-file deploy/.env.local -f deploy/docker-compose.local.yml down
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

Le test réel LibreOffice est optionnel sur la machine de développement :

```bash
RUN_LIBREOFFICE_INTEGRATION=1 pytest tests/test_pdf_conversion_service.py \
  -k real_libreoffice
```

Il nécessite le binaire `libreoffice`. Les autres tests PDF utilisent un
processus simulé et n'imposent aucune dépendance système à l'environnement de
test.

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
LLM_BASE_URL=<URL Tailscale vérifiée du serveur llama.cpp>
LLM_MODEL=nom-du-modele-charge
LLM_TIMEOUT_SECONDS=120
WORKER_POLL_INTERVAL_SECONDS=1
WORKER_STALE_JOB_TIMEOUT_SECONDS=600
LIBREOFFICE_EXECUTABLE=libreoffice
PDF_CONVERSION_TIMEOUT_SECONDS=60
PDF_CONVERSION_MAX_CONCURRENT=2
```

Dans l'environnement Docker local décrit plus haut, llama.cpp tourne sur une
autre machine : ne remplacez pas cette URL par `host.docker.internal` sans
avoir vérifié l'architecture réseau réelle.

L'intervalle de polling évite une boucle consommant inutilement le CPU. Le
timeout stale définit après combien de secondes un job `PROCESSING` est remis en
attente.

Le JSON Resume contient des données personnelles. Il n'est ni exposé par
l'endpoint de statut, ni destiné à être journalisé. Une politique de rétention
sera ajoutée dans une étape ultérieure.

## Test manuel de génération

Depuis la racine :

```bash
docker compose --env-file deploy/.env.local -f deploy/docker-compose.local.yml --profile generation up --build
```

Demander une génération via `POST /api/v1/documents/cv`,
`POST /api/v1/documents/cover-letter` ou
`POST /api/v1/documents/interview-prep` avec un JSON Resume fictif et, par
exemple, `"avp_number": "3134-26-1382/SR"`. Consulter ensuite
`GET /api/v1/documents/{id}/status`, puis `GET /api/v1/documents/{id}`. La
génération doit passer de `PENDING` à `PROCESSING`, puis `COMPLETED`, et
retourner un contenu `asciidoc`. Un AVP absent, une source OPT ou un LLM
inaccessible, ou une réponse LLM invalide termine la génération en `FAILED`
avec un code contrôlé.
