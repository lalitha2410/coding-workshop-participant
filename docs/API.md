# LoadBalance API Reference

Complete reference for the ACME **LoadBalance** backend — five independent Lambda
services: **auth**, **projects**, **deliverables**, **resources**, **allocations**.

All example requests and responses in this document were **captured from the
running deployed services** with a seeded admin token — they are real, not
invented.

- [Base URLs & routing](#base-urls--routing)
- [Authentication](#authentication)
- [Conventions](#conventions) — content type, pagination, data types, RBAC, common errors
- [Auth service](#auth-service) · [Projects](#projects-service) · [Deliverables](#deliverables-service) · [Resources](#resources-service) · [Allocations](#allocations-service)
- [Appendix: entity fields & enums](#appendix-entity-fields--enums)

---

## Base URLs & routing

Each service is a separate Lambda with its own base URL. The URLs are generated
per environment by `bin/generate-env.sh` (into `frontend/.env.local` as
`VITE_API_ENDPOINTS`) — **never hardcode them**; the app_id suffix changes per
deployment.

| Service | Local base (example) |
| ------- | -------------------- |
| auth | `http://<id>.lambda-url.us-east-1.localhost.localstack.cloud:4566` |
| projects | `http://<id>.lambda-url…:4566` |
| deliverables | `http://<id>.lambda-url…:4566` |
| resources | `http://<id>.lambda-url…:4566` |
| allocations | `http://<id>.lambda-url…:4566` |

**In the dev frontend**, calls go same-origin through the Vite proxy under
`/api/<service>` (see `vite.config.js`) to avoid browser CORS. So the browser
calls `/api/auth/login`, which is proxied to the auth Lambda's `/auth/login`.

Paths in this document are **service-relative** (e.g. `POST /auth/login`,
`GET /projects/{id}`). Prepend the service base URL (direct) or `/api` (via the
dev proxy).

---

## Authentication

- Auth is **JWT bearer token** only. **There is no cookie** — login returns the
  token in the JSON body; the client stores it (the web app uses `localStorage`)
  and sends it on every request as:

  ```
  Authorization: Bearer <token>
  ```

- Tokens are HS256, expire after **3600s** (60 min; `JWT_EXPIRES_MIN`). Claims:
  `sub` (user id, string), `username`, `role`, `iat`, `exp`.
- Get a token from [`POST /auth/login`](#post-authlogin). Every endpoint except
  `POST /auth/register` and `POST /auth/login` requires a valid token.

---

## Conventions

### Request/response format
- Requests with a body must send `Content-Type: application/json`.
- Successful responses are JSON, except **`DELETE` → `204 No Content` with an
  empty body**.
- Timestamps are ISO‑8601 strings (`"2026-07-23T01:18:16.632301"`). Dates are
  `"YYYY-MM-DD"`. Money fields (`budget_*`) serialize as **floats**
  (`800000.0`); percentages (`allocation_pct`, `completion_pct`) as **integers**.

### Pagination (all list endpoints)
List endpoints accept `?limit` and `?offset` and return a uniform envelope:

```jsonc
{
  "items": [ /* ... */ ],
  "total": 12,     // total rows matching the filters, ignoring limit/offset
  "limit": 2,      // effective limit applied
  "offset": 0      // effective offset applied
}
```

| Param | Default | Constraint |
| ----- | ------- | ---------- |
| `limit` | `50` | non‑negative integer; **capped at 200** (values >200 are clamped, not rejected) |
| `offset` | `0` | non‑negative integer |

Invalid values → **400** (see [pagination errors](#pagination-errors)).

The two **analytics** endpoints (`/allocations/over-allocated`,
`/allocations/summary`) return a **bare JSON array**, not a pagination envelope.

### Roles & permissions (RBAC)
The role is read from the token and enforced by the backend on every request.

| Action (HTTP) | Viewer | Contributor | Manager | Admin |
| ------------- | :----: | :---------: | :-----: | :---: |
| read (`GET`) | ✅ | ✅ | ✅ | ✅ |
| create (`POST`) | ❌ | ✅ | ✅ | ✅ |
| update (`PUT`) | ❌ | ✅ | ✅ | ✅ |
| delete (`DELETE`) | ❌ | ❌ | ✅ | ✅ |
| manage users/roles | ❌ | ❌ | ❌ | ✅ |

Seeded demo logins (from `bin/seed-data.sh`): `admin`/`admin123`,
`manager`/`manager123`, `contributor`/`contributor123`, `viewer`/`viewer123`.

### HTTP status codes
| Code | Meaning |
| ---- | ------- |
| 200 | OK (read / update) |
| 201 | Created |
| 204 | No Content (delete) |
| 400 | Validation error, malformed JSON, bad pagination, **duplicate**, or missing referenced entity |
| 401 | Missing / malformed / invalid / expired token, or the token's user no longer exists |
| 403 | Authenticated but the role isn't permitted (or unrecognized role) |
| 404 | Resource / route not found |
| 405 | Method not allowed on that path |
| 500 | Unexpected server/database error |

> **Note on duplicates:** the API returns **`400`** (not `409`) for unique‑constraint
> violations (duplicate email, duplicate allocation pair, duplicate username/email),
> with a clear message. There is no `409` in this API.

### Common error responses
These are **identical across every protected endpoint** (only the entity name /
path in the message varies). They are shown here once; per‑endpoint sections list
which apply and show endpoint‑specific bodies.

**Error envelope.** Every error is `{"error": "<message>"}`. Validation errors
additionally include a `details` array; unexpected 500s include a `details`
string.

`401` — missing header:
```json
{ "error": "Missing Authorization header." }
```
`401` — malformed header (not `Bearer <token>`):
```json
{ "error": "Authorization header must be in the form 'Bearer <token>'." }
```
`401` — invalid signature / not a JWT:
```json
{ "error": "Invalid authentication token." }
```
`401` — expired:
```json
{ "error": "Authentication token has expired." }
```
`401` — token's user was deleted:
```json
{ "error": "Authenticated user no longer exists." }
```
`403` — role lacks the permission (message names the role + action):
```json
{ "error": "Access denied: 'Viewer' cannot create." }
```
`403` — token carries a role the system doesn't recognize:
```json
{ "error": "Access denied: unrecognized role 'Wizard'." }
```
`405` — unsupported method on a CRUD path:
```json
{ "error": "Method PATCH not allowed." }
```
`500` — unexpected server/database error:
```json
{ "error": "Internal server error.", "details": "<exception detail>" }
```

<a id="pagination-errors"></a>**400 — bad pagination** (any list endpoint):
```json
{ "error": "`limit` must be a non-negative integer." }
```
```json
{ "error": "`offset` must be a non-negative integer." }
```

**400 — malformed JSON body** (any endpoint taking a body):
```json
{ "error": "Request body is not valid JSON." }
```

---

## Auth service

Base: the **auth** service URL. Routes: `/auth/register`, `/auth/login`, `/auth/me`.

### POST /auth/register
Create a user. **Public** (no token needed). New users get the **Viewer** role by
default; requesting any other role requires an **Admin** bearer token.

**Request**
- Headers: `Content-Type: application/json` (optional `Authorization: Bearer <admin-token>` only when assigning an elevated `role`)
- Body:

```json
{
  "username": "jordan.lee",
  "email": "jordan.lee@acme.test",
  "password": "password123",
  "role": "Viewer"
}
```
Fields: `username` (required, non‑empty), `email` (required, valid email),
`password` (required, 8–72 chars), `role` (optional; defaults to `Viewer`;
non‑default requires Admin).

**Success — `201 Created`**
```json
{
  "id": 15,
  "username": "doc_demo_155557",
  "email": "doc_demo_155557@acme.test",
  "role": "Viewer",
  "created_at": "2026-07-23T01:28:15.312555"
}
```

**Errors**
- `400` validation:
  ```json
  {
    "error": "Validation failed.",
    "details": [
      "`email` must be a valid email address.",
      "`password` must be between 8 and 72 characters."
    ]
  }
  ```
- `400` duplicate username or email:
  ```json
  { "error": "Username or email is already in use." }
  ```
- `403` requesting an elevated role without an Admin token:
  ```json
  { "error": "Access denied: only an Admin can assign the 'Admin' role." }
  ```
- `400` unknown role name: `{ "error": "Unknown role 'Wizard'." }`
- `400` malformed JSON · `405` non‑POST (`{ "error": "Method GET not allowed on /auth/register." }`) · `500`.

---

### POST /auth/login
Verify credentials and return a JWT. **Public.**

**Request**
- Headers: `Content-Type: application/json`
- Body — send **`username` or `email`**, plus `password`:

```json
{ "username": "admin", "password": "admin123" }
```

**Success — `200 OK`** (the exact login payload; **no `Set-Cookie` header**):
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3IiwidXNlcm5hbWUiOiJhZG1pbiIsInJvbGUiOiJBZG1pbiIsImlhdCI6MTc4NDc1MDI5NCwiZXhwIjoxNzg0NzUzODk0fQ.ZQ_9BLFoe3RDO3GJw3g4oKSSOYPudc-VUL0axo1CfTo",
  "token_type": "Bearer",
  "expires_in": 3600,
  "user": {
    "id": 7,
    "username": "admin",
    "email": "admin@acme.test",
    "role": "Admin"
  }
}
```
Response headers are plain JSON (`Content-Type: application/json`) — the token is
**only** in the body; there is no cookie.

**Errors**
- `401` wrong password or unknown user (same message either way, to avoid user enumeration):
  ```json
  { "error": "Invalid credentials." }
  ```
- `400` validation (missing username/email or password):
  ```json
  { "error": "Validation failed.", "details": ["A `username` or `email` is required.", "`password` is required and cannot be empty."] }
  ```
- `400` malformed JSON · `405` non‑POST · `500`.

---

### GET /auth/me
Return the current user described by the token. **Any authenticated role.**

**Request**
- Headers: `Authorization: Bearer <token>`

**Success — `200 OK`**
```json
{
  "id": 7,
  "username": "admin",
  "email": "admin@acme.test",
  "role": "Admin",
  "created_at": "2026-07-23T00:53:07.843884"
}
```

**Errors**
- `401` missing/invalid/expired token (see [common errors](#common-error-responses)):
  ```json
  { "error": "Missing Authorization header." }
  ```
- `404` unknown auth route (e.g. `GET /auth/bogus`):
  ```json
  { "error": "Unknown auth route. Use /auth/register, /auth/login, or /auth/me." }
  ```
- `405` non‑GET: `{ "error": "Method POST not allowed on /auth/me." }`
- `500`.

---

## Projects service

Base: the **projects** service URL. Object fields: see
[appendix](#project). All endpoints require a valid token.

### GET /projects
List projects (paginated). **Any authenticated role.**

**Request**
- Headers: `Authorization: Bearer <token>`
- Query params:

| Param | Default | Notes |
| ----- | ------- | ----- |
| `status` | — | filter: `planning` \| `active` \| `on_hold` \| `completed` \| `cancelled` |
| `department` | — | exact match, e.g. `Engineering` |
| `limit` | 50 | ≤200 |
| `offset` | 0 | ≥0 |

Example: `GET /projects?status=active&department=Data&limit=2&offset=0`

**Success — `200 OK`** (full pagination envelope, multi‑item):
```json
{
  "items": [
    {
      "id": 1,
      "name": "Apollo Platform Rebuild",
      "description": "Re-architect the core platform onto a modular services stack.",
      "status": "active",
      "department": "Engineering",
      "start_date": "2026-03-25",
      "end_date": "2026-10-21",
      "deadline": "2026-09-01",
      "budget_planned": 800000.0,
      "budget_consumed": 540000.0,
      "created_at": "2026-07-23T01:18:16.632301",
      "updated_at": "2026-07-23T01:18:16.632301"
    },
    {
      "id": 2,
      "name": "Nimbus Data Warehouse",
      "description": "Consolidate analytics into a governed warehouse.",
      "status": "active",
      "department": "Data",
      "start_date": "2026-04-24",
      "end_date": "2026-08-22",
      "deadline": "2026-08-04",
      "budget_planned": 650000.0,
      "budget_consumed": 612000.0,
      "created_at": "2026-07-23T01:18:16.632301",
      "updated_at": "2026-07-23T01:18:16.632301"
    }
  ],
  "total": 12,
  "limit": 2,
  "offset": 0
}
```

**Errors:** `400` bad pagination · `401` (common). 

### GET /projects/{id}
Get one project. **Any authenticated role.**

**Success — `200 OK`**
```json
{
  "id": 1,
  "name": "Apollo Platform Rebuild",
  "description": "Re-architect the core platform onto a modular services stack.",
  "status": "active",
  "department": "Engineering",
  "start_date": "2026-03-25",
  "end_date": "2026-10-21",
  "deadline": "2026-09-01",
  "budget_planned": 800000.0,
  "budget_consumed": 540000.0,
  "created_at": "2026-07-23T01:18:16.632301",
  "updated_at": "2026-07-23T01:18:16.632301"
}
```

**Errors**
- `404` not found (also returned for a non‑numeric id):
  ```json
  { "error": "Project 999999 not found." }
  ```
- `401` (common).

### POST /projects
Create a project. **Contributor+.**

**Request** — `Authorization: Bearer <token>`, `Content-Type: application/json`
```json
{
  "name": "Neptune Billing Revamp",
  "description": "Rebuild the billing engine.",
  "status": "planning",
  "department": "Finance",
  "start_date": "2026-08-01",
  "end_date": "2026-12-15",
  "deadline": "2026-12-01",
  "budget_planned": 275000,
  "budget_consumed": 0
}
```
Only `name` is required. `status` defaults to `planning`; budgets default to `0`.
Names ≤200 chars, department ≤100 chars.

**Success — `201 Created`**
```json
{
  "id": 13,
  "name": "Neptune Billing Revamp",
  "description": "Rebuild the billing engine.",
  "status": "planning",
  "department": "Finance",
  "start_date": "2026-08-01",
  "end_date": "2026-12-15",
  "deadline": "2026-12-01",
  "budget_planned": 275000.0,
  "budget_consumed": 0.0,
  "created_at": "2026-07-23T01:29:40.192094",
  "updated_at": "2026-07-23T01:29:40.192094"
}
```

**Errors**
- `400` validation (multiple messages in `details`):
  ```json
  {
    "error": "Validation failed.",
    "details": [
      "`name` is required and cannot be empty.",
      "`status` must be one of: planning, active, on_hold, completed, cancelled.",
      "`budget_planned` must be a number."
    ]
  }
  ```
- `403` as Viewer: `{ "error": "Access denied: 'Viewer' cannot create." }`
- `400` malformed JSON · `401` (common) · `500`.

### PUT /projects/{id}
Partial update (send only the fields to change). **Contributor+.**

**Request**
```json
{ "status": "active", "budget_consumed": 42000 }
```

**Success — `200 OK`** (`updated_at` is bumped):
```json
{
  "id": 13,
  "name": "Neptune Billing Revamp",
  "description": "Rebuild the billing engine.",
  "status": "active",
  "department": "Finance",
  "start_date": "2026-08-01",
  "end_date": "2026-12-15",
  "deadline": "2026-12-01",
  "budget_planned": 275000.0,
  "budget_consumed": 42000.0,
  "created_at": "2026-07-23T01:29:40.192094",
  "updated_at": "2026-07-23T01:29:40.277700"
}
```

**Errors:** `400` validation · `403` as Viewer (`… cannot update.`) · `404` not found · `401` (common).

### DELETE /projects/{id}
Delete a project (cascades to its deliverables & allocations). **Manager+.**

**Success — `204 No Content`** (empty body).

**Errors**
- `403` as Viewer or Contributor: `{ "error": "Access denied: 'Contributor' cannot delete." }`
- `404` not found: `{ "error": "Project 999999 not found." }`
- `401` (common).

### Unsupported method
`PATCH /projects/{id}` → `405`:
```json
{ "error": "Method PATCH not allowed." }
```

---

## Deliverables service

Base: the **deliverables** service URL. Object fields: [appendix](#deliverable).
A deliverable belongs to a project (`project_id`, FK).

### GET /deliverables
List deliverables (paginated). **Any authenticated role.**

**Query params:** `project_id` (int), `status` (`not_started`|`in_progress`|`blocked`|`completed`), `limit` (50, ≤200), `offset` (0).

Example: `GET /deliverables?project_id=1&limit=2`

**Success — `200 OK`**
```json
{
  "items": [
    {
      "id": 1,
      "project_id": 1,
      "name": "Service decomposition plan",
      "description": "Define bounded contexts and service boundaries.",
      "status": "completed",
      "completion_pct": 100,
      "due_date": "2026-06-23",
      "created_at": "2026-07-23T01:18:16.632301",
      "updated_at": "2026-07-23T01:18:16.632301"
    },
    {
      "id": 2,
      "project_id": 1,
      "name": "Auth service extraction",
      "description": "Split auth into its own service.",
      "status": "in_progress",
      "completion_pct": 65,
      "due_date": "2026-08-02",
      "created_at": "2026-07-23T01:18:16.632301",
      "updated_at": "2026-07-23T01:18:16.632301"
    }
  ],
  "total": 4,
  "limit": 2,
  "offset": 0
}
```

### GET /deliverables/{id}
**Any authenticated role.** `200 OK`:
```json
{
  "id": 1,
  "project_id": 1,
  "name": "Service decomposition plan",
  "description": "Define bounded contexts and service boundaries.",
  "status": "completed",
  "completion_pct": 100,
  "due_date": "2026-06-23",
  "created_at": "2026-07-23T01:18:16.632301",
  "updated_at": "2026-07-23T01:18:16.632301"
}
```
`404`: `{ "error": "Deliverable 999999 not found." }`

### POST /deliverables
Create. **Contributor+.** Requires an existing `project_id`.

**Request**
```json
{
  "project_id": 1,
  "name": "Rollout runbook",
  "description": "Cutover steps.",
  "status": "not_started",
  "completion_pct": 0,
  "due_date": "2026-09-20"
}
```
Required: `project_id` (must exist), `name`. `status` defaults `not_started`;
`completion_pct` defaults `0` (0–100).

**Success — `201 Created`**
```json
{
  "id": 28,
  "project_id": 1,
  "name": "Rollout runbook",
  "description": "Cutover steps.",
  "status": "not_started",
  "completion_pct": 0,
  "due_date": "2026-09-20",
  "created_at": "2026-07-23T01:30:37.945819",
  "updated_at": "2026-07-23T01:30:37.945819"
}
```

**Errors**
- `400` referenced project does not exist:
  ```json
  { "error": "Referenced project 999999 does not exist." }
  ```
- `400` validation:
  ```json
  {
    "error": "Validation failed.",
    "details": [
      "`project_id` is required and must be an integer.",
      "`name` is required and cannot be empty.",
      "`completion_pct` must be between 0 and 100."
    ]
  }
  ```
- `403` as Viewer · `401` (common).

### PUT /deliverables/{id}
Partial update. **Contributor+.** `200 OK`:
```json
{
  "id": 28,
  "project_id": 1,
  "name": "Rollout runbook",
  "description": "Cutover steps.",
  "status": "in_progress",
  "completion_pct": 35,
  "due_date": "2026-09-20",
  "created_at": "2026-07-23T01:30:37.945819",
  "updated_at": "2026-07-23T01:30:38.057551"
}
```
Errors: `400` validation / bad FK · `403` · `404` · `401`.

### DELETE /deliverables/{id}
**Manager+.** `204 No Content` (empty body). `404`:
`{ "error": "Deliverable 999999 not found." }`. `403` for Viewer/Contributor.

---

## Resources service

Base: the **resources** service URL. Object fields: [appendix](#resource).
`email` is **unique**.

### GET /resources
List resources (paginated). **Any authenticated role.**

**Query params:** `search` (case‑insensitive match on **name or title**), `limit` (50, ≤200), `offset` (0).

Example: `GET /resources?search=Engineer&limit=2`

**Success — `200 OK`**
```json
{
  "items": [
    {
      "id": 1,
      "name": "Marcus Reed",
      "email": "marcus.reed@acme.test",
      "title": "Staff Engineer",
      "created_at": "2026-07-23T01:18:16.632301"
    },
    {
      "id": 4,
      "name": "Tom Alvarez",
      "email": "tom.alvarez@acme.test",
      "title": "Data Engineer",
      "created_at": "2026-07-23T01:18:16.632301"
    }
  ],
  "total": 4,
  "limit": 2,
  "offset": 0
}
```

### GET /resources/{id}
**Any authenticated role.** `200 OK`:
```json
{
  "id": 1,
  "name": "Marcus Reed",
  "email": "marcus.reed@acme.test",
  "title": "Staff Engineer",
  "created_at": "2026-07-23T01:18:16.632301"
}
```
`404`: `{ "error": "Resource 999999 not found." }`

### POST /resources
Create. **Contributor+.**

**Request**
```json
{ "name": "Jordan Lee", "email": "jordan.lee@acme.test", "title": "QA Engineer" }
```
Required: `name`, valid `email` (unique). `title` optional. (name ≤150, email ≤255, title ≤100 chars.)

**Success — `201 Created`**
```json
{
  "id": 10,
  "name": "Jordan Lee",
  "email": "jordan.lee@acme.test",
  "title": "QA Engineer",
  "created_at": "2026-07-23T01:30:39.625598"
}
```

**Errors**
- `400` duplicate email:
  ```json
  { "error": "A resource with email 'jordan.lee@acme.test' already exists." }
  ```
- `400` validation:
  ```json
  { "error": "Validation failed.", "details": ["`name` is required and cannot be empty.", "`email` is required and cannot be empty."] }
  ```
- `403` as Viewer · `401` (common).

### PUT /resources/{id}
Partial update. **Contributor+.** `200 OK`:
```json
{
  "id": 10,
  "name": "Jordan Lee",
  "email": "jordan.lee@acme.test",
  "title": "Senior QA Engineer",
  "created_at": "2026-07-23T01:30:39.625598"
}
```
Errors: `400` validation / duplicate email · `403` · `404` · `401`.

### DELETE /resources/{id}
**Manager+.** `204 No Content` (cascades to the resource's allocations). `404`:
`{ "error": "Resource 999999 not found." }`.

---

## Allocations service

Base: the **allocations** service URL. Object fields: [appendix](#allocation).
An allocation links a **resource** to a **project**; the pair
`(resource_id, project_id)` is **unique**; `allocation_pct` is 0–100.

### GET /allocations
List allocations (paginated). **Any authenticated role.**

**Query params:** `resource_id` (int), `project_id` (int), `limit` (50, ≤200), `offset` (0).

Example: `GET /allocations?resource_id=1&limit=2`

**Success — `200 OK`**
```json
{
  "items": [
    { "id": 1, "resource_id": 1, "project_id": 1, "allocation_pct": 70, "start_date": "2026-04-14", "end_date": "2026-10-21" },
    { "id": 2, "resource_id": 1, "project_id": 4, "allocation_pct": 40, "start_date": "2026-06-13", "end_date": "2026-11-20" }
  ],
  "total": 3,
  "limit": 2,
  "offset": 0
}
```

### GET /allocations/{id}
**Any authenticated role.** `200 OK`:
```json
{ "id": 1, "resource_id": 1, "project_id": 1, "allocation_pct": 70, "start_date": "2026-04-14", "end_date": "2026-10-21" }
```
`404`: `{ "error": "Allocation 999999 not found." }`

### POST /allocations
Create. **Contributor+.** Requires existing `resource_id` and `project_id`; the
pair must not already exist.

**Request**
```json
{
  "resource_id": 9,
  "project_id": 10,
  "allocation_pct": 25,
  "start_date": "2026-08-01",
  "end_date": "2026-11-30"
}
```
Required: `resource_id`, `project_id` (both must exist). `allocation_pct` 0–100
(defaults 0); if both dates given, `end_date` ≥ `start_date`.

**Success — `201 Created`**
```json
{ "id": 21, "resource_id": 9, "project_id": 10, "allocation_pct": 25, "start_date": "2026-08-01", "end_date": "2026-11-30" }
```

**Errors**
- `400` duplicate (resource already allocated to that project):
  ```json
  { "error": "Resource 1 is already allocated to project 1." }
  ```
- `400` referenced entity missing (resource and/or project):
  ```json
  { "error": "Referenced resource 999999 does not exist." }
  ```
- `400` validation (range + date order):
  ```json
  {
    "error": "Validation failed.",
    "details": [
      "`resource_id` is required and must be an integer.",
      "`project_id` is required and must be an integer.",
      "`allocation_pct` must be between 0 and 100.",
      "`end_date` must not be before `start_date`."
    ]
  }
  ```
- `403` as Viewer · `401` (common).

### PUT /allocations/{id}
Partial update. **Contributor+.** `200 OK`:
```json
{ "id": 21, "resource_id": 9, "project_id": 10, "allocation_pct": 40, "start_date": "2026-08-01", "end_date": "2026-11-30" }
```
Errors: `400` validation / duplicate / bad FK · `403` · `404` · `401`.

### DELETE /allocations/{id}
**Manager+.** `204 No Content`. `404`:
`{ "error": "Allocation 999999 not found." }`.

---

### GET /allocations/over-allocated
Resources whose **summed** allocation across all their projects exceeds 100%.
**Any authenticated role.** Returns a **bare array** (no pagination envelope).

**Success — `200 OK`**
```json
[
  { "resource_id": 1, "resource_name": "Marcus Reed", "email": "marcus.reed@acme.test", "total_allocation_pct": 140, "project_count": 3, "over_allocated": true },
  { "resource_id": 4, "resource_name": "Tom Alvarez", "email": "tom.alvarez@acme.test", "total_allocation_pct": 130, "project_count": 2, "over_allocated": true },
  { "resource_id": 3, "resource_name": "Ana Duarte",  "email": "ana.duarte@acme.test",  "total_allocation_pct": 115, "project_count": 3, "over_allocated": true }
]
```
Empty array `[]` when nobody is over‑allocated. Errors: `401` (common).

### GET /allocations/summary
Per‑resource allocation totals for **every** resource that has at least one
allocation, each flagged `over_allocated`. Ordered by total desc. **Any
authenticated role.** Bare array.

**Success — `200 OK`**
```json
[
  { "resource_id": 1, "resource_name": "Marcus Reed",  "email": "marcus.reed@acme.test",  "total_allocation_pct": 140, "project_count": 3, "over_allocated": true },
  { "resource_id": 4, "resource_name": "Tom Alvarez",  "email": "tom.alvarez@acme.test",  "total_allocation_pct": 130, "project_count": 2, "over_allocated": true },
  { "resource_id": 3, "resource_name": "Ana Duarte",   "email": "ana.duarte@acme.test",   "total_allocation_pct": 115, "project_count": 3, "over_allocated": true },
  { "resource_id": 6, "resource_name": "Liam O'Brien", "email": "liam.obrien@acme.test",  "total_allocation_pct": 100, "project_count": 2, "over_allocated": false },
  { "resource_id": 8, "resource_name": "Nadia Hassan", "email": "nadia.hassan@acme.test", "total_allocation_pct": 100, "project_count": 2, "over_allocated": false },
  { "resource_id": 2, "resource_name": "Priya Nair",   "email": "priya.nair@acme.test",   "total_allocation_pct": 90,  "project_count": 2, "over_allocated": false },
  { "resource_id": 5, "resource_name": "Sofia Rossi",  "email": "sofia.rossi@acme.test",  "total_allocation_pct": 90,  "project_count": 2, "over_allocated": false },
  { "resource_id": 7, "resource_name": "Chen Wei",     "email": "chen.wei@acme.test",     "total_allocation_pct": 80,  "project_count": 2, "over_allocated": false },
  { "resource_id": 9, "resource_name": "Diego Santos", "email": "diego.santos@acme.test", "total_allocation_pct": 65,  "project_count": 2, "over_allocated": false }
]
```
> Uses an inner join, so resources with **zero** allocations don't appear here.
> Errors: `401` (common).

---

## Appendix: entity fields & enums

### project
| Field | Type | Notes |
| ----- | ---- | ----- |
| `id` | int | |
| `name` | string | required, ≤200 |
| `description` | string \| null | |
| `status` | enum | `planning` \| `active` \| `on_hold` \| `completed` \| `cancelled` (default `planning`) |
| `department` | string \| null | ≤100 |
| `start_date`, `end_date`, `deadline` | date \| null | `YYYY-MM-DD` |
| `budget_planned`, `budget_consumed` | float | default `0` |
| `created_at`, `updated_at` | timestamp | ISO‑8601 |

### deliverable
| Field | Type | Notes |
| ----- | ---- | ----- |
| `id` | int | |
| `project_id` | int | required, FK → project |
| `name` | string | required, ≤200 |
| `description` | string \| null | |
| `status` | enum | `not_started` \| `in_progress` \| `blocked` \| `completed` (default `not_started`) |
| `completion_pct` | int | 0–100 (default 0) |
| `due_date` | date \| null | |
| `created_at`, `updated_at` | timestamp | |

### resource
| Field | Type | Notes |
| ----- | ---- | ----- |
| `id` | int | |
| `name` | string | required, ≤150 |
| `email` | string | required, **unique**, valid email, ≤255 |
| `title` | string \| null | ≤100 |
| `created_at` | timestamp | (no `updated_at` on this entity) |

### allocation
| Field | Type | Notes |
| ----- | ---- | ----- |
| `id` | int | |
| `resource_id` | int | required, FK → resource |
| `project_id` | int | required, FK → project; **`(resource_id, project_id)` unique** |
| `allocation_pct` | int | 0–100 (default 0) |
| `start_date`, `end_date` | date \| null | if both set, `end_date` ≥ `start_date` |

### analytics row (`/over-allocated`, `/summary`)
| Field | Type | Notes |
| ----- | ---- | ----- |
| `resource_id` | int | |
| `resource_name` | string | |
| `email` | string | |
| `total_allocation_pct` | int | sum of `allocation_pct` across the resource's projects |
| `project_count` | int | number of projects the resource is on |
| `over_allocated` | bool | `true` when `total_allocation_pct > 100` |

### roles
`Viewer` · `Contributor` · `Manager` · `Admin` — see the
[RBAC matrix](#roles--permissions-rbac).
