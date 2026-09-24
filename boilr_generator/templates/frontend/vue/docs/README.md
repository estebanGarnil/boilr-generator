# Module Vue pour boilr — 1.0.0

Module frontend autonome : Vue 3, Vite 8, JavaScript, composants Single File Components et Docker pour le développement local. Il ne requiert ni Django ni base de données. Pas de modification du moteur Python.

## Installation dans le générateur

Depuis ce ZIP, copier `boilr_generator/templates/frontend/vue/` dans le même dossier du dépôt `boilr-generator`. Dans le monorepo, la destination est `packages/boilr-generator/boilr_generator/templates/frontend/vue/`.

Copier également `tests/test_vue_module.py` dans les tests du générateur si vous souhaitez conserver les vérifications fournies. Les autres fichiers du dépôt ne sont pas remplacés.

À la racine du générateur (ou dans `packages/boilr-generator`), installer la copie locale. Une installation PyPI existante ne voit pas automatiquement les nouveaux fichiers de votre checkout :

```powershell
python -m pip install -e .
```

Le registre découvre récursivement `module.yml`. Aucun enregistrement manuel n'est nécessaire. Le packaging du dépôt inclut déjà `templates/**/*` et les fichiers cachés des templates.

## Générer Vue seul

Depuis la racine du générateur :

```powershell
python -m boilr_generator.cli dry-run `
    .\boilr_generator\templates\frontend\vue\docs\examples\vue-only.yml `
    .\generated-vue

python -m boilr_generator.cli generate `
    .\boilr_generator\templates\frontend\vue\docs\examples\vue-only.yml `
    .\generated-vue

Set-Location .\generated-vue
docker compose up --build
```

Ouvrir http://localhost:5173. Modifier `frontend/src/App.vue` pour vérifier le rechargement automatique. Le service publie le port sur `127.0.0.1` uniquement.

Arrêter avec Ctrl+C, puis `docker compose down`. Le volume `vue_node_modules` conserve les dépendances Linux séparément de celles du poste de développement. Le démarrage exécute `npm ci`, ce qui resynchronise les dépendances avec le lockfile ; le premier build et chaque installation nécessitent l'accès au registre npm. Le Dockerfile installe aussi les dépendances pour permettre son utilisation sans Compose.

## Configuration

| Champ | Type | Défaut | Utilisation |
| --- | --- | --- | --- |
| `variables.project_name` | string | `Boilr Vue` | Titre de la page et de l'application ; indépendant du nom npm fixe. |
| `variables.frontend_port` | int | `5173` | Port hôte, à choisir entre 1 et 65535 et non occupé. Le port interne reste 5173. |
| `variables.api_proxy_target` | string | chaîne vide | URL HTTP(S) du backend vue depuis le serveur Vite ; vide = proxy désactivé. |
| `options.polling` | boolean | `false` | Activer si les modifications ne sont pas détectées avec Docker Desktop/WSL ; augmente l'activité CPU. |

Boilr vérifie les types, mais ne valide pas la plage des ports. La configuration Vite rejette une cible proxy sans préfixe HTTP(S). Le nom de projet est sérialisé avec `tojson` pour préserver guillemets, antislashs et caractères spéciaux.

Les valeurs sont locales au module : `project.name` ne remplace pas automatiquement `variables.project_name`.

## Ajouter Vue à un manifeste existant

Ajouter cette entrée à la liste `modules` existante :

```yaml
- key: vue
  variables:
    project_name: Mon application
    frontend_port: 5173
    api_proxy_target: http://backend:8000
  options:
    polling: false
```

`docs/examples/django-vue-postgres.yml` fournit une stack complète avec les modules existants `postgres`, `django` et `django-postgres`. Les secrets de cet exemple sont réservés au développement.

## Fonctionnement du proxy Django

Le navigateur appelle une URL relative, par exemple `fetch('/api/health/')`. Vite relaie cette requête vers `http://backend:8000/api/health/` à l'intérieur du réseau Compose. Le préfixe `/api` n'est pas retiré.

Il faut créer les routes API correspondantes dans Django : ce module n'ajoute aucun endpoint. Une réponse 404 est donc normale si la route n'existe pas. Un échec temporaire est possible tant que le backend démarre ; le frontend n'a volontairement pas de dépendance Compose obligatoire sur Django.

Dans Docker, `backend` désigne le service Django ; `localhost` désignerait le conteneur frontend. En développement hors Docker, utiliser `http://localhost:8000` à la place, via la variable d'environnement `BOILR_API_PROXY_TARGET`.

L'exemple ajoute `backend` aux `allowed_hosts` de Django, car le proxy utilise `changeOrigin: true`. Les appels relatifs via Vite restent sur la même origine côté navigateur : l'exemple désactive CORS. Les appels directs depuis le navigateur vers un autre port nécessiteraient leur propre configuration CORS.

Le proxy n'implémente ni authentification ni gestion CSRF. Pour des sessions Django et des requêtes POST, configurer les cookies, le jeton CSRF et les origines de confiance en fonction de l'application. Aucun secret ne doit être placé dans le code frontend ni dans une variable `VITE_*`.

## Contrat boilr et limites

Le module expose la capacité `frontend.web` avec `framework`, `service`, `host`, `port` et `published_port`. Le port interne est 5173 ; `published_port` reprend le paramètre utilisateur. Aucun binding ni point d'extension n'est consommé dans cette version ; il n'y a donc pas de `uses` à déclarer.

La connexion HTTP au backend est un paramètre explicite. Le module Django actuel expose seulement `backend.python` avec le runtime et le framework. Une future intégration automatique devra définir un contrat HTTP adapté ; cette version ne prétend pas le résoudre.

Chaque source possède un `id` stable. Les chemins `to` incluent explicitement `frontend/` car ils sont relatifs à la racine de sortie. Les fichiers Vue sont copiés, ce qui conserve leurs expressions `{{ ... }}`. Seules les deux configurations `.j2` sont rendues.

La copie utilise `merge` : les fichiers correspondants peuvent être écrasés lors d'une nouvelle génération. Ne pas relancer `generate` ou utiliser `--clean` sur un projet modifié sans examiner le plan. Utiliser le cycle `status`/`update` du générateur pour une application existante, en examinant les conflits.

Les noms de service `frontend`, de volume `vue_node_modules` et de dossier `frontend/` sont fixes. Cette version vise un frontend Vue par projet et peut entrer en conflit avec un autre module utilisant ces noms.

## Dépendances et reproductibilité

Vue `3.5.43`, Vite `8.3.1`, `@vitejs/plugin-vue` `6.0.9`. Les versions directes sont exactes et un `package-lock.json` est fourni. Docker utilise `node:24-alpine` (tag de branche, pas digest immuable). Pour travailler hors Docker, utiliser Node 24.

Pour ajouter une dépendance, utiliser `npm install <paquet>` dans `frontend/`, puis versionner ensemble `package.json` et `package-lock.json`. Ne pas modifier seulement le manifeste npm, car `npm ci` exige leur cohérence.

## Production

`npm run build` produit `frontend/dist/`. Le service Compose fourni est un serveur de développement. Pour la production, servir `dist/` via un serveur HTTP adapté et prévoir le fallback SPA si un routeur est ajouté. Le proxy Vite existe seulement en développement : le routage `/api` doit être configuré séparément sur le serveur de production.

Cette version ne comprend pas TypeScript, Vue Router, Pinia, un serveur de production ou une intégration automatique Django. Ces fonctionnalités peuvent être ajoutées explicitement ensuite.

## Vérifications

Après copie dans le dépôt :

```powershell
python -m pytest -q tests/test_vue_module.py
python -m ruff check tests/test_vue_module.py
git diff --check
```

Après génération :

```powershell
docker compose config
docker compose up --build
```

Consulter `VALIDATION.md` à la racine de l'archive pour les contrôles réellement effectués lors de la livraison.

## Références

- Conventions boilr : https://github.com/estebanGarnil/boilr-generator/blob/main/docs/creating-a-module.md
- Vue : https://vuejs.org/guide/introduction.html
- Vite et prérequis Node : https://vite.dev/guide/
- Proxy Vite : https://vite.dev/config/server-options.html#server-proxy
