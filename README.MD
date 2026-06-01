# Boilr Generator

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

The engine validates, resolves and assembles the final stack automatically.

The generated project is designed to run immediately using Docker Compose.

```
```


## Architecture

```text
project.yml / API JSON
        ↓
ProjectManifest
        ↓
Validation
        ↓
ModuleRegistry
        ↓
Resolver
        ↓
ResolvedProject
        ↓
GenerationPlan
        ↓
ProjectGenerator
        ↓
Generated Project
```

### Manifest

Defines the desired project.

Example:

```yaml
project:
  name: my_app
  type: fullstack_web
  version: "1.0.0"

modules:
  - key: postgres

  - key: django
```

---

### Validation

Before generation, Boilr validates:

* module existence
* required variables
* variable types
* unknown variables
* module compatibility
* module requirements

---

### Resolver

The resolver builds the final project structure.

Responsibilities:

* dependency resolution
* compatibility checks
* module ordering
* variable aggregation

---

### Generation Plan

Before generating files, Boilr can produce a complete generation plan.

The plan includes:

* files to create
* files to overwrite
* generated Docker services
* generated environment variables

This enables dry-run previews and future frontend integrations.

---

### Generation

The generator executes the plan and creates:

* project files
* Docker Compose configuration
* environment variables
* rendered templates

---

## Example

### Input

```yaml
project:
  name: blog

modules:
  - key: postgres

  - key: django
```

### Output

```text
blog/
├── backend/
├── docker-compose.yml
└── .env
```

---

## Features

* Modular architecture
* YAML / JSON manifests
* Docker-first project generation
* Docker Compose generation
* Environment generation
* Validation system
* Dependency resolution
* Compatibility checks
* Dry-run support
* Template rendering
* Fully tested

```
```


---

## Current Modules

### Backend

* Django

### Database

* PostgreSQL
* MySQL

### Cache

* Redis

More modules are planned.

---

## Roadmap

### Core Engine

* [x] Manifest system
* [x] Module registry
* [x] Validation system
* [x] Resolver
* [x] Generation plan
* [x] Project generation

### Platform

* [ ] Django API
* [ ] CLI
* [ ] Web Interface
* [ ] Module marketplace

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

## License

MIT License

```
```
