# Journal des modifications

Toutes les évolutions notables du projet sont documentées dans ce fichier. La
structure est inspirée de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).

## [À venir]

## [0.3.0] - 2026-10-02

### Ajouts

- Gestion sécurisée des clients et des clés API dans le package partagé.
- Authentification `X-API-Key` et isolation des documents par propriétaire.
- Interface privée d'administration avec sessions PostgreSQL, Argon2id, CSRF
  et protection contre les tentatives répétées de connexion.
- Image Docker indépendante pour l'administration.

### Modifications

- Centralisation des configurations Docker Compose dans `deploy/`.
- Publication de deux images GHCR versionnées pour le backend et
  l'administration.
- Procédure documentée de sauvegarde et de déploiement manuel sur Docker
  Desktop.


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
