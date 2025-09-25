# ![ChRIS logo](./docs/assets/logo_chris.png) ChRIS\_ultron\_backEnd

[![Build](https://github.com/FNNDSC/ChRIS_ultron_backEnd/actions/workflows/ci.yml/badge.svg)](https://github.com/FNNDSC/ChRIS_ultron_backEnd/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/fnndsc/ChRIS_ultron_backEnd.svg)](./LICENSE)

_ChRIS_ is an open-source platform for containerized medical compute.

https://chrisproject.org/

## TL;DR

With [Docker Compose](https://docs.docker.com/compose/) and [just](https://just.systems/) installed, run

```shell
git clone https://github.com/FNNDSC/ChRIS_ultron_backEnd.git
cd ChRIS_ultron_backEnd
just
```

## Introduction

The _ChRIS_ backend, a.k.a. _ChRIS Ultron Backend_ or _**CUBE**_ for short,
is a component of the _ChRIS_ system. It is responsible for maintaining the database
of users, files, plugins, and pipelines.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://chrisproject.org/img/figures/ChRIS_architecture_dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="https://chrisproject.org/img/figures/ChRIS_architecture.svg">
  <img alt="Architecture diagram" src="https://chrisproject.org/img/figures/ChRIS_architecture.svg">
</picture>

Here lives the code of _CUBE_. It is a Django project using PostgreSQL and Celery.
The HTTP API primarily supports the [collection+json](http://amundsen.com/media-types/collection/) content-type.

## Development

Development is mainly supported on Linux. MacOS and WSL on Windows also work (because Docker Desktop is a Linux VM). You will need at least 8GM RAM, 20GB disk space, and a good internet connection.

Install Docker (version 27 or above) or Podman (version 5.2 or above), Docker Compose, and [just](https://github.com/casey/just?tab=readme-ov-file#installation).

<details>
<summary>
Docker Installation Instructions
</summary>

- For MacOS and Windows, see: https://docs.docker.com/get-started/get-docker/
- For Linux, see: https://docs.docker.com/engine/install/

> [!CAUTION]
> On **Linux**, the official Docker Documentation will try to trick you into installing "Docker Desktop." Do not install "Docker Desktop." Look for "Docker Engine" instead.

> [!CAUTION]
> On **Ubuntu**, make sure you follow the instructions here: https://docs.docker.com/engine/install/ubuntu/. If you do not follow the instructions, Ubuntu will try to install Docker using snap, which will cause many problems.

</details>

<details>
<summary>
Podman Setup Instructions
</summary>

Rootless Podman is supported. You must install and configure Podman to use `docker-compose`, _not_ `podman-compose`. `podman-compose` is missing features, see issues [#575](https://github.com/containers/podman-compose/issues/575) and [#866](https://github.com/containers/podman-compose/issues/866).

A Podman daemon must be running, because _ChRIS_ runs containers of its own. To start the Podman daemon on Linux, run

```shell
systemctl --user start podman.service
```

If both Podman and Docker are installed, Podman will be used by default. A preference to use either Podman or Docker can be set by running

```shell
just prefer podman  # or
just prefer docker
```

With Podman, RabbitMQ might fail to start. Simply retry the command. See https://github.com/FNNDSC/ChRIS_ultron_backEnd/issues/573

</details>

### Just Commands

Development is handled by [`just`](https://just.systems).
Running _CUBE_ in development mode is as-simple-as running the command

```shell
just
```

The first run of `just` will take 5-20 minutes because it needs to pull and build container images. Subsequent runs should only take 1-5 minutes.

_CUBE_ is now running at http://localhost:8000/api/v1/. You can click around in the web browser. Alternatively, check out [chrs](https://chrisproject.org/docs/chrs) and/or [ChRIS\_ui](https://github.com/FNNDSC/ChRIS_ui).

Run tests:

```shell
just test-all                       # run all tests
just test-unit                      # run unit tests
just test-integration               # run integration tests
just test feeds.tests.test_views    # run chris_backend/feeds/tests/test_views.py
```

Shut down and clean up:

```shell
just nuke
```

List all `just` commands:

```shell
just --list --unsorted
```

### Development Tips and Tricks

#### Recreate containers after changing `docker-compose.yml`

If you modify `docker-compose.yml`, you need to recreate/restart the affected services.

```shell
just up
```

#### Rebuild the image after changing package dependencies

If you modify `Dockerfile` or `requirements/*.txt`, you need to rebuild the image and recreate your containers.

```shell
just build && just up
```

#### Trying HTTP requests from the CLI

For CLI tools, I recommend [xh](https://github.com/ducaale/xh) and [jnv](https://github.com/ynqa/jnv) or [jq](https://jqlang.github.io/jq/). Example:

```shell
xh -a chris:chris1234 :8000/api/v1/ | jnv
```

#### Interactive shell

It is often easiest to debug things using a shell.

```shell
just bash    # run bash in a container
# -- or --
just shell   # run a Python REPL
```

In the Python REPL, you can import models and interact with them. Here is some common starter code:

```python
from django.conf import settings
from django.contrib.auth.models import User, Group
from plugins.models import *
from plugininstances.models import *
from core.storage import connect_storage

storage = connect_storage(settings)
```

### IDE Setup

Visual Studio Code and PyCharm both support using Docker containers to run the Python interpreter. Run `just build`, then point your IDE to use the container image `localhost/fnndsc/cube:dev`.

Not all text editors support using Docker, or configuring the LSP might be inconvenient. In these cases, you need to install Python and the dependencies on-the-metal.

#### Installing Python Dependencies On-The-Metal

The traditional but worst approach is to install Python 3.11, then run

```shell
python -m venv venv
source venv/bin/activate
pip install -r requirements/local.txt
```

Some dependencies (such as `python-ldap`) build C code during installation,
requiring `clang` to be installed. Alternatively, my recommendation is to use
`micromamba` to install Python 3.11 and `python-ldap`, then use `pip` to
install everything else.
[Install micromamba](https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html), then run

```shell
micromamba create -p ./.mambaenv -c conda-forge -y python=3.11 python-ldap=3.4
micromamba -p ./.mambaenv run pip install -r requirements/local.txt
```

Now the environment is ready. Activate the environment

```shell
micromamba activate -p ./.mambaenv
```

And you are ready to run your LSP + text editor.

### OpenAPI Compatibility

[drf-spectacular](https://drf-spectacular.readthedocs.io/) is used to generate an OpenAPI schema.
Generally, its introspection is capable and accurate, but some special care is necessary to make
everything work. See:

- https://github.com/FNNDSC/ChRIS_ultron_backEnd/pull/584
- https://github.com/tfranzel/drf-spectacular/issues/1303#issuecomment-2387220962
- https://drf-spectacular.readthedocs.io/en/latest/faq.html#my-get-queryset-depends-on-some-attributes-not-available-at-schema-generation-time

Be sure to lint your OpenAPI annotations for errors and warnings by running:

```shell
just openapi > /dev/null
just openapi-split > /dev/null
```

## Production Deployment

See https://chrisproject.org/docs/run/helm

## GitHub Actions

This repository can also be used as a GitHub Actions step for running _CUBE_ integration tests, e.g.

```yaml
name: CI

on:
  push:
    branches: [ master ]
  pull_request:
    branches: [ master ]

jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - name: Run ChRIS backend integration tests
        uses: FNNDSC/ChRIS_ultron_backEnd@master
        # all inputs are optional
        with:
          engine: docker  # or podman
          command: test-integration  # or test-unit, ...
        # optionally change image used for pfcon, or cube
        env:
          CUBE_IMAGE: localhost/fnndsc/cube:dev
          PFCON_IMAGE: localhost/fnndsc/pfcon:dev
```

## Documentation

> [!CAUTION]
> Everything below in this section is outdated.

#### REST API reference

Available [here](https://fnndsc.github.io/ChRIS_ultron_backEnd).

Install Sphinx and the http extension (useful to document the REST API)
```
pip install Sphinx
pip install sphinxcontrib-httpdomain
```

Build the html documentation
```
cd docs/
make html
```

#### ChRIS REST API design.

Available [here](https://github.com/FNNDSC/ChRIS_ultron_backEnd/wiki/ChRIS-REST-API-design).

#### ChRIS backend database design.

Available [here](https://github.com/FNNDSC/ChRIS_ultron_backEnd/wiki/ChRIS-backend-database-design).
