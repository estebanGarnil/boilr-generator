# Boilr Generator

[![CI](https://github.com/estebanGarnil/boilr-generator/actions/workflows/ci.yml/badge.svg)](https://github.com/estebanGarnil/boilr-generator/actions/workflows/ci.yml)
[![Docker E2E](https://github.com/estebanGarnil/boilr-generator/actions/workflows/docker-e2e.yml/badge.svg)](https://github.com/estebanGarnil/boilr-generator/actions/workflows/docker-e2e.yml)

Boilr Generator is a modular scaffolding engine for assembling complete Dockerized application stacks from declarative YAML or JSON manifests.

Instead of maintaining one template for every technology combination, Boilr composes reusable modules. The current built-in stack combines Django, PostgreSQL, and Redis through explicit integration modules.

> Boilr is currently maintained by a single contributor and is under active pre-1.0 development.

## Features

- Declarative project manifests
- Reusable backend, database, cache, and integration modules
- Typed capabilities, requirements, and bindings
- Provider selection by module, PEP 440 version constraint, and tags
- Deterministic dependency resolution and cycle detection
- Typed extension points and contributions
- Complete generation plans before filesystem mutation
- Immutable dry runs with human-readable and JSON output
- Create, overwrite, skip, clean, and replace operations
- SHA-256 fingerprints and content sizes for planned files
- Safe path boundaries and structured diagnostics
- Docker Compose and environment-file generation
- Linux and Windows support on Python 3.11 through 3.14
- Wheel and source-distribution verification in CI
- Real Docker E2E coverage for Django, PostgreSQL, and Redis

## Installation

Boilr requires Python 3.11 or newer.

### Install from the repository

Clone the repository, create a virtual environment, and install the package:

~~~bash
git clone https://github.com/estebanGarnil/boilr-generator.git
cd boilr-generator
python -m venv .venv
~~~

Activate the environment on Linux or macOS:

~~~bash
source .venv/bin/activate
~~~

Activate it in Windows PowerShell:

~~~powershell
.venv\Scripts\Activate.ps1
~~~

Install Boilr:

~~~bash
python -m pip install .
~~~

The installation exposes the `boilr` command. The module entry point remains available as `python -m boilr_generator.cli`.

### Development installation

Install the package with its development dependencies:

~~~bash
python -m pip install -e ".[dev]"
~~~

## Quick start

Create a `project.yml` manifest:

~~~yaml
project:
  name: my_app
  type: fullstack_web
  version: 1.0.0

modules:
  - key: postgres
    variables:
      db_name: my_app
      db_user: my_app
      db_password: change-me
      db_port: 5432

  - key: redis
    variables:
      redis_host_port: 6379
      redis_database: 0

  - key: django
    variables:
      project_name: my_app
      django_settings_module: config.settings.local
      backend_port: 8000
      secret_key: change-me
      debug: true
      allowed_hosts:
        - localhost
        - 127.0.0.1
    options:
      rest_framework: true
      cors: true

  - key: django-postgres
  - key: django-redis
~~~

Preview every planned operation without writing anything:

~~~bash
boilr dry-run project.yml generated-project --info
~~~

Generate the project:

~~~bash
boilr generate project.yml generated-project --info
~~~

Start the generated stack:

~~~bash
cd generated-project
docker compose up --build
~~~

The resulting Compose stack contains three services:

- `backend`: Django
- `db`: PostgreSQL
- `redis`: Redis

The integration modules also add:

- `psycopg[binary]` and the PostgreSQL Django backend
- `django-redis` and the Django `CACHES` configuration

The credentials in this example are intended only for local development. Replace them before using a generated project in another environment.

## Project manifest

A manifest contains project metadata and an ordered list of selected modules.

~~~yaml
project:
  name: my_app
  type: fullstack_web
  version: 1.0.0

modules:
  - key: postgres
    variables:
      db_name: my_app
      db_user: my_app
      db_password: change-me
    options: {}
~~~

### Project metadata

| Field | Description |
| --- | --- |
| `name` | Project name |
| `type` | Project category used by the caller |
| `version` | Project version |

### Module inputs

Each module selection accepts:

| Field | Description |
| --- | --- |
| `key` | Built-in or registered module key |
| `variables` | Values declared by the module's variable schema |
| `options` | Optional feature switches declared by the module |
| `bindings` | Optional provider-selection criteria for named requirements |

Unknown modules, variables, and options are rejected. Required values and declared types are validated before resolution.

### Provider selection

When a capability has several possible providers, the consumer can select one through the requirement's binding name:

~~~yaml
modules:
  - key: django
    bindings:
      primary_database:
        provider: postgres
        version: ">=1,<2"
        tags:
          - database
          - sql
~~~

The available criteria are:

| Criterion | Meaning |
| --- | --- |
| `provider` | Exact provider module key |
| `version` | PEP 440 version specifier matched against the provider module version |
| `tags` | Tags that must all be present on the provider |

Criteria are combined with logical AND. A direct selection must contain at least one criterion.

If no provider matches, Boilr raises a structured provider-selection error. If a unique requirement still matches multiple providers, Boilr reports the remaining candidates as ambiguous.

## Built-in modules

| Key | Type | Contract |
| --- | --- | --- |
| `django` | Backend | Provides `backend.python`, requires one `database.connection` |
| `postgres` | Database | Provides `database.connection` and the `db` service |
| `redis` | Cache | Provides `cache.connection` and the `redis` service |
| `django-postgres` | Integration | Connects the Python backend to PostgreSQL |
| `django-redis` | Integration | Connects Django to Redis |

### Django

Required variables:

| Variable | Type | Default |
| --- | --- | --- |
| `project_name` | string | none |
| `django_settings_module` | string | `config.settings.local` |
| `backend_port` | integer | `8000` |
| `secret_key` | string | none |
| `debug` | boolean | `true` |
| `allowed_hosts` | list | `localhost`, `127.0.0.1` |

Options:

| Option | Type | Default |
| --- | --- | --- |
| `rest_framework` | boolean | `true` |
| `cors` | boolean | `true` |

### PostgreSQL

| Variable | Type | Default |
| --- | --- | --- |
| `db_name` | string | none |
| `db_user` | string | none |
| `db_password` | string | none |
| `db_port` | integer | `5432` |

### Redis

| Variable | Type | Default |
| --- | --- | --- |
| `redis_host_port` | integer | `6379` |
| `redis_database` | integer | `0` |

## Command-line interface

~~~text
boilr [OPTIONS] COMMAND [ARGS]...
~~~

Available commands:

| Command | Description |
| --- | --- |
| `dry-run` | Build and display a generation plan without mutating the output |
| `generate` | Build a plan and execute it |

### Preview a generation

~~~text
boilr dry-run [OPTIONS] MANIFEST_PATH OUTPUT_PATH
~~~

Options:

| Option | Description |
| --- | --- |
| `--info` | Show the detailed human-readable plan |
| `--json` | Print the complete serialized plan |
| `--clean` | Preview cleanup of the output directory |
| `--debug` | Show the complete traceback when an error occurs |

Even with `--clean`, a dry run does not create, overwrite, remove, or change permissions on any path.

Example:

~~~bash
boilr dry-run project.yml generated-project --clean --json
~~~

### Generate a project

~~~text
boilr generate [OPTIONS] MANIFEST_PATH OUTPUT_PATH
~~~

Options:

| Option | Description |
| --- | --- |
| `--info` | Show the generation plan before writing |
| `--clean` | Plan cleanup before generation |
| `--debug` | Show the complete traceback when an error occurs |

Example:

~~~bash
boilr generate project.yml generated-project --clean --info
~~~

## Dry-run JSON contract

The JSON representation contains metadata rather than complete file contents:

| Field | Description |
| --- | --- |
| `resolved_project` | Project metadata and resolved module order |
| `output_path` | Absolute destination path |
| `initial_output_state` | Filesystem snapshot used to protect plan execution |
| `directories` | Directories that execution must create |
| `files` | Complete file operations without embedded content bytes |
| `removals` | Exact clean or replace removals |
| `docker_services` | Generated Compose service names |
| `env_variables` | Generated environment-variable names |
| `clean_output` | Whether cleanup was requested |
| `summary` | Stable operation counters and byte totals |

Each planned file includes:

~~~json
{
  "source_path": "/absolute/source/path",
  "destination_path": "/absolute/output/backend/manage.py",
  "relative_destination_path": "backend/manage.py",
  "operation": "render",
  "action": "create",
  "module": "django",
  "mode": 438,
  "content_size": 684,
  "content_sha256": "..."
}
~~~

Possible file actions are `create`, `overwrite`, and `skip`.

The summary reports:

- selected module count
- captured initial paths
- directories to create
- files to create, overwrite, or skip
- clean and replace removal counts
- Docker service and environment-variable counts
- total prepared bytes and bytes that execution would write

## Resolution model

### Capabilities and bindings

Modules communicate through typed capabilities.

A provider exposes values:

~~~yaml
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
~~~

A consumer declares a named requirement:

~~~yaml
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
~~~

The resolver validates the provider values against the requirement contract and exposes the result to templates as a typed binding:

~~~jinja
{{ bindings.primary_database.host }}
{{ bindings.primary_database.port }}
{{ bindings.primary_database.service }}
~~~

When `unique` is false, the binding contains a list of matching providers.

### Dependency graph

Bindings create dependency edges. Boilr uses the resulting graph to:

- order modules deterministically
- assemble providers before consumers
- place integration modules after the modules they connect
- reject dependency cycles

## Extension points and contributions

A consumer can expose typed extension points:

~~~yaml
extension_points:
  python.dependencies:
    type: list
    merge: append_unique
    default: []

  django.settings:
    type: dict
    merge: deep_merge
    default: {}

  database.backend:
    type: string
    merge: replace
    required: true
~~~

An integration module contributes through a declared binding:

~~~yaml
contributions:
  - target: backend
    extension_point: python.dependencies
    value:
      - django-redis>=7.0,<8.0

  - target: backend
    extension_point: django.settings
    value:
      CACHES:
        default:
          BACKEND: django_redis.cache.RedisCache
          LOCATION: "{{ bindings.cache.url }}"
~~~

Supported merge strategies:

| Value type | Strategies |
| --- | --- |
| Scalar | `replace` |
| List | `replace`, `append`, `append_unique` |
| Dictionary | `replace`, `deep_merge` |

Required extension points must receive a contribution. Incompatible contributions and duplicate replacements are reported before generation.

## Planning and execution

Boilr separates generation into two phases:

~~~text
manifest
   |
   v
validation and resolution
   |
   v
GenerationPlan
   |
   v
execute(plan)
   |
   v
generated project
~~~

### Planning

Planning performs:

- manifest and module-input validation
- capability resolution and provider selection
- contribution merging
- dependency ordering
- template rendering
- copy-strategy resolution
- Docker Compose generation
- environment generation
- collision detection
- output-state capture

It returns a complete `GenerationPlan` without mutating the filesystem.

### Execution

Execution applies only the prepared plan. It does not resolve modules, rerender templates, or regenerate Docker and environment configuration.

Before writing, execution verifies the captured initial output state. A stale or externally modified plan is rejected.

This separation provides two guarantees:

1. A successful dry run describes every mutation that execution would perform.
2. Executing an unchanged plan writes the exact prepared bytes and applies the planned removals and modes.

### Copy strategies

| Strategy | Behavior |
| --- | --- |
| `merge` | Merge the source tree; source files replace matching destinations while unrelated destinations remain |
| `skip` | Leave an existing destination tree unchanged |
| `replace` | Remove the destination safely, then recreate it from the source |

Replace and clean removals are restricted to paths inside the project output directory.

## Diagnostics and safety

All expected failures derive from `BoilrError` and expose structured context such as:

- a stable error code
- a human-readable message
- the affected module
- the manifest or generation field path
- machine-readable context
- an optional remediation suggestion

Boilr validates or protects:

- manifest structure
- duplicate and unknown modules
- unknown variables and options
- required values and input types
- provider versions and tag criteria
- missing and ambiguous capabilities
- binding contracts
- dependency cycles
- extension-point targets, types, and conflicts
- template rendering
- generated file collisions
- environment-variable names and values
- source reads and output writes
- output, clean, and replacement path boundaries
- symbolic links and unsupported filesystem entries
- stale generation plans

Use `--debug` to include the complete traceback for unexpected failures. Without it, the CLI renders the structured Boilr diagnostic.

Canonical exceptions are exported from:

~~~python
from boilr_generator.exceptions import BoilrError
~~~

Compatibility exports from older exception modules remain available temporarily, but new code should use the canonical module.

## Internal architecture

~~~text
project.yml
    |
    v
ProjectManifest
    |
    v
ModuleRegistry
    |
    v
Resolver
    |-- capabilities and requirements
    |-- provider selections
    |-- typed bindings
    |-- dependency graph
    |-- extension points
    â””â”€â”€ contributions
    |
    v
ResolvedProject
    |
    v
GenerationPlan
    |
    v
ProjectGenerator.execute(plan)
    |
    v
Generated project
~~~

Technology-specific behavior belongs in modules and integrations. The resolver and generation engine remain framework-agnostic.

## Creating a module

Built-in modules are stored by category:

~~~text
boilr_generator/templates/
|-- backend/
|   â””â”€â”€ django/
|-- database/
|   â””â”€â”€ postgres/
|-- cache/
|   â””â”€â”€ redis/
â””â”€â”€ integration/
    |-- django-postgres/
    â””â”€â”€ django-redis/
~~~

A module contains a `module.yml` manifest and optional source files:

~~~text
module/
|-- module.yml
â””â”€â”€ files/
~~~

The module manifest can define:

| Section | Purpose |
| --- | --- |
| `meta` | Name, key, type, version, description, and tags |
| `role` | Module role group |
| `dependencies` | Base and optional generated dependencies |
| `provides` | Capabilities exposed by the module |
| `requires` | Named capability requirements and contracts |
| `extension_points` | Typed contribution targets |
| `contributions` | Values contributed through bindings |
| `variables` | Required and defaulted module variables |
| `options` | Optional module features |
| `assembly` | Priority and destination root |
| `sources.copy` | File trees copied with a declared strategy |
| `sources.render` | Jinja templates and destinations |
| `docker` | Compose services and volumes |
| `exports.env` | Generated environment variables |
| `docs` | Inline module summary and notes |

Integration modules often have no source files. They connect other modules by requiring their capabilities and contributing dependencies or configuration through extension points.

When adding a module:

1. keep technology-specific decisions outside the core engine
2. declare all variables, options, and capability contracts
3. use an integration module for cross-technology behavior
4. add resolver, generation, and conflict tests
5. add a real Docker E2E scenario when practical

Open an issue before starting a large module contribution.

## Development and testing

Install development dependencies:

~~~bash
python -m pip install -e ".[dev]"
~~~

Run the complete test suite:

~~~bash
python -m pytest -q
~~~

Run Ruff:

~~~bash
python -m ruff check .
~~~

Build the wheel and source distribution:

~~~bash
python -m build
~~~

Run the Docker E2E test on Linux or macOS:

~~~bash
BOILR_RUN_DOCKER_E2E=1 python -m pytest -q tests/e2e/test_docker_stack.py -m docker_e2e -W error
~~~

Run it in Windows PowerShell:

~~~powershell
$env:BOILR_RUN_DOCKER_E2E = "1"
python -m pytest -q tests\e2e\test_docker_stack.py -m docker_e2e -W error
Remove-Item Env:BOILR_RUN_DOCKER_E2E
~~~

CI validates:

- Python 3.11, 3.12, 3.13, and 3.14
- Ubuntu and Windows
- the complete test suite
- Ruff
- wheel and source-distribution contents
- installation of the wheel outside the source tree
- built-in module discovery from the installed wheel
- generation from the installed package
- a real Django, PostgreSQL, and Redis Docker stack

## Project status and roadmap

Version 0.1.0 is functional and under active development.

The current engine supports:

- strict manifest and module-input validation
- declarative capability resolution
- advanced provider selection
- typed contributions
- deterministic and exhaustive planning
- safe plan execution
- Dockerized Django, PostgreSQL, and Redis generation
- cross-platform CI and distribution verification

Potential future work includes:

- a Django API around the generator
- a web interface
- a module marketplace
- additional backend and frontend modules
- MySQL, MongoDB, and message-queue providers
- reverse-proxy and deployment modules

## Contributing

Contributions are welcome. See [CONTRIBUTING.MD](CONTRIBUTING.MD) for development and contribution guidance.

Useful contributions include:

- new modules and integrations
- examples
- documentation
- cross-platform tests
- diagnostics and safety improvements

## Why Boilr exists

Modern projects repeatedly need the same foundations: an application framework, database, cache, environment configuration, containers, and service orchestration.

Maintaining a full template for every possible combination does not scale. Boilr instead treats each technology as a reusable module and each cross-technology decision as an explicit integration.

The long-term goal is an interface-agnostic ecosystem in which a CLI, API, web application, or automation can produce the same manifest and rely on the same deterministic generator core.

## License

Boilr is distributed under the [MIT License](LICENSE).
