# Creating a Boilr Module

A Boilr module is a reusable, declarative building block.

Modules can provide capabilities, consume capabilities from other modules, expose extension points, contribute values, copy files, render templates, define Docker services, and export environment variables.

Most new technologies can be added without modifying the core generator.

## Module categories

Typical module categories include:

- backend;
- frontend;
- database;
- cache;
- proxy;
- infrastructure;
- integration.

An integration module connects two or more independent modules. For example, `django-postgres` contributes the PostgreSQL driver and Django database backend without placing PostgreSQL-specific logic inside the Django module.

## Directory structure

```text
module-name/
|-- module.yml
|-- files/
`-- docs/
```

Only `module.yml` is mandatory. The other directories depend on what the module generates.

## Minimal manifest

```yaml
meta:
  name: Example
  key: example
  type: backend
  version: 1.0.0
  description: Example reusable module
  tags:
    - example

role:
  group: backend

assembly:
  priority: 100
  destination_root: backend

sources:
  copy: []
  render: []
```

## Metadata

The `meta` section identifies the module:

```yaml
meta:
  name: Django
  key: django
  type: backend
  version: 1.0.0
  description: Django backend
  tags:
    - python
    - django
```

The module key must be lowercase and unique in the registry.

The `role.group` field classifies the module. Uniqueness is not defined globally by roles; consumers express their actual provider requirements through capability bindings.

## Variables

Variables are values supplied by the project manifest:

```yaml
variables:
  project_name:
    type: string
    required: true
    description: Project name

  backend_port:
    type: int
    required: true
    default: 8000
    description: Published backend port
```

Supported variable types are:

- `string`;
- `int`;
- `boolean`;
- `list`.

A required variable must either have a default or be provided by the project manifest.

Variables are available as top-level Jinja values:

```jinja
{{ project_name }}
{{ backend_port }}
```

## Options

Options enable configurable module features:

```yaml
options:
  rest_framework:
    type: boolean
    default: true
    description: Enable Django REST Framework

  cors:
    type: boolean
    default: true
    description: Enable CORS support
```

Options are available through the `options` namespace:

```jinja
{{ options.rest_framework }}
{{ options.cors }}
```

## Providing capabilities

A module exposes reusable data through `provides`:

```yaml
provides:
  - capability: database.connection
    values:
      engine: postgresql
      host: db
      port: "{{ db_port }}"
      name: "{{ db_name }}"
      user: "{{ db_user }}"
      password: "{{ db_password }}"
      service: db
```

Provider values are rendered with the provider module's variables. Native Jinja rendering preserves integers, booleans, lists, and dictionaries.

Each module may provide a given capability only once.

## Requiring capabilities

A consumer declares its needs through `requires`:

```yaml
requires:
  - capability: database.connection
    binding: primary_database
    optional: false
    unique: true
    contract:
      engine: string
      host: string
      port: int
      name: string
      user: string
      password: string
      service: string
```

Fields:

- `capability`: capability identifier;
- `binding`: local name exposed to the consumer;
- `optional`: whether generation can continue without a provider;
- `unique`: whether exactly one provider is expected;
- `contract`: required provider fields and their types.

Supported contract types are:

- `string`;
- `int`;
- `boolean`;
- `list`.

If `unique` is `true`, the binding contains one provider value dictionary:

```jinja
{{ bindings.primary_database.host }}
```

If `unique` is `false`, the binding contains a list of provider value dictionaries.

Missing providers, ambiguous unique providers, and invalid contracts are rejected during resolution.

## Extension points

A module exposes typed locations that integration modules may extend:

```yaml
extension_points:
  python.dependencies:
    type: list
    merge: append_unique
    default: []

  database.backend:
    type: string
    merge: replace
    required: true
```

Supported extension-point types are:

- `string`;
- `int`;
- `boolean`;
- `list`;
- `dict`.

Supported merge strategies depend on the type:

| Type | Strategies |
|---|---|
| `string` | `replace` |
| `int` | `replace` |
| `boolean` | `replace` |
| `list` | `replace`, `append`, `append_unique` |
| `dict` | `replace`, `deep_merge` |

A required extension point must receive at least one contribution.

Final extension values are available to templates:

```jinja
{{ extensions["database.backend"] }}
```

## Contributions

A contribution targets a module through one of the contributor's bindings:

```yaml
contributions:
  - target: backend
    extension_point: python.dependencies
    value:
      - psycopg[binary]

  - target: backend
    extension_point: database.backend
    value: django.db.backends.postgresql
```

The target must match a binding declared in the same module.

Contribution values can use:

- contributor variables;
- `options`;
- `bindings`.

Example of a dynamic contribution:

```yaml
contributions:
  - target: backend
    extension_point: database.options
    value:
      engine: "{{ bindings.database.engine }}"
      port: "{{ bindings.database.port }}"
```

Contribution values cannot reference `extensions`, because extension values are produced only after all contributions have been collected.

Boilr validates the rendered value against the target extension-point type before applying its merge strategy.

## Integration modules

An integration module connects capabilities and contributions without generating technology-specific branches in the core engine.

Example:

```yaml
meta:
  name: Django PostgreSQL Integration
  key: django-postgres
  type: integration
  version: 1.0.0

role:
  group: integration

requires:
  - capability: backend.python
    binding: backend
    optional: false
    unique: true
    contract:
      runtime: string
      framework: string

  - capability: database.connection
    binding: database
    optional: false
    unique: true
    contract:
      engine: string
      host: string
      port: int
      name: string
      user: string
      password: string
      service: string

contributions:
  - target: backend
    extension_point: python.dependencies
    value:
      - psycopg[binary]

  - target: backend
    extension_point: database.backend
    value: django.db.backends.postgresql

assembly:
  priority: 200
  destination_root: .

sources:
  copy: []
  render: []
```

The dependency graph places providers before consumers and the integration module after the modules it connects.

## Dependencies

Python or runtime dependencies can be declared by feature:

```yaml
dependencies:
  base:
    - Django>=5.0,<6.0
    - gunicorn>=21.2.0

  rest_framework:
    - djangorestframework>=3.15.0
```

Templates can access the dependency structure through:

```jinja
{{ dependencies.base }}
```

Extension-point contributions can add dependencies supplied by integration modules.

## Copy sources

Copy operations support three strategies:

```yaml
sources:
  copy:
    - from: files/apps
      to: backend/apps
      strategy: merge
```

Strategies:

- `merge`: copy the source tree into the destination, overwrite matching source paths, and retain unrelated destination files;
- `skip`: if the destination exists, leave the entire destination unchanged;
- `replace`: remove the destination and recreate it from the source.

Replacement removals are part of the generation plan and must remain strictly inside the project output directory.

## Render sources

Templates are rendered with strict Jinja evaluation:

```yaml
sources:
  render:
    - from: files/templates/settings.py.j2
      to: backend/config/settings.py
```

The template context contains:

- module variables as top-level values;
- `options`;
- `dependencies`;
- `bindings`;
- `extensions`.

An undefined value produces a structured template-rendering error.

## Docker services

Modules can define Docker services and volumes:

```yaml
docker:
  services:
    backend:
      build:
        context: ./backend
        dockerfile: Dockerfile

      depends_on:
        - "{{ bindings.primary_database.service }}"

  volumes: {}
```

Docker values use the complete module rendering context. Services from different modules are merged into one Compose file. Conflicting definitions are rejected.

Boilr emits the modern Compose format without the obsolete top-level `version` attribute.

## Environment exports

Modules can export environment variables:

```yaml
exports:
  env:
    DB_HOST: "{{ bindings.primary_database.host }}"
    DB_PORT: "{{ bindings.primary_database.port }}"
```

Exports from all modules are rendered and merged into the generated `.env` file. Conflicting values are rejected.

## Assembly order

The `assembly` section provides a stable priority:

```yaml
assembly:
  priority: 100
  destination_root: backend
```

Capability bindings create the actual dependency graph. Priority is used only as a deterministic ordering hint when dependency constraints do not decide the order.

## Documentation metadata

Each module should describe its purpose:

```yaml
docs:
  summary: Reusable Django backend module
  notes:
    - Supports Django REST Framework
    - Supports typed database integrations
```

## Validation checklist

Before opening a pull request, verify:

- the module key is lowercase;
- all required variables have values or defaults;
- variable and option types are valid;
- provided capability values satisfy consumer contracts;
- binding names are unique within the module;
- contribution targets reference declared bindings;
- target extension points exist;
- contribution values match extension-point types;
- generated destinations do not conflict;
- copy removals remain inside the output directory;
- templates render without undefined values;
- Docker Compose validates successfully;
- tests and `git diff --check` pass.

Run:

```powershell
python -m ruff check boilr_generator tests
python -m pytest -q
git diff --check
```

## Core compatibility exports

Some historical exception import paths remain temporarily available for backward compatibility.

New code should import canonical exceptions from:

```python
from boilr_generator.exceptions import BoilrError
```

The compatibility exports may be removed in a future major release.