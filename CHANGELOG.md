# Journal des modifications

Toutes les évolutions notables du projet sont documentées dans ce fichier. La
structure est inspirée de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).

## [À venir]



## [0.2.0] - 2026-09-29

### Ajouts

- Ajout de la génération des lettres de motivation.
- Documentation code et Swagger en français.

## [0.1.0] - 2026-09-29

### Ajouts

- Création asynchrone de jobs de génération de CV via FastAPI.
- Récupération des offres d'emploi AVP publiées par l'OPT.
- Génération de CV AsciiDoc avec un serveur llama.cpp.
- Persistance des jobs et du résultat AsciiDoc dans PostgreSQL.
- Worker séparé pour le traitement des générations.
- Génération et téléchargement à la demande des CV au format DOCX.
- Image Docker de production commune à l'API, au worker et aux migrations.
- Workflows GitHub d'intégration continue et de publication des versions sur GHCR.
