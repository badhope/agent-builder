# API reference

All endpoints live under `/v1`. Every request must include
`Authorization: Bearer <token>` (JWT) or `X-API-Key: dck_…` (API key)
unless it is marked **public**.

All responses are JSON. Errors share a single shape:

```json
{ "code": "validation_error", "message": "email: not a valid email", "details": {…} }
```

Status code → error code matrix:

| Status | Codes |
|--------|-------|
| 400 | `bad_request`, `validation_error` |
| 401 | `auth_missing`, `auth_invalid`, `auth_expired` |
| 403 | `auth_forbidden` |
| 404 | `not_found` |
| 409 | `conflict`, `idempotency_conflict` |
| 413 | `file_too_large` |
| 415 | `unsupported_media_type` |
| 422 | `unprocessable` |
| 429 | `rate_limited` |
| 500 | `internal_error` |
| 502 | `converter_unavailable` |
| 504 | `converter_timeout` |

---

## Auth

### `POST /v1/auth/register`

Public. Creates a new user and returns a token pair.

```json
{ "email": "alice@example.com", "password": "Sup3rStrong!Pass", "full_name": "Alice" }
```

Response `201`:

```json
{
  "access_token": "eyJ…",
  "refresh_token": "eyJ…",
  "refresh_jti": "uuid",
  "token_type": "Bearer",
  "expires_in": 900
}
```

### `POST /v1/auth/login`

Public. Body: `{"email": …, "password": …}`. Response identical to register.

### `POST /v1/auth/refresh`

Public. Body: `{"refresh_token": "eyJ…"}`. Returns a new access token.

### `POST /v1/auth/logout`

Body: `{"refresh_token_jti": "uuid"}`. Revokes the refresh token.

### `GET /v1/auth/me`

Returns the current user.

### `POST /v1/auth/change-password`

Body: `{"old_password": …, "new_password": …}`.

### `GET /v1/auth/api-keys` / `POST /v1/auth/api-keys` / `DELETE /v1/auth/api-keys/{id}`

Manage API keys. The plain key is **only** returned on creation.

---

## Files

### `POST /v1/files/uploads`

`multipart/form-data` with one `file` field. Query: `purpose=source|asset|avatar`.

Performs magic-byte validation against the declared MIME type. Rejects
mismatches with 415. Optionally calls ClamAV if `ANTIVIRUS_ENABLED=1`.

Response `201`: `FileRead` (see schemas).

### `GET /v1/files`

Query: `limit`, `offset`, `purpose`. Returns paginated list.

### `GET /v1/files/{id}`

Returns `FileRead`.

### `GET /v1/files/{id}/download`

Streams the file with a `Content-Disposition: attachment` header.

### `GET /v1/files/{id}/signed-url`

Query: `expires_in` (60–86400). Returns a one-shot URL valid for the
requested period. The URL embeds an HMAC-signed token — no bearer
required to download.

### `DELETE /v1/files/{id}`

Hard delete (also removes the underlying object).

---

## Convert

### `POST /v1/convert`

Query:

* `source_file_id`: UUID
* `target_format`: `pdf`, `docx`, `png`, …
* `options`: optional JSON object (forwarded to the converter)
* `webhook_url`: optional; will be POSTed on completion

Response `202`: `TaskRead`.

### `POST /v1/convert/sync`

Same as above but blocks the request until the conversion finishes or
the `timeout` (default 60s) elapses. Use only for small files.

---

## Tasks

### `GET /v1/tasks`

Query: `state`, `source_format`, `target_format`, `limit`, `offset`.

### `GET /v1/tasks/{id}`

### `GET /v1/tasks/{id}/logs`

Returns a chronological list of `TaskLog` rows (state transitions, errors, etc.).

### `POST /v1/tasks/{id}/cancel`

### `POST /v1/tasks/{id}/retry`

Resets the task and re-enqueues. Respects the `max_attempts` ceiling.

### `DELETE /v1/tasks/{id}`

---

## Batches

### `POST /v1/batches`

Body:

```json
{
  "name": "Q4 reports",
  "items": [
    { "source_file_id": "…", "target_format": "pdf" },
    { "source_file_id": "…", "target_format": "pdf", "options": {"page_size": "A4"} }
  ],
  "webhook_url": "https://…"
}
```

### `GET /v1/batches` / `GET /v1/batches/{id}`

### `POST /v1/batches/{id}/cancel` / `POST /v1/batches/{id}/retry` / `DELETE /v1/batches/{id}`

---

## Formats

### `GET /v1/formats`

Returns the list of every format the server supports.

```json
{ "formats": ["pdf", "docx", "xlsx", …] }
```

### `GET /v1/formats/convertible`

Adjacency list of supported source→target pairs.

### `GET /v1/formats/{fmt}/targets`

List of formats reachable from `fmt`.

---

## WebSocket

### `WS /ws/tasks/{id}?token=…`

Subscribes to real-time progress events for a single task. Requires a
JWT in the `token` query parameter (browsers can't set headers on the
WebSocket upgrade).

Server sends:

```json
{ "type": "progress", "task_id": "…", "state": "running", "progress_pct": 42, "ts": 1730000000 }
{ "type": "hello",   "task_id": "…", "user_id": "…" }
{ "type": "pong" }
```

---

## Webhooks (outbound)

If you provide a `webhook_url` on a convert / batch request, DocFormatConverter
will POST to it on completion. The request is signed:

```
X-DocConv-Signature: sha256=<hex hmac>
X-DocConv-Timestamp: 1730000000
X-DocConv-Delivery:  <uuid>
```

Body:

```json
{
  "event": "task.succeeded",
  "task_id": "…",
  "output_file_id": "…",
  "state": "succeeded",
  "attempts": 1
}
```

Verify with the shared secret:

```python
expected = hmac.new(secret, f"{ts}.{body}".encode(), sha256).hexdigest()
assert hmac.compare_digest(expected, signature.removeprefix("sha256="))
```

---

## Rate limits

| Route group | Default | Override env |
|-------------|---------|--------------|
| `POST /v1/auth/login` | 5/minute per IP | `RATE_LIMIT_AUTH_LOGIN` |
| `POST /v1/auth/register` | 3/hour per IP | `RATE_LIMIT_AUTH_REGISTER` |
| `POST /v1/files/uploads` | 30/minute per user | `RATE_LIMIT_UPLOAD` |
| `POST /v1/convert` | 60/minute per user | `RATE_LIMIT_CONVERT` |
| Default for all other routes | 120/minute per user | `RATE_LIMIT_DEFAULT` |

Exceeding the limit returns `429` with `Retry-After`.
