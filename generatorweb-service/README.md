# Interface web CV-Generator

Socle React de l'interface publique de CV-Generator. Cette première étape met
en place la navigation et les outils de développement ; les appels à l'API et
les fonctionnalités de génération seront ajoutés ultérieurement.

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
│   ├── layout/      # Structure partagée de l'application
│   └── ui/          # Composants shadcn/ui locaux
├── lib/             # Utilitaires communs
├── pages/           # Écrans associés aux routes
├── App.tsx
├── main.tsx
└── index.css
```

Les futurs appels HTTP seront placés dans `src/services/`, la logique React
réutilisable dans `src/hooks/` et les contrats dans `src/types/` lorsqu'ils
deviendront nécessaires.

Le répertoire `public/logos/` est réservé aux logos officiels qui seront
fournis ultérieurement. Aucun visuel de remplacement n'est inclus.

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

Les écrans actuels sont volontairement informatifs. La gestion de la clé API,
l'import JSON Resume, la génération, le suivi des jobs, l'historique et les
téléchargements feront l'objet d'évolutions séparées.
