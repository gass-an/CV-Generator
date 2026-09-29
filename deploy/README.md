# Déploiement Docker manuel

Cette configuration déploie sur la machine de production :

- PostgreSQL, avec un volume persistant et sans port publié ;
- llama.cpp avec le GPU NVIDIA et un cache de modèle persistant ;
- une migration Alembic one-shot ;
- l'API FastAPI, publiée uniquement sur `127.0.0.1:8000` ;
- le worker de génération, sans port publié.

L'API, le worker et les migrations utilisent la même image versionnée :
`ghcr.io/gass-an/cv-generator:${APP_VERSION}`.

## Configuration

Depuis la racine du dépôt, créer le fichier local de production :

```bash
cp deploy/.env.example deploy/.env
```

Renseigner dans `deploy/.env` une version publiée explicite, les identifiants
PostgreSQL et les autres paramètres. Ce fichier contient des secrets et ne doit
jamais être commité. Le backend contacte llama.cpp sur le réseau Docker via
`http://llm:8080`.

## Déployer ou mettre à jour

Il n'existe volontairement aucun déploiement automatique. Après publication
d'une version, exécuter manuellement :

```bash
docker compose \
  --env-file deploy/.env \
  -f deploy/docker-compose.prod.yml \
  pull

docker compose \
  --env-file deploy/.env \
  -f deploy/docker-compose.prod.yml \
  up -d
```

Le service `generator-migrate` attend PostgreSQL, applique les migrations puis
se termine. L'API et le worker ne démarrent qu'après sa réussite.

## Vérifier les services

```bash
docker compose \
  --env-file deploy/.env \
  -f deploy/docker-compose.prod.yml \
  ps
```

L'API est accessible localement sur `http://127.0.0.1:8000`. Le serveur LLM
reste accessible localement sur `http://127.0.0.1:8080`.

Pour suivre les logs de tous les services :

```bash
docker compose \
  --env-file deploy/.env \
  -f deploy/docker-compose.prod.yml \
  logs -f --tail=100
```

Pour cibler un service, ajouter par exemple `generator-api`, `generator-worker`
ou `llm` à la fin de cette commande.

## Arrêter les services

```bash
docker compose \
  --env-file deploy/.env \
  -f deploy/docker-compose.prod.yml \
  down
```

Cette commande conserve les volumes PostgreSQL et llama.cpp. Ne pas ajouter
`--volumes` sauf si leur suppression définitive est explicitement souhaitée.

## Versions et rollback

La procédure complète de publication, de déploiement et de rollback est la
source de vérité dans [`RELEASING.md`](../RELEASING.md). Le déploiement utilise
toujours `APP_VERSION` plutôt que `latest` afin de permettre un retour manuel à
une image connue.

## Particularités de la tour Windows

Docker Desktop doit disposer de l'accès au GPU NVIDIA requis par l'image
llama.cpp. Lorsque le serveur n'est plus utilisé, Docker Desktop peut être
quitté puis WSL arrêté depuis PowerShell :

```powershell
wsl --shutdown
```
