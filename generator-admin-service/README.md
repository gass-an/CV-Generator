# Service privé d'administration

Application FastAPI indépendante, rendue côté serveur avec Jinja2. Elle permet
au propriétaire du serveur de créer des propriétaires et leurs clés API, de
renouveler ou révoquer une clé et de désactiver un propriétaire. Elle partage
uniquement le package `cv-generator-shared` et PostgreSQL avec l'API publique.

## Installation locale

Depuis la racine du dépôt :

```bash
python -m pip install \
  -e ./shared \
  -e './generator-service[dev]' \
  -e './generator-admin-service[dev]'
```

Générez le hash Argon2id sans afficher le mot de passe :

```bash
python generator-admin-service/scripts/generate_password_hash.py
```

Créez d'abord la configuration locale centralisée :

```bash
cp deploy/.env.local.example deploy/.env.local
```

Copiez le résultat complet dans `ADMIN_PASSWORD_HASH` de
`deploy/.env.local`, entre apostrophes simples afin que Docker Compose conserve
ses caractères `$` sans transmettre les apostrophes. Définissez aussi
`ADMIN_USERNAME` et un `ADMIN_SESSION_SECRET` aléatoire d'au moins 32 caractères,
par exemple généré localement avec `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
Ces valeurs ne doivent jamais être versionnées.

Si un ancien fichier `.env.admin.local` contient déjà ces secrets, reportez-les
manuellement dans la section Administration de `.env.local`, sans les afficher
dans un terminal et sans écraser automatiquement l'un ou l'autre fichier.

La base est la même que celle de l'API publique. Pour lancer PostgreSQL, les
migrations, le backend et l'administration avec rechargement automatique :

```bash
docker compose --env-file deploy/.env.local -f deploy/docker-compose.local.yml up --build
```

En production, utilisez HTTPS, `APP_ENV=production`,
`ADMIN_COOKIE_SECURE=true`, une URL HTTPS dans `ADMIN_BASE_URL` et ne déclarez
dans `ADMIN_TRUSTED_PROXY_IPS` que les proxys réellement maîtrisés.

`ADMIN_TIMEZONE` définit le fuseau des dates saisies et affichées dans
l'administration. Sa valeur par défaut est `Pacific/Noumea`. Les dates du champ
« Expiration » sont interprétées dans ce fuseau, puis enregistrées en UTC dans
PostgreSQL. Une valeur doit correspondre à un identifiant IANA reconnu ;
l'application refuse de démarrer si le fuseau est inconnu.

## Utilisation

Après connexion, la page principale affiche toutes les clés. « Nouvelle clé
API » permet de sélectionner un propriétaire existant ou d'en créer un. La clé
complète est affichée une seule fois, immédiatement après sa création : copiez-la
avant de quitter l'écran. Une ancienne clé ne peut jamais être récupérée, car la
base ne conserve que son préfixe public et son empreinte SHA-256. Il faut alors
en créer une nouvelle puis révoquer l'ancienne.

Une clé créée est immédiatement active dans l'API publique. Elle peut être
testée dans Swagger avec « Authorize », ou ainsi :

```bash
export API_KEY='valeur-copiée-sur-écran'
curl -H "X-API-Key: $API_KEY" http://127.0.0.1:8000/api/v1/documents/ID/status
```

La révocation est définitive. La désactivation d'un propriétaire invalide
immédiatement toutes ses clés sans supprimer ses documents.

## Sécurité

Les sessions sont conservées côté PostgreSQL ; le navigateur ne reçoit qu'un
identifiant opaque. Son empreinte, et non sa valeur, est stockée. Les cookies
utilisent `HttpOnly` pour la session et `SameSite=Strict`; le cookie CSRF est
séparé. Toutes les mutations exigent un jeton CSRF. Les échecs de connexion sont
comptés dans PostgreSQL par adresse IP et par identifiant haché pendant la fenêtre
configurée. `X-Forwarded-For` n'est lu que pour un proxy explicitement autorisé.

Toutes les pages administratives envoient `Cache-Control: no-store`. La réponse
de création contenant la clé brute n'est ni redirigée, ni enregistrée en session,
cookie, URL, stockage navigateur ou message persistant.

## Tests

Les tests exigent une base PostgreSQL dédiée dont le nom se termine par
`_admin_test`, migrée au préalable :

```bash
export ADMIN_TEST_DATABASE_URL='postgresql+asyncpg://.../cv_generator_admin_test'
export DATABASE_URL="$ADMIN_TEST_DATABASE_URL"
cd generator-service && alembic upgrade head && cd ..
pytest generator-admin-service
```
