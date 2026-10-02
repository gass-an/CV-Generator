# Package partagé CV-Generator

`cv-generator-shared` contient l'unique base déclarative SQLAlchemy, les modèles
`ApiClient` et `ApiKey`, leurs repositories asynchrones et le service métier de
gestion des clés. Il est installable indépendamment et n'importe jamais le
backend public.

## Clés et sécurité

Une clé a la forme `cvg_<préfixe>_<secret>`. Le préfixe est généré avec
`secrets.token_hex(9)` et le secret, indépendamment, avec
`secrets.token_urlsafe(32)` à partir de 32 octets aléatoires. La base ne reçoit
que le préfixe public et le SHA-256 de la clé complète. La valeur complète n'est
présente que dans `CreatedApiKey.value`, dont le champ est exclu de `repr`, et
n'est renvoyée qu'à la création. Les valeurs transitoires de génération masquent
également la clé et son empreinte dans leur représentation textuelle.

SHA-256 convient ici parce que les clés sont aléatoires et possèdent une forte
entropie. Un futur mot de passe administrateur devra employer un algorithme de
dérivation adapté aux mots de passe, tel qu'Argon2id.

La vérification valide strictement le format, recherche le préfixe, recalcule
l'empreinte et utilise `hmac.compare_digest`. Elle refuse une clé inconnue,
révoquée, expirée (y compris exactement à l'instant courant), ou appartenant à
un client désactivé. Une révocation est définitive et idempotente. Renouveler
une clé consiste toujours à en créer une nouvelle.

## Transactions et concurrence

`ApiKeyService` possède les transactions : chaque méthode publique ouvre et
termine sa transaction. Son appelant doit donc lui fournir une session libre de
toute transaction active et ne doit pas entourer ces appels d'un `begin()`.
Les repositories ne committent jamais ; ils exécutent uniquement les requêtes
et les `flush` demandés par le service.

La création et la désactivation verrouillent la ligne du client avec
`SELECT ... FOR UPDATE`. Chaque tentative de génération est isolée dans un
savepoint. Une collision sur `uq_api_key_prefix` ou `uq_api_key_key_hash`
provoque une nouvelle génération, avec cinq tentatives par défaut. Toute autre
erreur d'intégrité remonte à l'appelant. Aucun appel réseau n'est effectué dans
une transaction.

## Installation et vérification

Depuis la racine du dépôt :

```bash
python -m pip install -e 'shared[dev]'
ruff format --check shared
ruff check shared
TEST_DATABASE_URL=postgresql+asyncpg://cv_generator:cv_generator@localhost:5432/cv_generator_test \
  pytest shared
```

Les tests d'intégration refusent toute URL dont le nom de base ne se termine pas
par `_test`, afin d'éviter une exécution destructive sur une base réelle.
