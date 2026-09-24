# Frontend Vue + Vite

Application générée par le module `vue` de boilr. Node 24 est requis pour un lancement local ; Docker fournit ce runtime automatiquement.

## Avec Docker

Depuis la racine du projet contenant `docker-compose.yml` :

```powershell
docker compose up --build
```

Ouvrir http://localhost:5173 (ou le port choisi dans le manifeste). Le compteur de la page permet de vérifier que Vue fonctionne. Modifier `src/App.vue` pour personnaliser l'application.

## Sans Docker

Depuis `frontend/` :

```powershell
npm ci
npm run dev
```

Pour utiliser un backend démarré sur le poste :

```powershell
$env:BOILR_API_PROXY_TARGET = 'http://localhost:8000'
npm run dev
```

Le serveur écoute sur `0.0.0.0:5173` pour être utilisable dans Docker. En lancement local, vous pouvez limiter l'écoute avec `npm run dev -- --host 127.0.0.1`.

## API

Appeler des chemins relatifs, par exemple `/api/health/`. Si le proxy est activé, le préfixe `/api` est conservé. L'endpoint doit être implémenté côté backend. Les variables du frontend sont publiques : ne pas y inclure de secrets.

## Build

```powershell
npm run build
npm run preview
```

Le build est écrit dans `dist/`. `preview` sert à le vérifier localement, pas à héberger une production. Le proxy `/api` du serveur de développement doit être remplacé par un routage côté serveur en production.

## Dépendances

Ajouter un paquet avec `npm install <paquet>`, puis conserver `package.json` et `package-lock.json` ensemble. Dans Docker, redémarrer le service pour resynchroniser son volume de dépendances avec `npm ci`.
