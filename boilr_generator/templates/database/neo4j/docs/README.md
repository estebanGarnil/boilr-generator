# Neo4j pour boilr — module 1.0.0

Service Neo4j Community destiné au développement local. Image officielle
`neo4j:5.26-community` : branche 5.26 LTS, tag évolutif et non digest immuable.
Utilisateur initial et base applicative : `neo4j`. Aucun plugin APOC ou GDS
n'est installé. Aucune modification du moteur Python n'est nécessaire.

## Installation du module dans le monorepo

Copier le dossier `boilr_generator/templates/database/neo4j` de l'archive dans
`packages/boilr-generator/boilr_generator/templates/database/neo4j`.
Copier `tests/test_neo4j_module.py` dans `packages/boilr-generator/tests/`.
Depuis `packages/boilr-generator` :

```powershell
python -m pip install -e .
python -m pytest -q tests/test_neo4j_module.py
python -m ruff check tests/test_neo4j_module.py
git diff --check
```

Il est possible de conserver la branche `feature/vue-module` en séparant les
commits Vue et Neo4j. Aucun changement de branche n'est requis pour ces tests.

## Générer et démarrer une nouvelle base

Depuis le package du générateur, utiliser un dossier de sortie neuf :

```powershell
python -m boilr_generator.cli dry-run `
    .\boilr_generator\templates\database\neo4j\docs\examples\neo4j-only.yml `
    .\generated-neo4j

python -m boilr_generator.cli generate `
    .\boilr_generator\templates\database\neo4j\docs\examples\neo4j-only.yml `
    .\generated-neo4j

Set-Location .\generated-neo4j
docker compose config --quiet
docker compose up -d neo4j
docker compose ps
docker compose logs --tail 100 neo4j
```

Attendre l'état `healthy`. Le contrôle de santé exécute `RETURN 1` via Bolt et
vérifie donc également l'authentification. Une machine lente peut nécessiter
plusieurs minutes de démarrage.

Ouvrir http://localhost:7474 et se connecter à `bolt://localhost:7687` avec
l'utilisateur `neo4j` et le mot de passe du manifeste. L'exemple emploie
`dev-graph-password`, uniquement pour le développement. Dans Browser :

```cypher
RETURN 1 AS ok;
```

Ou depuis le terminal, sans mettre le mot de passe dans l'historique :

```powershell
docker compose exec neo4j cypher-shell -u neo4j -d neo4j
```

## Variables du manifeste

| Variable | Défaut | Signification |
| --- | --- | --- |
| `neo4j_password` | Obligatoire, sans défaut | Mot de passe initial, au moins 8 caractères. |
| `neo4j_http_port` | `7474` | Port publié pour Browser. |
| `neo4j_bolt_port` | `7687` | Port publié pour les drivers. |

Les ports hôte doivent être libres, distincts et compris entre 1 et 65535.
Le schéma actuel de boilr vérifie les types et la présence des valeurs, pas
ces contraintes de plage ni la longueur du mot de passe. Neo4j vérifie le mot
de passe au démarrage. Utiliser une valeur non vide, sur une seule ligne,
sans caractère nul ; préférer un mot de passe long.

Les `$` du mot de passe sont doublés uniquement dans le YAML Compose pour
préserver leur valeur lors de l'interpolation Docker. Le binding conserve
le mot de passe original. Le secret figure en clair dans le manifeste et le
Compose généré : ces fichiers doivent être traités comme des configurations
locales contenant des secrets.

`NEO4J_AUTH` initialise uniquement une base neuve. Changer le manifeste ne
change pas le mot de passe d'une base déjà persistée. Faire la rotation dans
Neo4j puis aligner la configuration ; sinon le healthcheck échouera.

## Connexions et ports

| Client | URI à utiliser avec les ports par défaut |
| --- | --- |
| Python sur Windows | `bolt://localhost:7687` |
| Backend dans le même Compose | `bolt://neo4j:7687` |
| Neo4j Browser | Page `http://localhost:7474`, connexion `bolt://localhost:7687` |

Si le port hôte Bolt devient 17687, utiliser `bolt://localhost:17687` depuis
Windows et Browser. L'URI interne reste `bolt://neo4j:7687`.
Le schéma `bolt://` cible directement cette instance sans routage de cluster.
Les ports publiés sont liés à `127.0.0.1`, pour un usage local.

## Capacité et exports

Le module expose **graph.connection**, avec les champs suivants :

| Champ | Type | Valeur |
| --- | --- | --- |
| `engine` | string | `neo4j` |
| `host` | string | `neo4j` |
| `port` | int | `7687` |
| `name` | string | `neo4j` |
| `user` | string | `neo4j` |
| `password` | string | Valeur de `neo4j_password` |
| `service` | string | `neo4j` |
| `uri` | string | `bolt://neo4j:7687` |

Un futur consommateur peut déclarer :

```yaml
requires:
  - capability: graph.connection
    binding: graph_database
    unique: true
    optional: false
    contract:
      uri: string
      user: string
      password: string
      name: string
      service: string
```

Ses templates accéderont à `bindings.graph_database.uri`, etc. Déclarer aussi
`uses.bindings: [graph_database]` sur les ressources concernées.

Les exports `.env` sont `NEO4J_URI`, `NEO4J_USER`, `NEO4J_DATABASE`,
`NEO4J_LOCAL_URI` et `NEO4J_BROWSER_URL`. Un programme Python ne charge pas
le `.env` automatiquement. Le mot de passe n'est pas exporté : le sérialiseur
actuel de boilr écrit des valeurs dotenv sans échappement ; cela pourrait
altérer certains secrets. Le fournir explicitement à l'application (saisie
interactive dans l'exemple Python), ou via une future intégration maîtrisée.

## Cohabitation avec Django et PostgreSQL

Le manifeste `docs/examples/django-postgres-neo4j.yml` génère les trois services.
PostgreSQL reste la base SQL de Django ; Neo4j est disponible pour le graphe.
Le nom de service `neo4j` et les exports `NEO4J_*` ne remplacent ni `db` ni
`DB_*`. La capacité distincte évite une sélection ambiguë pour Django.

Cette version ne modifie pas Django, n'installe pas son driver et ne configure
pas automatiquement sa connexion au graphe. Installer le driver Python
`neo4j` dans les dépendances du backend puis utiliser `GraphDatabase.driver`
avec `bolt://neo4j:7687`. Neo4j ne remplace pas le backend SQL du Django ORM.

Pour tester depuis Windows, depuis le package du générateur :

```powershell
python -m pip install "neo4j>=5.26,<6"
python .\boilr_generator\templates\database\neo4j\docs\examples\check_connection.py
```

Si le port hôte est personnalisé, définir `$env:NEO4J_LOCAL_URI` avant ce test.
L'exemple vérifie une connexion et exécute une requête en lecture seule.

## Données et imports

`neo4j_data` persiste `/data` ; `neo4j_logs` persiste `/logs`.
`docker compose down` conserve ces volumes. **`docker compose down -v`
supprime les volumes de la stack et peut effacer toutes ses bases.**

Le dossier généré `database/neo4j/import` est monté en lecture seule dans
`/var/lib/neo4j/import`. Placer un CSV puis utiliser `file:///nom.csv` avec
`LOAD CSV`. Aucun fichier n'est importé automatiquement.

Le module démarre une base neuve distincte : il ne récupère pas une base Neo4j
existante ni les dumps Wikipédia. Pour un gros graphe, prévoir une procédure
d'import et un dimensionnement mémoire/disque séparés. Cette version garde
les réglages mémoire de l'image et ne promet pas de performances particulières.

Les noms du service, des volumes et le nom de base sont fixes. Une seule
instance de ce module est prévue par projet. Le dossier import et le README
utilisent la stratégie `merge` ; une régénération peut remplacer leurs fichiers
homonymes. Examiner le plan avant de régénérer un projet modifié.

## Sources officielles consultées

- https://neo4j.com/docs/operations-manual/current/docker/introduction/
- https://neo4j.com/docs/operations-manual/current/docker/operations/
- https://neo4j.com/docs/operations-manual/current/docker/mounting-volumes/
- https://neo4j.com/blog/developer/neo4j-v5-lts-evolution/
- https://hub.docker.com/_/neo4j

Le rapport de validation de l'archive précise les tests réellement exécutés.
