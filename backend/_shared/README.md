# backend/_shared

Canonical source for code shared across backend services.

Each Lambda is packaged **only from its own folder** (`backend/<service>/`), and
local hot-reload uploads that same folder — so shared code cannot be imported
from outside the service directory at runtime. Instead, the modules here are
**propagated into every backend service folder** by a build step.

## How it works

- Edit shared modules **only in this folder** (e.g. `postgres_service.py`).
- Run the sync to copy them into each Python service (any `backend/*/` folder
  with a `requirements.txt`, excluding `_`/`.`-prefixed folders):

  ```sh
  bin/sync-shared.sh
  ```

- The generated copies carry a `GENERATED FILE - DO NOT EDIT` header pointing
  back here. Never edit them by hand; re-run the sync instead.

The `_` prefix keeps this folder from being auto-discovered as its own Lambda
service (see `infra/locals.tf`).
