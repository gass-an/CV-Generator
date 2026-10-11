# Journal des modifications

Toutes les évolutions notables du projet sont documentées dans ce fichier. La
structure est inspirée de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).

## [À venir]

### Ajouts

- Ajout du mode sombre
- Ajout de l'agrandissement de l'aperçu PDF après génération

## [0.5.0] - 2026-10-11

### Ajouts

- Ajout de la CI sélective et de l'image frontend Nginx intégrée au déploiement.
- Ajout de l'historique interactif, de la prévisualisation PDF et des téléchargements DOCX/PDF.
- Ajout de la génération des trois documents et du suivi asynchrone des traitements.
- Ajout de la configuration et de la vérification des clés API dans le frontend.
- Ajout de l'import JSON Resume et de la saisie du numéro AVP.
- Création de l'interface responsive HackAVP et intégration des logos officiels.
- Initialisation du frontend React avec TypeScript, Vite et Tailwind CSS.
- Ajout d'un historique paginé des documents générés, accessible par client API.
- Ajout de la génération et de la prévisualisation des documents au format PDF.

### Corrections

- Fiabilisation des téléchargements, des aperçus PDF et de l'authentification du frontend.
- Sécurisation des relances de génération, du suivi et des changements de clé API.

## [0.4.1] - 2026-10-10

### Corrections

- Correction de la mise en forme AsciiDoc des documents générés
- Amélioration du rendu DOCX (gras, italique, listes et sous-listes)
- Normalisation des réponses du LLM pour corriger les erreurs de syntaxe Markdown
- Fixation de l'image postgres 18 

## [0.4.0] - 2026-10-10

### Ajouts

- Guide de préparation à l'entretien

## [0.3.2] - 2026-10-05

### Modifications

- Ajout de la version dynamique dans le swagger

## [0.3.1] - 2026-10-03

### Modifications

- Utilisation de chemins relatifs pour les ressources statiques

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
