# Docker Compose

Les deux configurations Docker du projet sont centralisées ici :

- `docker-compose.local.yml` pour le développement ;
- `docker-compose.prod.yml` pour le déploiement manuel.

Toutes les commandes ci-dessous sont exécutées depuis la racine du dépôt.
Chaque environnement utilise un seul fichier réel, ignoré par Git :
`deploy/.env.local` en développement et `deploy/.env` en production. Seuls
leurs modèles `.example` sont versionnés.

## Développement local

Créer la configuration locale sans y placer de secret réel destiné à la
production :

```bash
cp deploy/.env.local.example deploy/.env.local
python generator-admin-service/scripts/generate_password_hash.py
```

Renseigner `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH` et un
`ADMIN_SESSION_SECRET` aléatoire dans `deploy/.env.local`. Placer le hash
Argon2id entre apostrophes simples, par exemple
`ADMIN_PASSWORD_HASH='$argon2id$...'` : Docker Compose retire les apostrophes
et transmet littéralement les caractères `$`.

`LLM_BASE_URL` doit contenir l'URL réellement vérifiée du serveur llama.cpp de
la tour Windows via Tailscale. `host.docker.internal` désigne l'hôte Linux des
conteneurs locaux, pas cette machine distante. Ne devinez ni son adresse ni
son port : contrôlez d'abord la configuration Tailscale existante.

Lancer PostgreSQL, les migrations, l'API et l'administration :

```bash
docker compose --env-file deploy/.env.local -f deploy/docker-compose.local.yml up --build
```

Les sources du backend, de l'administration et du package partagé sont montées
dans les conteneurs. Uvicorn recharge les deux applications après modification.
PostgreSQL écoute uniquement sur `127.0.0.1:5432`, l'API sur `127.0.0.1:8000`
et l'administration sur `127.0.0.1:8001`.

Le worker est facultatif :

```bash
docker compose --env-file deploy/.env.local -f deploy/docker-compose.local.yml --profile generation up --build
```

Il contacte llama.cpp à l'adresse explicitement définie par `LLM_BASE_URL`.
Arrêter les conteneurs locaux sans supprimer leur volume :

```bash
docker compose --env-file deploy/.env.local -f deploy/docker-compose.local.yml down
```

## Production

Le Compose de production contient PostgreSQL 18, llama.cpp, les migrations,
l'API, le worker et l'administration. L'API et l'administration sont publiées
respectivement sur `127.0.0.1:8000` et `127.0.0.1:8001`. llama.cpp conserve
temporairement sa publication sur `127.0.0.1:8080`, car la configuration
Tailscale Serve existante de la tour peut en dépendre. PostgreSQL et le worker
ne publient aucun port hôte.

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

La procédure de sauvegarde et de déploiement Windows est détaillée dans
[`RELEASING.md`](../RELEASING.md).

## Préparation HTTPS avec Tailscale

L'administration écoute sur `127.0.0.1:8001`, prête à être placée derrière un
proxy HTTPS local comme Tailscale Serve. Cette configuration ne modifie pas
Tailscale. Avant toute future publication privée, conserver la configuration
Tailscale existante, choisir son URL HTTPS comme `ADMIN_BASE_URL`, puis vérifier
explicitement l'adresse source du proxy avant de l'ajouter à
`ADMIN_TRUSTED_PROXY_IPS`. Une liste vide est le réglage sûr par défaut.
