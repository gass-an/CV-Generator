# CV-Generator

CV-Generator génère des CV, des lettres de motivation et des guides de
préparation à l'entretien adaptés à un avis de vacance de poste (AVP) de l'OPT,
à partir des seules informations d'un JSON Resume.

Le dépôt sépare :

- le backend FastAPI et son worker dans `generator-service/` ;
- les modèles et la gestion des clés communs dans `shared/` ;
- le service privé d'administration dans `generator-admin-service/` ;
- le frontend React dans `generatorweb-service/`.

Le backend enregistre chaque demande comme un job PostgreSQL. Un worker appelle
ensuite llama.cpp, stocke le document source en AsciiDoc et permet son
téléchargement au format DOCX généré à la demande.

La [documentation du backend](generator-service/README.md) détaille
l'installation et l'API. Les [exemples curl](generator-service/demo/curl-examples.md)
permettent de tester les trois types de documents. Le
[déploiement Docker](deploy/README.md) décrit l'installation de production.
La gestion métier des clés est documentée dans [shared/README.md](shared/README.md).
Les configurations Docker locales et de production sont centralisées dans
[`deploy/`](deploy/README.md).

## Publication des versions

La procédure de version, de publication et de déploiement manuel est décrite
dans [RELEASING.md](RELEASING.md), qui constitue la source de vérité.
