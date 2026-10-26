# Docker Compose

Les deux configurations Docker du projet sont centralisées ici :

- `docker-compose.local.yml` pour le développement ;
- `docker-compose.prod.yml` pour le déploiement manuel.

Toutes les commandes ci-dessous sont exécutées depuis la racine du dépôt. La
configuration Docker canonique est `deploy/.env`, ignorée par Git ;
`deploy/.env.example` est le seul modèle versionné. Ne remplacez jamais un
fichier réel déjà renseigné par le modèle.

## Développement local

Créer la configuration locale sans y placer de secret réel destiné à la
production :

```bash
cp deploy/.env.example deploy/.env
python generator-admin-service/scripts/generate_password_hash.py
```

Renseigner `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH` et un
`ADMIN_SESSION_SECRET` aléatoire dans `deploy/.env`. Placer le hash
Argon2id entre apostrophes simples, par exemple
`ADMIN_PASSWORD_HASH='$argon2id$...'` : Docker Compose retire les apostrophes
et transmet littéralement les caractères `$`.

`LLM_BASE_URL` doit contenir l'URL réellement vérifiée du serveur llama.cpp de
la tour Windows via Tailscale. `host.docker.internal` désigne l'hôte Linux des
conteneurs locaux, pas cette machine distante. Ne devinez ni son adresse ni
son port : contrôlez d'abord la configuration Tailscale existante.

Lancer PostgreSQL, les migrations, l'API et l'administration :

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.local.yml up --build
```

Les sources du backend, de l'administration et du package partagé sont montées
dans les conteneurs. Uvicorn recharge les deux applications après modification.
PostgreSQL écoute uniquement sur `127.0.0.1:5432`, l'API sur `127.0.0.1:8000`
et l'administration sur `127.0.0.1:8001`. Le frontend Nginx écoute sur le port
loopback `WEB_PORT` (8082 par défaut) et relaie `/api/v1` vers l'API. Pour
travailler uniquement sur React, `npm run dev` reste le parcours le plus rapide
et utilise `DEV_API_PROXY_TARGET`.

Le worker est facultatif :

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.local.yml --profile generation up --build
```

Il contacte llama.cpp à l'adresse explicitement définie par `LLM_BASE_URL`.
Arrêter les conteneurs locaux sans supprimer leur volume :

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.local.yml down
```

## Production

Le Compose de production contient PostgreSQL 18, llama.cpp Router, les migrations,
l'API, le worker, l'administration et le frontend. L'API et l'administration sont publiées
respectivement sur `127.0.0.1:8000` et `127.0.0.1:8001`. Le Router llama.cpp
n'est plus publié sur l'hôte : seuls le worker et l'administration peuvent le
joindre sur le réseau Docker à `http://llm:8080`. PostgreSQL et le worker ne
publient aucun port hôte.

Le Router utilise l'image CUDA `b11889` épinglée par digest, démarre sans
`-hf`, conserve `LLAMA_CACHE=/models` sur le volume existant
`cv-generator-models`, et applique `--models-max 1`, `--ctx-size 8192` et
`--n-gpu-layers 99` aux instances dynamiques. `LLM_MODEL` sert uniquement à
initialiser PostgreSQL au premier passage de la migration ; les changements
suivants sont réalisés dans « Modèles LLM » et ne nécessitent aucun redémarrage.
En production, le worker et l'administration reçoivent explicitement
`http://llm:8080` : une ancienne valeur `LLM_BASE_URL` encore présente dans le
`.env` ne peut pas les détourner du Router interne. Le Compose local conserve
au contraire sa valeur configurable pour l'accès Tailscale de développement.

Le frontend `ghcr.io/gass-an/cv-generator-web:${APP_VERSION}` est publié
uniquement sur `127.0.0.1:${WEB_PORT:-8082}`. Les trois images applicatives
emploient la même valeur `APP_VERSION`.

Créer une fois la configuration locale de la tour :

```bash
cp deploy/.env.example deploy/.env
```

Renseigner toutes les sections dans `deploy/.env` et conserver `APP_VERSION`
sur une version explicite.
`ADMIN_BASE_URL` doit être l'URL HTTPS qui sera présentée par le proxy privé et
`ADMIN_COOKIE_SECURE` doit rester à `true`. Entourer le hash Argon2id
d'apostrophes simples afin de préserver ses `$`; ces apostrophes ne sont pas
transmises à l'application.

Après une installation utilisant les anciens fichiers séparés, ouvrir
manuellement l'ancien fichier administrateur localement et reporter ses
valeurs dans la section « Administration » du fichier général correspondant.
Ne jamais afficher ces secrets dans le terminal, les recopier dans un modèle
`.example`, ni remplacer automatiquement le fichier général. Supprimer
l'ancien fichier secret n'est qu'une opération manuelle facultative, après
vérification de la nouvelle configuration.

Les volumes de production existants sont volontairement nommés :

- `cv-generator_postgres-data` pour PostgreSQL ;
- `cv-generator-models` pour le modèle llama.cpp.

Ne changez ni ces noms, ni `name: cv-generator` en tête du Compose. N'utilisez
jamais `docker compose down -v` ou `docker volume prune` sur la tour.

Avant le premier déploiement Router, vérifier manuellement `tailscale serve
status`. Aucune route ne doit cibler l'ancien port `127.0.0.1:8080` : les
endpoints `/models` pilotent désormais des téléchargements et des chargements
GPU sans authentification propre. Ne publiez pas ce port avec Tailscale Serve,
Funnel, un autre reverse proxy ou une règle de pare-feu. L'administration HTTPS
sur `127.0.0.1:8001` est le seul point d'entrée autorisé pour ces opérations.

## Premier déploiement du Router

1. Sauvegarder PostgreSQL et relever les noms des volumes sans les recréer.
2. Contrôler `tailscale serve status` et retirer manuellement toute route vers
   `127.0.0.1:8080` avant le démarrage du nouveau Router.
3. Vérifier que Docker Desktop/WSL2 voit toujours la RTX avec
   `docker run --rm --gpus all nvidia/cuda:12.8.1-base-ubuntu24.04 nvidia-smi`.
4. Récupérer les nouvelles images applicatives et l'image llama.cpp épinglée.
5. Exécuter `generator-migrate` (ou `alembic upgrade head`) avant les services.
6. Vérifier que `cv-generator-models` est toujours monté sur `/models` et que
   `GET /models` voit le cache existant depuis le réseau Docker.
7. Ouvrir l'administration et confirmer que
   `ggml-org/Qwen3-14B-GGUF:Q4_K_M` est sélectionné et utilisable.
8. Télécharger puis activer un petit modèle de test depuis l'administration.
9. Générer un document et contrôler le modèle et la durée dans « Activité ».

En retour arrière applicatif, remettre les images applicatives précédentes en
conservant PostgreSQL et les volumes. La migration ajoutée est additive ; ne
pas lancer automatiquement de `alembic downgrade`. L'ancien worker ignore les
nouvelles colonnes, mais l'ancien service llama.cpp nécessitera à nouveau son
argument `-hf` : documenter cette modification Compose séparément et ne jamais
supprimer le cache.

La procédure de sauvegarde et de déploiement Windows est détaillée dans
[`RELEASING.md`](../RELEASING.md).

## Préparation HTTPS avec Tailscale

L'administration écoute sur `127.0.0.1:8001`, prête à être placée derrière un
proxy HTTPS local comme Tailscale Serve. Cette configuration ne modifie pas
Tailscale. Avant toute future publication privée, conserver la configuration
Tailscale existante, choisir son URL HTTPS comme `ADMIN_BASE_URL`, puis vérifier
explicitement l'adresse source du proxy avant de l'ajouter à
`ADMIN_TRUSTED_PROXY_IPS`. Une liste vide est le réglage sûr par défaut.

Le frontend est prêt à être relayé depuis son port loopback sans modifier le
bundle ni exposer directement l'API. Sur Windows PowerShell, commencer par :

```powershell
Get-NetTCPConnection -LocalPort 8082 -ErrorAction SilentlyContinue
docker ps --format "table {{.Names}}\t{{.Ports}}"
docker compose --env-file .env -f docker-compose.prod.yml ps
curl.exe -I http://127.0.0.1:8082/
curl.exe http://127.0.0.1:8082/api/v1/health
tailscale serve status
```

Si 8082 est occupé, modifier seulement `WEB_PORT` dans `deploy/.env`, puis
recréer `generator-web` sans reconstruire l'image. Examiner les routes
existantes, choisir un point d'entrée HTTPS libre et ajouter manuellement un
proxy vers `http://127.0.0.1:$WEB_PORT` avec la syntaxe de la version Tailscale
installée. Ne jamais exécuter `tailscale serve reset`. Tester ensuite `/`,
`/historique`, `/parametres` et `/api/v1/health` depuis une autre machine du
tailnet.

Tailscale Serve reste privé aux appareils autorisés du tailnet. Funnel publie
sur Internet et ne doit pas être activé sans décision explicite. Ni le port
HTTPS 443 de Tailscale ni le port Docker 8082 ne sont présumés disponibles.

## Matrice de validation CI

| Changement | Jobs applicatifs |
|---|---|
| Frontend seul | Frontend |
| Backend seul | Backend |
| Administration seule | Administration |
| `shared/` | Shared, backend, administration |
| Migration Alembic | Backend, administration |
| Backend et frontend | Backend, frontend |
| Configuration Nginx seule | Docker/Nginx |
| `.gitignore` racine | Vérification légère des exclusions |
| Compose, Dockerfile ou `.dockerignore` | Toutes les suites et Docker |
| Documentation seule, y compris dans un service | Agrégateur uniquement |
| Workflow GitHub | Toutes les suites et Docker |
| Lancement manuel | Toutes les suites et Docker |
| Tag `vX.Y.Z` | Release complète et trois images |

Le job Docker valide les deux Compose avec des valeurs factices, construit les
trois images et exécute le même smoke test que la release. Celui-ci vérifie le
fallback SPA, le chemin transmis au backend simulé, l'en-tête `X-API-Key` et la
conservation des réponses API `401` et `404`.
