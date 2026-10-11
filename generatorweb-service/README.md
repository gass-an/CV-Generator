# Interface web CV-Generator

Interface publique responsive de CV-Generator. Elle permet de configurer
l'accès à l'API, préparer une candidature, lancer la génération d'un document
et suivre son traitement asynchrone.

## Stack technique

- React 19 et TypeScript strict ;
- Vite 8 ;
- Tailwind CSS 4 et composants shadcn/ui ;
- React Router et icônes Lucide ;
- ESLint, Prettier, Vitest et React Testing Library.

## Prérequis

- Node.js `^22.13.0`, `^24.0.0` ou `>=26.0.0` ;
- npm 11 ou une version compatible avec la version de Node.js utilisée.

Le fichier `package-lock.json` est versionné. Sur une copie propre du dépôt,
préférer `npm ci` pour reproduire exactement l'installation validée.

## Installation et commandes

Depuis `generatorweb-service/` :

```bash
npm install
npm run dev
```

Les autres commandes disponibles sont :

| Commande               | Rôle                                                                    |
| ---------------------- | ----------------------------------------------------------------------- |
| `npm run build`        | Contrôle TypeScript puis construit les fichiers statiques dans `dist/`. |
| `npm run preview`      | Sert localement le build de production.                                 |
| `npm run lint`         | Exécute ESLint.                                                         |
| `npm run format`       | Formate les sources avec Prettier.                                      |
| `npm run format:check` | Vérifie le formatage sans modifier les fichiers.                        |
| `npm run typecheck`    | Contrôle les types sans produire de fichiers.                           |
| `npm run test`         | Exécute les tests une fois.                                             |
| `npm run test:watch`   | Relance les tests pendant le développement.                             |
| `npm run test:ci`      | Exécute les tests avec un rapport détaillé pour la CI.                  |

## Organisation

```text
src/
├── app/             # Provider de l'application et état partagé
├── components/
│   ├── layout/      # Structure partagée et navigation
│   └── ui/          # Composants shadcn/ui locaux (cartes et badges)
├── hooks/           # Accès typé à l'état React partagé
├── lib/             # Utilitaires communs
├── pages/           # Écrans associés aux routes
├── services/        # Client HTTP et appels ciblés au backend
├── types/           # Types des données du frontend
├── App.tsx
├── main.tsx
└── index.css
```

`AppProvider` conserve séparément la configuration d'authentification, le
brouillon de candidature et le job suivi. Le hook `useAppState` les rend
disponibles pendant la navigation sans gestionnaire d'état externe.

Les routes disponibles sont `/` pour préparer une génération, `/historique`
pour les documents du client et `/parametres` pour la future configuration de
la clé API. Les routes inconnues affichent une page 404 dans le layout commun.

Les logos officiels CV-Generator, OPT et IAE sont servis depuis
`public/logos/`. Le composant `BrandLogo` centralise leurs chemins, textes
alternatifs et dimensions afin de préserver leurs proportions respectives.

## Proxy API en développement

Le navigateur utilisera toujours des chemins relatifs sous `/api`. En mode
développement seulement, Vite peut les transmettre au backend FastAPI :

```bash
cp .env.example .env.local
npm run dev
```

`DEV_API_PROXY_TARGET` est lu uniquement par le serveur Vite et vaut
`http://localhost:8000` par défaut. Cette configuration ne doit contenir
aucune clé API. En production, le reverse proxy Nginx assurera le routage.

## Configuration de la clé API

La page `/parametres` vérifie la clé avec une requête authentifiée vers
`GET /api/v1/documents?limit=1&offset=0`. La clé est transmise uniquement dans
l'en-tête `X-API-Key` et ne devient active qu'après une réponse `200`.

Par défaut, une clé validée est enregistrée dans `sessionStorage` et reste
disponible pendant la session de l'onglet. L'option « Mémoriser » la déplace
dans `localStorage` afin de la retrouver après la fermeture du navigateur. Une
seule copie est conservée. Toute clé chargée au démarrage est de nouveau
vérifiée avant que l'interface affiche l'état connecté.

Ces stockages sont accessibles au JavaScript de la même origine : ils ne sont
ni chiffrés ni protégés contre une compromission de la page. La clé n'est
jamais placée dans une URL, un log ou une variable d'environnement Vite.

## Import JSON Resume et numéro AVP

La page `/` accepte des fichiers JSON de 2 Mo maximum sous deux formes :

1. un objet JSON Resume direct ;
2. une enveloppe contenant `resume` et, facultativement, `avp_number`.

L'enveloppe est normalisée : seul son objet `resume` est conservé comme profil,
sans supprimer ses propriétés supplémentaires. Un numéro AVP exploitable
préremplit le champ correspondant, que l'utilisateur peut ensuite modifier.
L'import d'un profil direct sans AVP ne remplace pas une valeur déjà saisie.

La syntaxe JSON, la racine, l'enveloppe et les principaux types JSON Resume
sont validés localement. Un import invalide ne remplace pas le dernier profil
valide. Le profil complet reste uniquement dans la mémoire React : il n'est
écrit dans aucun stockage navigateur et aucune donnée n'est envoyée au backend
lors du simple import. Un rechargement complet impose donc de réimporter le
fichier.

## Génération et suivi asynchrone

Après validation de la clé, du profil et du numéro AVP, l'utilisateur choisit
un CV, une lettre de motivation ou un guide de préparation à l'entretien. Une
seule requête `POST` est envoyée vers la route FastAPI correspondante. En cas
d'erreur réseau ou de timeout pendant cet envoi, l'application ne réessaie pas
automatiquement, car le backend peut déjà avoir créé le job.
Une réponse de création incertaine bloque donc toute nouvelle soumission jusqu'à
ce que l'utilisateur confirme explicitement qu'il accepte le risque de doublon.

Le job retourné est conservé dans `AppProvider` pendant la navigation. Son
statut est consulté environ toutes les 2,5 secondes, sans requêtes
concurrentes. Le suivi s'arrête sur `completed` ou `failed`. Une interruption
réseau est distinguée d'un échec du traitement et peut être reprise sur le même
identifiant, sans soumettre une nouvelle génération. L'utilisateur peut aussi
arrêter ce suivi local sans annuler le traitement côté serveur. Cet état reste
en mémoire uniquement, mais un job peut être retrouvé et repris depuis
l'historique après un rechargement complet.

La suppression d'une clé ou son remplacement réussi par une clé différente
réinitialise le job suivi et le brouillon de candidature. Cela évite d'afficher
ou de réutiliser les données personnelles du client précédent sur un navigateur
partagé. Un remplacement refusé conserve au contraire la clé, le brouillon et
le suivi existants.

## Historique et fichiers générés

La page `/historique` charge des pages de 20 générations appartenant au client
API authentifié. Plusieurs clés du même client voient donc le même historique :
il ne s'agit pas d'un historique individuel. Les filtres de type et de statut
sont appliqués par l'API, et les jobs en attente ou en cours peuvent être repris
sans nouvel import et sans nouvelle requête de création.

Pour un document terminé, le frontend récupère les fichiers avec `X-API-Key` :
`/documents/{id}/download` pour le DOCX et `/documents/{id}/pdf` pour le PDF.
Le PDF est généré à la demande par LibreOffice côté backend puis affiché depuis
une Blob URL locale ; la clé API n'apparaît jamais dans l'URL du visualiseur.
Les téléchargements utilisent des noms lisibles construits à partir du type,
du candidat, de l'AVP et de la date.

Les Blob URLs sont libérées après usage, à la fermeture d'un aperçu, lors d'un
changement de document ou de clé et au démontage des composants. Aucun PDF,
DOCX, contenu AsciiDoc ou JSON Resume n'est conservé dans un stockage navigateur
persistant. Le timeout couvre aussi la lecture complète des réponses binaires.
Un refus `401` de la clé active invalide immédiatement la session et masque les
données du client devenues inaccessibles ; une réponse tardive liée à une
ancienne clé est ignorée. Les erreurs `409`, conversion, timeout et réseau sont
présentées sans nouvelle conversion automatique ; l'utilisateur peut relancer
manuellement un aperçu.

Le futur reverse proxy Nginx devra autoriser une durée suffisante pour les
conversions PDF, cohérente avec le timeout backend de 60 secondes et le timeout
frontend dédié de 90 secondes.

## Étapes suivantes

La configuration, la génération, le suivi, l'historique, la prévisualisation
PDF et les téléchargements sont fonctionnels. L'intégration Docker/Nginx et la
CI/CD du frontend restent prévues pour une étape ultérieure.
