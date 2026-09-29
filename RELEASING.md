# Publier une nouvelle version

Le projet suit le versionnage sémantique `vMAJOR.MINOR.PATCH` :

- `PATCH` correspond à une correction compatible ;
- `MINOR` correspond à une nouvelle fonctionnalité compatible ;
- `MAJOR` correspond à un changement incompatible.

Pendant la phase de développement, des versions telles que `v0.1.0`, `v0.2.0`
et leurs correctifs sont appropriées.

## 1. Mettre à jour la branche principale

```bash
git switch main
git pull --ff-only
git status
```

Le working tree doit être propre avant de préparer la release.

## 2. Choisir la version

Choisir la nouvelle version selon les changements inclus, par exemple :

```text
v0.1.0
```

## 3. Mettre à jour le changelog

Dans `CHANGELOG.md`, déplacer les éléments concernés de `## [Unreleased]` vers
une section datée, sans le préfixe `v` :

```markdown
## [Unreleased]

## [0.1.0] - YYYY-MM-DD
```

Conserver une section `[Unreleased]` vide au-dessus de la nouvelle version.

## 4. Commiter la préparation

```bash
git add CHANGELOG.md
git commit -m "chore(release): préparer la version v0.1.0"
```

D'autres fichiers peuvent faire partie de ce commit si la préparation de la
release le nécessite.

## 5. Créer un tag annoté

```bash
git tag -a v0.1.0 -m "Version 0.1.0"
```

## 6. Pousser la branche puis le tag

```bash
git push origin main
git push origin v0.1.0
```

Le push du tag déclenche automatiquement le workflow GitHub de release. Ce
workflow valide le backend, construit et publie l'image Docker, puis crée la
GitHub Release. Il ne déploie rien sur la machine de production.

## 7. Vérifier la publication sur GitHub

Vérifier successivement :

- le workflow dans GitHub Actions ;
- la GitHub Release et ses notes générées ;
- le package publié dans GHCR.

Pour `v0.1.0`, l'image attendue est :

```text
ghcr.io/gass-an/cv-generator:v0.1.0
```

## 8. Déployer manuellement sur la tour

Il n'existe volontairement aucun déploiement continu. Sur la machine hébergeant
Docker, renseigner la version explicite dans `deploy/.env` :

```env
APP_VERSION=v0.1.0
```

Depuis la racine du dépôt :

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

Vérifier ensuite les services :

```bash
docker compose \
  --env-file deploy/.env \
  -f deploy/docker-compose.prod.yml \
  ps
```

Consulter leurs logs si nécessaire :

```bash
docker compose \
  --env-file deploy/.env \
  -f deploy/docker-compose.prod.yml \
  logs -f --tail=100
```

## Rollback manuel

Pour revenir, par exemple, de `v0.2.0` à `v0.1.0`, remplacer dans
`deploy/.env` :

```env
APP_VERSION=v0.1.0
```

Puis récupérer et redémarrer les images de cette version :

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

L'utilisation d'une version explicite dans `deploy/.env`, plutôt que `latest`,
garantit que ce rollback redéploie exactement la version choisie.
