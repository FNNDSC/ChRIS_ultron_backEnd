# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

CUBE (ChRIS Ultron BackEnd) is the Django/DRF backend of the ChRIS medical-compute platform.
Stack: Django 6.0 (pinned `<6.1`), DRF, PostgreSQL 18, Celery (Dragonfly as the Redis-compatible
broker), django-channels + NATS for live PACS progress, uvicorn in production. The HTTP API at
`/api/v1/` speaks `application/vnd.collection+json` first, plain JSON second.

The Django project root is `chris_backend/` (bind-mounted into the container at
`/opt/app-root/src`). Everything else at the repo root is packaging, compose, CI, and the
`benchmarks/` harness (its own `pyproject.toml`/`uv.lock`, built from its own context).

## Commands

Everything runs in containers through `just`. Never call `docker compose` directly: the justfile
injects `UID`/`GID`, the engine socket, and the storage-override compose files.

```shell
just                      # = just dev: start services, migrate, register plugins/users (chrisomatic), attach
just up / just down       # (re)create / stop services; `just nuke` also wipes volumes and job containers
just build && just up     # required after changing Dockerfile, pyproject.toml, or uv.lock
just logs [service]

just test-unit            # manage.py test --exclude-tag integration
just test-integration     # manage.py test --tag integration (needs pfcon + plugin images)
just test-all
just test <label...>      # Django test labels, e.g. just test feeds.tests.test_views
                          #   or just test feeds.tests.test_views.FeedListViewTests.test_feed_list_success
just test-coverage        # full suite under coverage + report
just test-unit-coverage   # writes chris_backend/coverage.xml (what CI uploads to Codacy)

just shell / just bash    # Django shell / bash inside the chris container
just run <cmd>            # docker-compose run --rm chris <cmd>
just makemigrations / just migrate

just openapi > /dev/null        # CI fails on ANY drf-spectacular warning or error
just openapi-split > /dev/null  # same, with SPECTACULAR_SPLIT_REQUEST=true

just lock                 # re-resolve both uv.lock files after editing a pyproject.toml
just lock-upgrade <pkg>   # bump one dependency
just lock-check           # fails if a lockfile is stale (CI's first job; Dockerfile uses uv sync --locked)

just set-storage s3|swift|fslink   # persist storage mode (.storage); default fslink
just prefer docker|podman          # persist engine choice (.preference)
just dev-uvicorn          # serve via ASGI on :8000 (runserver is WSGI and cannot serve WebSockets)

just bench-start / bench-run --tier smoke / bench-test / bench-down   # benchmarks/ harness (pytest)
```

The dev API is at http://localhost:8000/api/v1/ (superuser `chris`/`chris1234`, user
`cube`/`cube1234`). `uv sync` on the host is only for editor/LSP support; tests need the stack.
pylint/flake8 are dev dependencies but there is no config file and no lint step in CI.

## Testing conventions

- Runner is Django's `manage.py test` (not pytest). Integration tests are marked
  `@tag('integration')`; they talk to the real pfcon service and run real plugin containers.
- Tests that exercise Celery use `TransactionTestCase` and start an in-process worker with
  `celery.contrib.testing.worker.start_worker(celery_app)` after setting
  `celery_app.conf.update(task_routes=None)`, so tasks land on the default `celery` queue, which
  is reserved for tests (see `core/celery.py`). `core/testrunner.py` terminates leftover DB
  connections so the test database can be dropped.
- `core.storage.helpers.mock_storage(target_settings)` swaps the storage backend for a temp
  directory. `core/tests/test_swiftmanager.py` and `test_s3manager.py` need the matching
  `just set-storage` environment.
- Test fixtures create users directly with `User.objects.create_user`; the `chris` superuser and
  root folders already exist because `core/apps.py` creates them on `post_migrate`.

## Architecture

### Settings and entry points
- `config/settings/common.py` holds app/DRF/spectacular config; `local.py` (dev, `DEBUG=True`,
  hard-coded service hostnames that match compose network aliases: `chris_dev_db`,
  `pfcon.remote`, `nats`, `dragonflydb`, `lldap`), `production.py` (everything via `get_secret`
  from env; missing vars raise `ImproperlyConfigured`), `benchmark.py` (local + env-driven DB
  pool). Both `local` and `production` verify the storage connection at import time.
- `manage.py` and `core/celery.py` default to `config.settings.local`; `config/asgi.py`
  defaults to `production`. The ASGI app routes HTTP to Django and WebSockets through
  `core/websockets/` (token-in-query-string auth).
- `config/urls.py` mounts `core.api` under `/api/`, the admin-only plugin/compute-resource API
  under `/chris-admin/api/v1/`, and the drf-spectacular schema views. `core/api.py` is the single
  URL table for every app's views; serializers' `HyperlinkedRelatedField`s reference its names.

### Collection+JSON API pattern
- Views are DRF generic views. Every list view overrides `list()` to append a `queries` block
  (derived from the sibling `.../search/` view's `FilterSet`) and a write `template` via
  `collectionjson.services`. `FilterSet`s live in each app's `models.py` next to the model.
- `collectionjson/renderers.py` turns hyperlinked fields into `links`; `core.middleware.
  ResponseMiddleware` renders unhandled exceptions as Collection+JSON 500s in production (re-raises
  under `DEBUG`).
- OpenAPI: `get_queryset` methods guard with `if getattr(self, "swagger_fake_view", False)`;
  schema fix-ups live in `*/spectacular_hooks.py` and are listed in `SPECTACULAR_SETTINGS`.
- Auth: DRF token (`/api/v1/auth-token/`), basic, and session. File downloads and WebSockets use
  short-lived `downloadtokens` (JWT signed with a key derived from `SECRET_KEY`, see
  `core/utils.py`) passed as `?token=`. The superuser named `chris` is special-cased everywhere
  (`core.permissions.IsOwnerOrChris`, `core.models.user_can_access_obj`).

### Virtual filesystem (`core/models.py`)
- `ChrisFolder` (unique `path`, parent chain auto-created on save), `ChrisFile` (`fname` is the
  storage key), and `ChrisLinkFile` (`.chrislink` pointing at another path). Each carries owner,
  `public`, and per-user/per-group `r`/`w` permission tables. `validate_path_access` is the single
  path-authorization rule; use it rather than re-deriving access.
- Roots created on `post_migrate`: `home`, `SHARED`, `PUBLIC`, `PIPELINES`, `SERVICES/PACS`.
  `users.models.UserProxy.save` builds `home/<user>/{uploads,feeds}` plus `public`/`shared`
  link files for every new user (also via `CustomLDAPBackend`). Groups `all_users` and
  `pacs_users` gate access.
- Subtypes are proxies/subclasses of `ChrisFile`: `UserFile` (`home/...`), `PACSFile`
  (`SERVICES/PACS/...`), `PipelineSourceFile`. The `filebrowser` app exposes the tree generically.
  `post_delete` receivers delete the storage object, so deleting a model row deletes bytes.
- Storage backends are behind `core.storage.StorageManager` (Swift, S3, filesystem) chosen by
  `STORAGE_ENV`; get one with `connect_storage(settings)`. Files are immutable (WORM).

### Feeds, plugin instances, and job orchestration
- A `Feed` is a DAG of `PluginInstance`s. Plugin types: `fs` (creates a feed), `ds` (one
  `previous`), `ts` (topological, multiple parents listed in its `plugininstances` string param).
  `PluginInstance.save` creates the feed and the output `ChrisFolder` at
  `home/<owner>/feeds/feed_<id>/<plugin>_<id>/.../data`; the folder is only null transiently.
- Status state machine in `plugininstances/enums.py` (`created → waiting → copying → scheduled →
  started → uploading → registeringFiles → finishedSuccessfully | finishedWithError |
  cancelled`). `plugininstances.utils.run_if_ready` decides whether a new instance runs now or
  waits on its parents; the `periodic` beat tasks in `plugininstances/tasks.py` advance waiting
  instances, poll running ones, and cancel stuck ones.
- Remote execution goes through pfcon via `plugininstances/services/`: `abstractjobs.
  PluginInstanceJob` handles auth-token refresh and job id prefixing; `PluginInstanceAppJob`,
  `CopyJob`, `UploadJob`, `DeleteJob` are the concrete flows. `ComputeResource` flags
  (`compute_innetwork`, `compute_requires_copy_job`, `compute_requires_upload_job`) select which
  jobs run. Post-terminal cleanup is tracked separately in `remote_cleanup_status`. Errors are
  logged and stored as `CODEnn` codes on the instance.
- Celery: queues `main1`, `main2`, `periodic` with explicit `task_routes` and the beat schedule in
  `core/celery.py` (`CUBE_CELERY_POLL_INTERVAL` env var). Compose runs `worker-mains`,
  `worker-periodic`, and `celery-scheduler` (django-celery-beat DatabaseScheduler).
- Deletion of feeds, folders, plugin instances, and PACS series is asynchronous:
  `AsyncDeletableModel.mark_deletion_pending()` then a `delete_*` task; the tasks are idempotent
  and record failures in `deletion_status`/`deletion_error`.

### Plugins, pipelines, workflows
- Plugins are registered from a ChRIS-store-style JSON representation through the
  `/chris-admin/api/v1/` API, the Django admin, or `plugins/services/manager.py` (CLI). In dev,
  chrisomatic (`chrisomatic/chrisomatic.yml`) registers the `host` compute resource, users, and
  the plugin list on every `just`. `chrisomatic/postscript.yml` is an optional larger set.
- `Pipeline` = template graph of `PluginPiping`s with default piping parameters; a `Workflow`
  instantiates it into plugin instances (`workflows/_types.py` resolves per-node overrides).
  `core/graph.py` provides the DAG/cycle checks. `plugins/fields.py` defines `CPUInt`/`MemoryInt`
  (values like `1000m`, `512Mi`).

### PACS and DICOMweb
- `pacsfiles`: `PACS`, `PACSQuery`/`PACSRetrieve` (sent to pfdcm via `pacsfiles/services.py`),
  `PACSSeries`, `PACSFile`. oxidicom writes files to storage and then calls the
  `register_pacs_series` Celery task. Retrieval progress is streamed from NATS using LONK
  (`pacsfiles/lonk.py`) over the WebSocket route `v1/pacs/ws/` and the SSE view `v1/pacs/sse/`.
- `dicomweb`: `PACSStudy` and `PACSInstance` index rows for QIDO-RS, populated at ingest by
  `dicomweb.tasks.index_pacs_instance`; study counters are maintained by signals with `F()`
  updates and rely on `pg_trgm` (threshold set per connection via `DATABASES OPTIONS`).

## Gotchas

- `pyproject.toml` constraints are lower bounds; `uv.lock` is the source of truth. Django is
  capped `<6.1` because django-celery-beat 2.9 requires it. After any pyproject change run
  `just lock` and commit the lockfile, otherwise CI and the image build fail.
- `chris_backend/__version__.py` is a placeholder that CI overwrites from the git tag; do not
  edit it by hand.
- The `README.md` "Documentation" section (Sphinx under `docs/`) is marked outdated upstream; the
  OpenAPI schema generated by `just openapi` is the current API reference.
- `docker-compose.yml` comments flag hostnames and ports that are hard-coded in
  `config/settings/local.py` and `chrisomatic/*.yml`; change them together.
