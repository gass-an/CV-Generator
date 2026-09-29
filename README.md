# CV-Generator

CV-Generator fournit une API et un worker de génération asynchrone de CV à
partir d'un JSON Resume et d'une offre d'emploi AVP de l'OPT. Le résultat
AsciiDoc est stocké dans PostgreSQL et peut être téléchargé au format DOCX.

Le backend se trouve dans `generator-service/`. La configuration du déploiement
manuel de production se trouve dans `deploy/`.

## Releases

La procédure de version, de publication et de déploiement manuel est décrite
dans [RELEASING.md](RELEASING.md), qui constitue la source de vérité.
