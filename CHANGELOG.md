# Journal des modifications

Toutes les évolutions notables du projet sont documentées dans ce fichier. La
structure est inspirée de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).

## [À venir]

## [0.8.3] - 2026-10-27

### Ajouts

- Estimation prudente de la VRAM des modèles GGUF à partir de leurs métadonnées locales, du contexte configuré et des buffers CUDA, avec prise en charge des fichiers répartis en plusieurs shards.
- Chargement et déchargement manuel du modèle principal sans perdre la sélection PostgreSQL ni le rechargement automatique à la prochaine génération.

### Modifications

- Refonte responsive de la page « Modèles LLM » en cartes : modèle principal, modèles disponibles, progression contextuelle et ajout Hugging Face repliable.
- Lecture en accès seul du cache GGUF par l’administration afin d’afficher la taille SSD réelle des modèles déchargés, sans téléchargement supplémentaire.

### Corrections

- Inspection GGUF déplacée hors de la boucle asynchrone, mise en cache avec invalidation par shard et protégée contre les fichiers incomplets, instables ou malformés.

## [0.8.0] - 2026-10-26

### Ajouts

- Gestion sécurisée des modèles GGUF depuis l’administration privée : téléchargement suivi, activation, déchargement, sélection PostgreSQL persistante et historique du modèle réellement utilisé.

### Modifications

- Passage de llama.cpp au mode Router, limité à un modèle simultanément en VRAM, avec cache Docker existant conservé et image CUDA reproductible.

## [0.7.2] - 2026-10-18

### Ajouts

- Annulation automatique des générations en attente lors de la révocation de la clé API qui les a demandées, avec un statut « Annulée » visible dans l’administration et l’historique.

## [0.7.1] - 2026-10-17

### Ajouts

- Ajout d’un tableau de bord d’activité administrateur, actualisé automatiquement, avec compteurs, attribution aux propriétaires et historique paginé filtrable des générations.

### Modifications

- Partage du modèle `DocumentJob` entre le générateur et l’administration, et ajout d’index PostgreSQL adaptés aux consultations chronologiques de l’activité.
- Fiabilisation des tests par des horloges déterministes, un nettoyage systématique des timers et mocks, et l’alignement explicite de Node.js et des contrôles Alembic entre les validations locales et la CI.


## [0.6.2] - 2026-10-17

### Ajouts

- Ajout du logo STATION N et de liens accessibles vers les sites officiels des trois partenaires dans le footer.
- Ajout des téléchargements du source AsciiDoc et de sa conversion Markdown pour les CV, lettres de motivation et guides d'entretien.
- Intégration des quatre formats PDF, DOCX, ADOC et MD dans la génération et l'historique du frontend.

### Modifications

- Harmonisation des routes d'export sous `/documents/{id}/{format}` et remplacement définitif de `/download` par `/docx`.
- Conversion Markdown cohérente avec la normalisation DOCX, avec listes imbriquées CommonMark et préservation des blocs délimités pris en charge.
- Sécurisation des blocs de code Markdown par un délimiteur CommonMark adapté aux séquences d'accents graves présentes dans leur contenu.

### Corrections

- Renouvellement transparent du jeton CSRF de connexion après une longue inactivité, avec distinction entre expiration du formulaire et identifiants invalides et protection contre les doubles soumissions.

## [0.5.7] - 2026-10-14

### Modifications

- Modernisation de l'administration, avec reconnexion fiable après expiration, navigation protégée et thèmes clair, sombre et automatique.

## [0.5.5] - 2026-10-14

### Modifications

- Fix d'un soucis avec la référence de l'offre dans l'objet des lettres de motivation.

## [0.5.5] - 2026-10-14

### Modifications

- Remplacement de Swagger UI par Redoc pour la documentation de l'API publique.
- Ajout de la référence de l'offre dans l'objet des lettres de motivation.
- Ajout du logo CV-Generator comme favicon du frontend.

## [0.5.4] - 2026-10-11

### Ajouts

- Ajout d'une combobox de filtrage par numéro AVP dans l'historique, avec récupération des AVP distincts et filtrage exact côté API.

### Corrections

- Fiabilisation de l'indicateur de génération avec respect de `prefers-reduced-motion`.
- Amélioration de la navigation clavier dans la combobox et cohérence du filtrage des numéros AVP comportant des espaces périphériques.

## [0.5.2] - 2026-10-11

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
