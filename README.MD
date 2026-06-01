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

The `project.yml` file is the contract between the user interface and the generator core.
You can build your own CLI, web app, SaaS interface, or internal automation tool on top of Boilr.

```
CLI / Web UI / API / Automation
                ↓
          project.yml
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
│   ├── manage.py
│   ├── requirements.txt
│   └── config/
│
├── docker-compose.yml
├── .env
└── README.md
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

## Project Status

Boilr is currently under active development.

The core generation engine is functional, tested and already capable of generating complete Dockerized application stacks.

Current focus areas:

- Django API
- CLI
- Module ecosystem growth
- Frontend interface


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

### Ecosystem

- [ ] React module
- [ ] Vue module
- [ ] FastAPI module
- [ ] MongoDB module
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

