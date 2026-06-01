# Contributing to Boilr Generator

Thank you for your interest in contributing to Boilr.

The project is currently looking for contributors to help expand the module ecosystem.

## What we need

The most valuable contribution today is the creation of new modules.

Examples:

* React
* Vue
* Angular
* FastAPI
* NestJS
* MongoDB
* RabbitMQ
* Elasticsearch
* Celery
* Traefik

---

## Creating a Module

Each module should follow the standard structure:

```text
module_name/
├── module.yml
├── files/
└── docs/
```

---

## Step 1 — Create the Module Manifest

Create a `module.yml` file describing the module.

Example:

```yaml
meta:
  name: React
  key: react
  type: frontend
  version: 1.0.0
  description: React frontend application

role:
  group: frontend
  unique: true
```

The manifest defines:

* module identity
* dependencies
* compatibility rules
* variables
* options
* Docker services
* exports

---

## Step 2 — Add Template Files

Place all template files inside:

```text
files/
```

These files will be copied or rendered during project generation.

---

## Step 3 — Write Documentation

Every module should contain documentation explaining:

### Description

What problem does the module solve?

### Requirements

Does it require another module?

Examples:

* PostgreSQL
* Redis
* Nginx

### Variables

Document all required variables.

Example:

```text
project_name
frontend_port
api_url
```

### Generated Services

Explain which Docker services are added to the generated stack.

---

## Step 4 — Add Tests

Every new feature must include tests.

Required:

* manifest validation tests
* resolver tests
* generation tests (if applicable)

---

## Pull Requests

Before opening a large pull request, please open an issue describing:

* the module you want to add
* the intended use case
* any dependencies

This helps avoid duplicated work.

---

## Current Goal

The current priority is building a rich ecosystem of reusable Dockerized modules.

Every new module makes Boilr more powerful.

Thank you for contributing.

## Creating Modules

Boilr is designed to be extended through modules.

See:

- CONTRIBUTING.md
- docs/creating-a-module.md

## A Note from the Maintainer

Boilr is currently maintained by a single developer.

The project already includes:

- a validation system
- a resolver
- a generation engine
- a dry-run system
- automated tests

The next challenge is growing the ecosystem.

If you are familiar with a technology that is not yet supported, creating or improving a module is one of the most impactful ways to help the project.