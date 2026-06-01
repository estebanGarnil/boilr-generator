# Contributing to Boilr

Thank you for your interest in contributing to Boilr.

## What is a Boilr Module?

A module is a reusable building block that contributes:

- files
- Docker services
- environment variables
- dependencies
- compatibility rules

Multiple modules are assembled together to generate a complete Dockerized application stack.

## The Goal

Boilr is a modular Docker-first project generator.

The core engine is responsible for:

* validating projects
* resolving dependencies
* generating Docker Compose stacks
* rendering templates

As a contributor, you **do not need to understand the generator internals**.

Most contributions only require knowledge of the technology you want to add.

If you know:

* React
* Vue
* Angular
* FastAPI
* Django
* PostgreSQL
* MongoDB
* Redis
* RabbitMQ
* Nginx

you can already contribute.

---


# How Can I Contribute?

Boilr is designed to be extended primarily through modules.

Most contributors will never need to modify the generator itself.

If you know how to build and Dockerize a technology such as React, Vue, Django, FastAPI, PostgreSQL or Redis, you can already make valuable contributions.

There are four main ways to contribute.

---

## 1. Create a New Module

This is currently the most valuable contribution.

A module represents a reusable building block that can contribute:

- files
- Docker services
- environment variables
- dependencies
- compatibility rules

Examples of modules:

- React
- Next.js
- Vue
- Angular
- FastAPI
- NestJS
- MongoDB
- RabbitMQ
- Elasticsearch
- Celery
- Traefik

Every new module expands the Boilr ecosystem and unlocks new project combinations.

For example:

```text
Django + PostgreSQL
```

or

```text
FastAPI + MongoDB + Redis
```

can be generated from independent modules.

---

## 2. Improve Existing Modules

You do not need to create a new module to contribute.

Improving existing modules is just as valuable.

Examples:

### Django

- improve Docker configuration
- improve project structure
- add optional features
- improve generated settings
- improve dependency management

### PostgreSQL

- improve initialization scripts
- improve Docker configuration
- improve exported variables

### Redis

- improve persistence options
- improve configuration defaults

### Any Module

- improve documentation
- fix bugs
- improve templates
- improve Docker services
- improve compatibility rules

---

## 3. Improve Documentation

Good documentation is essential for adoption.

Examples:

- tutorials
- getting started guides
- example manifests
- module documentation
- architecture documentation
- contribution guides

Documentation contributions are always welcome.

---

## 4. Advanced Contributions

Although most contributors only need to work on modules, improvements to the Boilr engine are also welcome.

Examples:

- validation improvements
- resolver improvements
- generation plan improvements
- Docker generation improvements
- CLI development
- API development
- frontend development
- testing infrastructure
- developer experience improvements

Current architecture:

```text
Manifest
    ↓
Validation
    ↓
Module Registry
    ↓
Resolver
    ↓
Generation Plan
    ↓
Project Generator
```

Before modifying core behavior, please open an issue to discuss the proposed change.

---

# Why Module Contributions Matter

Boilr's long-term goal is not simply to generate Django projects.

The goal is to provide a rich ecosystem of reusable Dockerized modules that can be assembled together to create complete application stacks.

The more modules available, the more powerful Boilr becomes.

For this reason, module contributions are currently the highest priority for the project.


# Module Structure

Every module follows the same structure:

```text
module_name/
├── module.yml
├── files/
└── docs/
```

Example:

```text
django/
├── module.yml
├── files/
└── docs/
```

---

# The module.yml File

The `module.yml` file is the heart of a module.

It describes:

* what the module is
* what it requires
* what it generates
* which Docker services it provides
* which files it contributes

The generator uses this file to understand how the module should be assembled.

---

# Example: Django Module

Below is a simplified example extracted from the Django module.

```yaml
meta:
  name: Django
  key: django
  type: backend

role:
  group: backend
  unique: true

requirements:
  mandatory:
    - type: database

compatibility:
  database:
    - postgres
    - mysql
```

This tells Boilr:

* this module is a backend
* only one backend may exist
* it requires a database
* it supports PostgreSQL and MySQL

---

# Meta

Identifies the module.

Example:

```yaml
meta:
  name: Django
  key: django
  type: backend
  version: 1.0.0
```

Required fields:

* name
* key
* type
* version

---

# Role

Defines how the module behaves inside a project.

Example:

```yaml
role:
  group: backend
  unique: true
```

Meaning:

* the module belongs to the backend group
* only one backend may be selected

---

# Requirements

Defines dependencies.

Example:

```yaml
requirements:
  mandatory:
    - type: database
```

The Django module cannot be used without a database module.

---

# Compatibility

Defines compatible modules.

Example:

```yaml
compatibility:
  database:
    - postgres
    - mysql

  cache:
    - redis

  proxy:
    - nginx
```

This means the Django module supports:

* PostgreSQL
* MySQL
* Redis
* Nginx

---

# Variables

Variables are values provided by the user.

Example:

```yaml
variables:
  project_name:
    type: string
    required: true

  backend_port:
    type: int
    required: true
    default: 8000
```

Supported types:

* string
* int
* boolean
* list

---

# Options

Options enable optional functionality.

Example:

```yaml
options:
  rest_framework:
    type: boolean
    default: true

  cors:
    type: boolean
    default: true
```

These options can activate additional dependencies and configuration.

---

# Sources

Sources define which files are generated.

Copy files:

```yaml
sources:
  copy:
    - from: files/apps
      to: backend/apps
```

Render templates:

```yaml
sources:
  render:
    - from: files/templates/manage.py.j2
      to: backend/manage.py
```

---

# Docker Services

Modules can contribute Docker services.

Example:

```yaml
docker:
  services:
    backend:
      build:
        context: ./backend
```

Boilr automatically merges all module services into a single Docker Compose stack.

---

# Environment Variables

Modules can export environment variables.

Example:

```yaml
exports:
  env:
    DJANGO_SECRET_KEY: "{{ secret_key }}"
```

All exported variables are automatically merged into the generated `.env` file.

---

# Documentation

Every module should include documentation.

At minimum:

```yaml
docs:
  summary: Reusable Django backend module
```

Recommended:

* purpose
* supported technologies
* dependencies
* variables
* options
* generated services

---

# Before Opening a Pull Request

Please ensure:

* the module loads correctly
* generated files are valid
* Docker services start correctly
* documentation is included

---

# Current Priority Modules

The following modules would have the biggest impact:

### Frontend

* React
* Next.js
* Vue
* Angular

### Backend

* FastAPI
* NestJS

### Databases

* MongoDB

### Infrastructure

* RabbitMQ
* Elasticsearch
* Traefik

---

# Final Note

Boilr is designed so contributors can extend the ecosystem without modifying the generator itself.

If you can create a Dockerized project manually, you can most likely create a Boilr module.
