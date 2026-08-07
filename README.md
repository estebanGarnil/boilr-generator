# Boilr Generator

> 🚧 Currently developed and maintained by a single contributor.

Boilr Generator is a modular project scaffolding engine designed to generate complete dockerized application stacks from reusable modules.

Instead of maintaining dozens of project templates, Boilr allows you to describe a project using YAML or JSON and generate a complete, ready-to-run application structure.

The core engine is framework-agnostic and can be used from:

* a CLI
* a backend API
* a web frontend
* custom integrations

---

## Why Boilr?

Modern applications rarely consist of a single framework.

A production-ready project often requires:

* an application framework
* a database
* a cache
* environment variables
* Docker configuration
* service orchestration

Boilr is designed to generate complete Dockerized application stacks from reusable modules.

Instead of maintaining dozens of project templates, a project is assembled from independent modules:

```text
Django
+
PostgreSQL
+
Redis
+
Nginx
```

For example, a user could generate:

- Django + PostgreSQL
- FastAPI + MongoDB
- NestJS + Redis + RabbitMQ
- React + FastAPI + PostgreSQL

without maintaining separate project templates.

The engine validates, resolves and assembles the final stack automatically.

The generated project is designed to run immediately using Docker Compose.

## Vision

Boilr aims to become a modular ecosystem for building complete Dockerized application stacks.

The long-term goal is to allow developers to assemble projects from reusable modules through:

- a CLI
- a backend API
- a web interface

Rather than maintaining hundreds of project templates, contributors can build reusable modules that work together across the ecosystem.

## Philosophy

Boilr is intentionally interface-agnostic.

The project manifest is the contract between the user interface and the generator core.

The manifest may be produced by:
- a CLI
- a web interface
- a backend API
- automation tools

Boilr only focuses on validation, resolution and generation.
You can build your own CLI, web app, SaaS interface, or internal automation tool on top of Boilr.

```
CLI / Web UI / API / Automation
                ↓
            manifest
                ↓
       Boilr Generator Core
                ↓
       Generated Application
```


## Why I Started Boilr

Like many developers, I found myself rebuilding the same foundations over and over again:

a backend, a database, Docker configuration, environment variables, and deployment setup.

At first, project templates seemed like the obvious solution. But as the number of projects and technologies grew, maintaining those templates became more difficult than maintaining the projects themselves.

Boilr was born from a simple idea:

instead of maintaining reusable projects, maintain reusable modules that can be assembled together to create complete Dockerized application stacks.

## Architecture

```text
project.yml
    ->
ProjectManifest
    ->
ModuleRegistry
    ->
Resolver
    |- capability providers
    |- capability requirements
    |- typed bindings
    |- dependency graph
    |- extension points
    `- contributions
    ->
ResolvedProject
    ->
GenerationPlan
    ->
ProjectGenerator.execute(plan)
    ->
Generated Project
```

The resolver is declarative: modules describe what they provide, what they consume, and how they contribute to other modules. Technology-specific decisions belong in integration modules rather than in the core engine.

### Manifest

A project manifest selects modules and supplies their variables and options.

```yaml
project:
  name: my_app
  type: fullstack_web
  version: "1.0.0"

modules:
  - key: postgres
    variables:
      db_name: my_app
      db_user: my_app
      db_password: password

  - key: django
    variables:
      project_name: my_app
      secret_key: dev-secret

    options:
      rest_framework: true
      cors: true

  - key: django-postgres
```

### Validation

Before generation, Boilr validates:

- requested module existence;
- required variables and their types;
- option types;
- capability contracts;
- missing or ambiguous capability providers;
- dependency cycles;
- contribution targets and value types;
- extension-point merge conflicts;
- generated file conflicts;
- copy strategies and planned removal safety.

### Capabilities and bindings

Modules communicate through typed capabilities.

A provider exposes a capability and its values:

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

A consumer declares the capability it needs:

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

The resolver matches providers to consumers and creates typed bindings. Templates can access them through Jinja:

```jinja
{{ bindings.primary_database.host }}
{{ bindings.primary_database.port }}
{{ bindings.primary_database.service }}
```

When `unique` is `false`, the binding contains a list of matching provider values.

### Extension points and contributions

A module can expose typed extension points:

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

Integration modules contribute through one of their declared bindings:

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

Contribution values can use the contributor's variables, options, and bindings. Rendering uses native Jinja values, so integers, booleans, lists, and dictionaries keep their types.

Supported extension-point merge strategies are:

- scalar values: `replace`;
- lists: `replace`, `append`, `append_unique`;
- dictionaries: `replace`, `deep_merge`.

Required extension points must receive at least one contribution.

### Dependency graph

Capability bindings create dependency edges between modules. Boilr uses this graph to:

- order modules deterministically;
- ensure providers are assembled before consumers;
- place integration modules after the modules they connect;
- reject dependency cycles.

### Generation Plan

Before writing anything, Boilr creates a complete and inspectable `GenerationPlan`.

The plan contains:

- the resolved project;
- every destination path;
- final file contents as bytes;
- create, overwrite, or skip actions;
- SHA-256 fingerprints and content sizes;
- Docker services and environment-variable names;
- planned removals;
- the `clean_output` decision.

Planning performs template rendering, Docker generation, environment generation, collision detection, and copy-strategy resolution.

`execute(plan)` applies only the prepared plan. It does not resolve modules or regenerate file contents. This guarantees that a successful preview represents the execution that follows.

Use `--info` to display the plan:

```powershell
python -m boilr_generator.cli generate `
    project.yml `
    generated-project `
    --info
```

### Copy strategies

Copy sources support three strategies:

- `merge`: combine the source tree with the destination. Source files overwrite files at the same paths, while unrelated destination files remain;
- `skip`: if the destination exists, leave the complete destination unchanged;
- `replace`: plan removal of the destination, then create it again from the source.

Example:

```yaml
sources:
  copy:
    - from: files/apps
      to: backend/apps
      strategy: merge
```

Planned removals are restricted to paths strictly inside the project output directory.

### Generation

The generator applies the plan and creates:

- copied module files;
- rendered templates;
- Docker Compose configuration;
- the project `.env` file.

With `--clean`, output cleanup becomes part of the plan and all resulting files are planned as creations.

---

## Example

### Input

```yaml
project:
  name: blog
  type: fullstack_web
  version: "1.0.0"

modules:
  - key: postgres
    variables:
      db_name: blog
      db_user: blog
      db_password: password

  - key: django
    variables:
      project_name: blog
      secret_key: dev-secret

  - key: django-postgres
```

### Output

```text
blog/
|-- backend/
|   |-- apps/
|   |-- config/
|   |-- Dockerfile
|   |-- manage.py
|   `-- requirements.txt
|-- docker-compose.yml
`-- .env
```

The Django/PostgreSQL integration contributes:

- `psycopg[binary]` to `backend/requirements.txt`;
- `django.db.backends.postgresql` to Django settings.

---

## Features

- Declarative modular architecture
- YAML and JSON project manifests
- Typed capability providers and requirements
- Automatic capability bindings
- Deterministic dependency graph
- Cycle detection
- Typed extension points and contributions
- Dynamic native-Jinja contributions
- Explicit contribution conflict detection
- Complete deterministic generation plans
- Dry-run plan previews
- Safe copy strategies
- Docker Compose generation
- Environment generation
- Strict template rendering
- Structured diagnostics
- Fully tested core engine

---

## Current Modules

### Backend

- Django

### Database

- PostgreSQL

### Integrations

- Django + PostgreSQL

More modules are planned.

---

## Project Status

Boilr is under active development.

The core engine can resolve declarative module contracts, assemble integration contributions, build deterministic generation plans, and generate a complete Dockerized Django/PostgreSQL project.

The public exception compatibility exports are temporarily preserved to avoid breaking existing imports. New code should import canonical exceptions from:

```python
from boilr_generator.exceptions import BoilrError
```

---

## Roadmap

### Core Engine

- [x] Manifest system
- [x] Module registry
- [x] Typed capabilities
- [x] Capability bindings
- [x] Dependency graph and cycle detection
- [x] Typed extension points
- [x] Dynamic contributions
- [x] Deterministic generation plan
- [x] Safe copy strategies
- [x] Project generation
- [x] CLI

### Platform

- [ ] Django API
- [ ] Web interface
- [ ] Module marketplace

### Ecosystem

- [ ] React module
- [ ] Vue module
- [ ] FastAPI module
- [ ] MySQL integration
- [ ] MongoDB module
- [ ] Redis module
- [ ] RabbitMQ module

---


## Contributing

Contributions are welcome.

The project currently needs help with:

* new modules
* module documentation
* example manifests
* testing
* CLI development
* frontend development

### Creating a module

Each module contains:

```text
module/
├── module.yml
├── files/
└── docs/
```

Example categories:

* FastAPI
* Next.js
* React
* Vue
* MongoDB
* RabbitMQ
* Elasticsearch
* Celery
* Traefik

If you would like to contribute a module, please open an issue before starting implementation.

---

## Testing

Run all tests:

```bash
pytest
```

Current test coverage includes:

* manifest validation
* module loading
* resolver behavior
* generation plan
* file generation

---

## About the Project

Boilr is currently developed and maintained by a single contributor.

The project started as an exploration of a simple question:

How can we generate complete Dockerized application stacks without maintaining dozens of independent templates?

Today, the core engine is functional and tested, but the ecosystem is still in its early stages.

Contributions are highly appreciated, whether through:

- new modules
- improvements to existing modules
- documentation
- testing
- engine improvements

If the project interests you, don't hesitate to open an issue or start a discussion.

## License

MIT License

