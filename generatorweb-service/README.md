# Interface web CV-Generator

Interface publique responsive de CV-Generator. Elle prépare les parcours de
génération, d'historique et de configuration ; les appels à l'API et les
fonctionnalités métier seront ajoutés ultérieurement.

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

`AppProvider` conserve séparément la configuration d'authentification et le
brouillon de candidature. Le hook `useAppState` les rend disponibles pendant
la navigation sans gestionnaire d'état externe.

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

## Étapes suivantes

La clé API, l'import JSON Resume et le numéro AVP sont fonctionnels. La
sélection du type de document, la génération, le polling, l'historique
dynamique, la prévisualisation et les téléchargements restent volontairement
inactifs jusqu'aux prochaines étapes.
