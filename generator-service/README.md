# Generator Service

Backend stateless du projet HackAVP, destiné à générer des documents à partir
d'un CV au format JSON Resume et des données d'un AVP.

Cette première version expose uniquement un endpoint de santé. Le routeur de
documents est préparé, sans implémenter la génération.

## Prérequis

- Python 3.12

## Installation

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
cp .env.example .env
```

## Lancement en développement

```bash
uvicorn app.main:app --reload
```

L'API est alors disponible sur `http://127.0.0.1:8000`. Le contrôle de santé
est accessible via `GET /api/v1/health` et la documentation OpenAPI via
`/docs`.

## Qualité et tests

```bash
ruff format --check .
ruff check .
pytest
```

Pour appliquer automatiquement le formatage :

```bash
ruff format .
```

## Configuration

La configuration est lue depuis les variables d'environnement et, en local,
depuis un éventuel fichier `.env`. Copier `.env.example` pour obtenir la liste
des variables attendues. Ne jamais y stocker de vrai secret dans le dépôt.
