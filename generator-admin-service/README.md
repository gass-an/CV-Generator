# Service privé d'administration

Application FastAPI indépendante, rendue côté serveur avec Jinja2. Elle permet
au propriétaire du serveur de créer des propriétaires et leurs clés API, de
renouveler ou révoquer une clé et de désactiver un propriétaire. Elle partage
uniquement le package `cv-generator-shared` et PostgreSQL avec l'API publique.

La rubrique « Modèles LLM » relaie côté serveur les opérations officielles du
Router llama.cpp. Le navigateur ne reçoit jamais son URL et ne le contacte pas
directement. En production, `LLM_MANAGEMENT_ENABLED=true` et `LLM_BASE_URL` est
fixée à `http://llm:8080` dans Compose ; en développement la rubrique reste
désactivée par défaut afin de préserver un llama.cpp distant non administrable.

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
cp deploy/.env.example deploy/.env.local
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

La page « Activité » présente les générations en attente, en cours, terminées
ou échouées, puis un historique paginé filtrable. L'attribution correspond au
propriétaire de la clé API (`client_id`) : le modèle ne permet pas d'identifier
la clé précise ayant créé un job. Les anciens jobs sans propriétaire restent
visibles comme tels. Seul le nom du candidat, lorsqu'il existe dans
`resume_data.basics.name`, est projeté ; le JSON Resume, les résultats générés
et les erreurs internes ne sont jamais transmis à cette interface. Les données
sont actualisées toutes les cinq secondes lorsque l'onglet est visible.

Une clé créée est immédiatement active dans l'API publique. Redoc décrit
l'en-tête attendu sur `/docs` ; la clé peut être testée ainsi :

```bash
export API_KEY='valeur-copiée-sur-écran'
curl -H "X-API-Key: $API_KEY" http://127.0.0.1:8000/api/v1/documents/ID/status
```

La révocation est définitive. La désactivation d'un propriétaire invalide
immédiatement toutes ses clés sans supprimer ses documents.

La racine `/` est la page d'accueil protégée. Sans session valide, une navigation
est redirigée vers `/login`, puis revient vers la page locale initialement demandée
après authentification. Une session expirée est remplacée par une nouvelle session
de connexion et un nouveau jeton CSRF : aucune suppression manuelle de cookie
n'est nécessaire.

L'interface propose les thèmes clair, sombre et automatique. Le mode automatique,
utilisé par défaut, suit le thème du système. Le choix est conservé dans le
`localStorage` de l'origine de l'administration sous la clé
`cv-generator.theme` ; il est donc indépendant de celui du frontend principal
lorsque les deux services utilisent des ports différents.

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

Les destinations de retour après connexion sont limitées aux chemins locaux.
Les pages HTML protégées redirigent vers la connexion lorsque la session est
absente ou expirée ; la dépendance d'authentification générique conserve une
réponse HTTP `401` pour les éventuels endpoints programmatiques.

`document_job` constitue l'historique de génération. Aucun nettoyage ni délai
de rétention automatique n'est actuellement configuré dans l'application ; une
politique de rétention devra donc être décidée séparément si le volume l'exige.

## Tests

Les tests exigent une base PostgreSQL dédiée dont le nom se termine par
`_admin_test`, migrée au préalable :

```bash
export ADMIN_TEST_DATABASE_URL='postgresql+asyncpg://.../cv_generator_admin_test'
export DATABASE_URL="$ADMIN_TEST_DATABASE_URL"
cd generator-service && alembic upgrade head && cd ..
pytest generator-admin-service
```
