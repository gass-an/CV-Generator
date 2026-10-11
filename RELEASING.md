# Publier et déployer une version

Un tag manuel `vX.Y.Z` déclenche une validation complète puis publie trois
images portant exactement ce tag :

- `ghcr.io/gass-an/cv-generator:vX.Y.Z` ;
- `ghcr.io/gass-an/cv-generator-admin:vX.Y.Z` ;
- `ghcr.io/gass-an/cv-generator-web:vX.Y.Z`.

Le workflow ne déploie rien sur la tour. `GITHUB_TOKEN` doit disposer de
`contents: write` pour la release GitHub et de `packages: write` pour GHCR. Les
pull requests ne publient jamais d'image.

## Préparer la release

Depuis une branche propre et à jour :

```bash
python run_all_tests.py
cd generatorweb-service
npm ci
npm run typecheck
npm run lint
npm run format:check
npm run test:ci
npm run build
cd ..
docker build -f generator-service/Dockerfile -t cv-generator:check .
docker build -f generator-admin-service/Dockerfile -t cv-generator-admin:check .
docker build -f generatorweb-service/Dockerfile -t cv-generator-web:check .
```

Après revue et commit, créer et pousser explicitement le tag :

```bash
git tag -a vX.Y.Z -m "Version X.Y.Z"
git push origin master
git push origin vX.Y.Z
```

Vérifier dans GitHub Actions que les suites Shared, backend, administration et
frontend ont réussi, puis que les trois paquets GHCR possèdent le même tag.

## Sauvegarder PostgreSQL sur la tour Windows

Depuis `deploy/` dans PowerShell, créer une sauvegarde avant toute mise à jour :

```powershell
New-Item -ItemType Directory -Force backups
docker compose --env-file .env -f docker-compose.prod.yml exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/cv-generator-before-update.dump'
$postgresContainer = docker compose --env-file .env -f docker-compose.prod.yml ps -q postgres
docker cp "${postgresContainer}:/tmp/cv-generator-before-update.dump" ".\backups\cv-generator-before-update.dump"
Get-Item ".\backups\cv-generator-before-update.dump"
```

Ne jamais remplacer le véritable `deploy/.env` par `.env.example`, afficher ses
secrets, ni utiliser `docker compose down -v` ou `docker volume prune`.

## Déployer manuellement

Vérifier d'abord que `WEB_PORT` est libre ; 8082 n'est qu'une valeur par défaut :

```powershell
Get-NetTCPConnection -LocalPort 8082 -ErrorAction SilentlyContinue
docker ps --format "table {{.Names}}\t{{.Ports}}"
```

Modifier manuellement `APP_VERSION=vX.Y.Z` dans `deploy/.env`, sans toucher aux
secrets, puis :

```powershell
docker login ghcr.io
docker compose --env-file .env -f docker-compose.prod.yml config --quiet
docker compose --env-file .env -f docker-compose.prod.yml pull
docker compose --env-file .env -f docker-compose.prod.yml up -d
docker compose --env-file .env -f docker-compose.prod.yml ps
docker compose --env-file .env -f docker-compose.prod.yml logs --tail=100 generator-migrate
docker compose --env-file .env -f docker-compose.prod.yml logs --tail=100 generator-api generator-worker generator-admin generator-web
```

`generator-migrate` doit terminer avec succès. Les volumes nommés
`cv-generator_postgres-data` et `cv-generator-models` doivent être conservés.

Tester ensuite le chemin public unique du frontend :

```powershell
curl.exe -I http://127.0.0.1:8082/
curl.exe -I http://127.0.0.1:8082/historique
curl.exe -I http://127.0.0.1:8082/parametres
curl.exe http://127.0.0.1:8082/api/v1/health
```

## Tailscale Serve

Cette procédure ne configure pas Tailscale automatiquement. Examiner les routes
existantes avant tout changement :

```powershell
tailscale serve status
```

Choisir un point d'entrée HTTPS libre et configurer manuellement Tailscale
Serve vers `http://127.0.0.1:$WEB_PORT` avec la syntaxe de la version installée.
Ne pas exécuter `tailscale serve reset` et ne pas supposer que 443 est libre.
Vérifier depuis une autre machine du tailnet le frontend et
`/api/v1/health`. Serve est privé ; Funnel rendrait le service public et ne doit
pas être activé sans demande explicite.

## Checklist fonctionnelle réelle

Ces contrôles doivent être effectués sur la tour et consignés ; la CI ne les
remplace pas :

- importer un JSON Resume et saisir un numéro AVP ;
- générer un CV et observer `pending`, `processing`, puis `completed` ;
- prévisualiser le PDF et télécharger DOCX et PDF ;
- actualiser l'application et retrouver le document dans l'historique ;
- reprendre un job en cours ;
- vérifier deux clés d'un même client puis l'isolation de deux clients ;
- vérifier les messages lorsque FastAPI ou llama.cpp est indisponible.

## Retour arrière applicatif

Remettre l'ancienne valeur explicite de `APP_VERSION`, puis exécuter `pull` et
`up -d`. Ce retour arrière ne rétrograde pas la base. Ne lancer aucun downgrade
Alembic automatique ; une incompatibilité de migration exige une procédure
dédiée et une sauvegarde vérifiée.
