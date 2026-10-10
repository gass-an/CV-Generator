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
├── app/             # Déclaration des routes
├── components/
│   ├── layout/      # Structure partagée et navigation
│   └── ui/          # Composants shadcn/ui locaux (cartes et badges)
├── lib/             # Utilitaires communs
├── pages/           # Écrans associés aux routes
├── App.tsx
├── main.tsx
└── index.css
```

Les futurs appels HTTP seront placés dans `src/services/`, la logique React
réutilisable dans `src/hooks/` et les contrats dans `src/types/` lorsqu'ils
deviendront nécessaires.

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

## Étapes suivantes

Les écrans actuels présentent les emplacements et états vides définitifs, mais
leurs contrôles sont volontairement désactivés. La gestion de la clé API,
l'import JSON Resume, la génération, le suivi des jobs, l'historique dynamique
et les téléchargements feront l'objet d'évolutions séparées.
