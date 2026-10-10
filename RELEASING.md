# Préparer et déployer la version v0.3.0

Le dépôt publie deux images pour chaque tag :

- `ghcr.io/gass-an/cv-generator:v0.3.0` pour l'API, le worker et Alembic ;
- `ghcr.io/gass-an/cv-generator-admin:v0.3.0` pour l'administration.

Le workflow ne déploie rien. La création du tag et la publication restent des
opérations manuelles à effectuer seulement après validation du diff.

## Préparer la release

Depuis la racine, sur une branche propre et à jour :

```bash
git status
python run_all_tests.py
docker build -f generator-service/Dockerfile -t cv-generator:v0.3.0 .
docker build -f generator-admin-service/Dockerfile -t cv-generator-admin:v0.3.0 .
```

Après revue et commit, les opérations manuelles de publication seront :

```bash
git tag -a v0.3.0 -m "Version 0.3.0"
git push origin master
git push origin v0.3.0
```

Elles ne doivent pas être exécutées pendant la préparation locale.

## Sauvegarde PostgreSQL sur la tour Windows

Avant une mise à jour, créer le dossier `backups` depuis PowerShell, puis faire
produire l'archive dans le conteneur et la copier sur l'hôte :

```powershell
New-Item -ItemType Directory -Force backups
docker compose --env-file .env -f docker-compose.prod.yml exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/cv-generator-before-v0.3.0.dump'
$postgresContainer = docker compose --env-file .env -f docker-compose.prod.yml ps -q postgres
docker cp "${postgresContainer}:/tmp/cv-generator-before-v0.3.0.dump" ".\backups\cv-generator-before-v0.3.0.dump"
```

Vérifier que le fichier existe et possède une taille non nulle. Cette procédure
est documentée seulement : elle ne doit pas être lancée depuis une autre machine
et aucune restauration ne doit être improvisée sans copie supplémentaire.

## Déploiement manuel sur la tour

Préconditions : Docker Desktop en fonctionnement, accès GHCR configuré, GPU
NVIDIA disponible et dépôt positionné sur le commit de la release. Ne remplacez
jamais `.env` par son exemple : modifiez seulement les valeurs nécessaires
dans le fichier réel déjà présent, notamment `APP_VERSION=v0.3.0`.

Si les secrets administrateur se trouvent encore dans un ancien fichier
séparé, les reporter manuellement dans la section Administration de
`.env`, sans les afficher dans le terminal ni écraser automatiquement le
fichier existant. Placer `ADMIN_PASSWORD_HASH` entre apostrophes simples pour
préserver les `$`; Docker Compose ne transmet pas ces apostrophes au conteneur.

Depuis la racine du dépôt :

```powershell
docker login ghcr.io
docker compose --env-file .env -f docker-compose.prod.yml config --quiet
docker compose --env-file .env -f docker-compose.prod.yml pull
docker compose --env-file .env -f docker-compose.prod.yml up -d
docker compose --env-file .env -f docker-compose.prod.yml ps
```

`generator-migrate` attend PostgreSQL et doit terminer avec succès avant le
démarrage de l'API, du worker et de l'administration. Contrôler son état et les
logs sans afficher le fichier d'environnement :

```powershell
docker compose --env-file .env -f docker-compose.prod.yml logs --tail=100 generator-migrate
docker compose --env-file .env -f docker-compose.prod.yml logs --tail=100 generator-api generator-worker generator-admin
```

Tester localement :

```powershell
curl.exe http://127.0.0.1:8000/api/v1/health
curl.exe -i http://127.0.0.1:8001/login
```

L'administration reste liée à `127.0.0.1:8001`. Une future configuration
Tailscale Serve devra relayer cette adresse en HTTPS sans modifier les services
Docker, avec `ADMIN_BASE_URL` réglée sur l'URL HTTPS privée. Ne modifiez pas la
configuration Tailscale existante pendant le déploiement Docker.
llama.cpp reste temporairement lié à `127.0.0.1:8080` afin de préserver cette
configuration Tailscale Serve existante ; ne la réinitialisez pas pendant la
mise à jour.

## Retour arrière applicatif

Un retour arrière consiste à remettre l'ancienne valeur explicite de
`APP_VERSION`, puis à exécuter `pull` et `up -d`. Attention : les migrations de
base ne sont pas automatiquement annulées. Ne lancez jamais de downgrade
Alembic sur la production sans procédure dédiée et sauvegarde vérifiée.

Les commandes de déploiement ci-dessus préservent les volumes
`cv-generator_postgres-data` et `cv-generator-models`. Ne lancez jamais
`docker compose down -v`, `docker volume prune` ou une recréation manuelle de
ces volumes.
