# Service d'administration

Ce répertoire accueillera l'application web privée permettant au propriétaire
du serveur de créer des clients, d'émettre ou révoquer leurs clés d'API et de
désactiver leur accès.

La future application sera indépendante du backend public et installera le
package `cv-generator-shared` situé dans `shared/`. Cette PR ne contient ni
application, ni route, ni authentification administrateur, ni image Docker.
