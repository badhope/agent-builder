# Security

A running list of what we actually do, what we *say* we do, and what's
on my mental list to fix before someone with a louder voice than mine
asks about it. Read this with the OWASP
[API Security Top 10](https://owasp.org/API-Security/editions/2023/en/0x11-t10/)
open in another tab.

## Threat model

The table below is what I came up with after one afternoon with a
pencil. It is not exhaustive. Things I almost added and then
second-guessed are in the section after the table.

| Asset | Threat | What we actually do |
|-------|--------|---------------------|
| User passwords | Credential stuffing, brute force | Argon2id, password rules, `slowapi` rate limit on `/login` (5/min/IP, 10/min/email). |
| JWT signing key | Token forgery | RS256 4096-bit, key on a mounted volume, not in the image. |
| API keys | DB leak | Stored as SHA-256 of `prefix:secret`, only the prefix is shown in the UI once. |
| User files | Path traversal, MIME confusion | `safe_join` + magic-byte sniff on every upload. Rejecting by extension would be one bug away from a CVE. |
| Conversion sandbox | RCE via crafted document | `setsid` + `rlimit` (AS/CPU/NPROC/FSIZE) + wall-clock timeout. See [Sandboxing](#sandboxing) for the gotchas. |
| Webhooks | Replay, spoofing | HMAC-SHA256 with timestamp + 5 min replay window. HTTPS only. |
| Admin endpoints | Privilege escalation | `require_admin` dependency on every privileged route, audit log row per call. |
| Logs | PII leakage | Structured JSON, redacts `Authorization`, `Cookie`, `X-API-Key`. **Known issue: free-form `request.body` is not yet redacted — see TODO in `logging.py`.** |
| Storage | Unauthorized read | MinIO bucket is private. Downloads use HMAC-signed pre-signed URLs, expiry ≤ 24h. |

### Things I almost wrote into the threat model

- **SSRF on webhook URLs.** Right now the worker will POST to any URL
  the user provides. An attacker who has compromised a session can
  point this at `http://169.254.169.254/...` and try to steal instance
  metadata. TODO: resolve the host, block private IP ranges, and
  refuse redirects. Tracked in `services/webhook.py`.
- **Tenant isolation.** The data model is single-tenant, so this is
  not really a "tenant" thing, but the *quota* is per-user. An admin
  could in theory read another user's files via the admin endpoints.
  I log every admin read, but the data scoping on `GET /v1/files/{id}`
  is currently "any admin can see it". Want to fix this when we get a
  second customer.
- **Side-channel timing on login.** We hash the password even if the
  user doesn't exist, but we do *not* hash with a constant per-user
  salt, so the timing difference is small but measurable. Argon2 is
  slow enough that the network jitter probably covers it. Not sure.
  Need to measure before promising anything in writing.

## Authentication

- **Passwords**: Argon2id, time=3, memory=64 MiB, parallelism=4,
  salt=16 bytes, hash=32 bytes. On login we rehash if the cost
  parameters have changed (i.e. after a config bump). The rehash is
  fire-and-forget — if it fails, the user still logs in. Not ideal,
  see FIXME in `services/auth_service.py`.
- **Access tokens**: RS256, 15 min. Claims: `sub`, `iat`, `exp`,
  `iss`, `aud`, `type`, `role`, `scopes`. The `aud` is `"web"` for
  the SPA and `"cli"` for the API key flow, which lets us reject
  tokens issued for the wrong client.
- **Refresh tokens**: RS256, 30 days, `jti` stored in
  `revoked_token` until natural expiry. Logout marks the row
  immediately. There is no rotation on refresh — a stolen refresh
  token is good for 30 days minus however long since it was issued.
  This is on the list.
- **API keys**: 32 random bytes, base64url. Prefixed `dck_live_` /
  `dck_test_`. We keep the first 12 chars (`prefix`) in plain text so
  the dashboard can show "Last used with prefix `dck_live_aB12...`";
  the full key is hashed as `SHA-256(prefix + ":" + key)`.
- **MFA**: not built. Admin-only routes currently re-ask for the
  password via `X-Reauth` header. I would like TOTP (RFC 6238) before
  the year is out.

## Authorization

- Roles: `admin` > `user`. Plans are orthogonal: `free` / `pro` /
  `enterprise`. The plan check is in the quota layer, not in the
  router — this is a deliberate choice so that adding a new plan
  limit does not require touching every route. (It also means you
  need to read `services/quota.py` to know which route costs what.
  I'm aware that's a tradeoff.)
- Scopes on API keys: `files:read`, `files:write`, `convert:read`,
  `convert:write`, `batches:read`, `batches:write`, `admin:*`. Each
  route advertises its required scope in its dependency, e.g.
  `Depends(require_scope("files:write"))`.

## Transport

- TLS 1.2+ only, HSTS for 2 years with `includeSubDomains; preload`.
- HTTP→HTTPS redirect at the nginx layer.
- Cookies: not used. The SPA stores the JWT in `localStorage`. I know
  this is a known anti-pattern (XSS → token theft). The reason I
  haven't moved to `HttpOnly` cookies is the API is also consumed by
  the WeChat mini-program, which can't share a cookie jar with the
  web origin. So either I eat the XSS risk on the web, or I eat the
  "I have to refresh the token in two places" complexity. I chose
  the first. PRs welcome.

## Webhook signing

Headers on outbound webhooks:

```
POST /your/webhook HTTP/1.1
Content-Type: application/json
X-DocConv-Delivery:   9c5b…
X-DocConv-Event:      task.succeeded
X-DocConv-Timestamp:  1730000000
X-DocConv-Signature:  sha256=<hex hmac-sha256 of "ts.body" with the shared secret>
```

Replay window is 5 minutes. Verify on receipt (Python):

```python
import hmac, hashlib, time

SECRET = b"…"
ts   = request.headers["X-DocConv-Timestamp"]
sig  = request.headers["X-DocConv-Signature"].removeprefix("sha256=")
if abs(time.time() - int(ts)) > 300:
    abort(401)
expected = hmac.new(
    SECRET, f"{ts}.{request.body.decode()}".encode(), hashlib.sha256
).hexdigest()
if not hmac.compare_digest(expected, sig):
    abort(401)
```

I am going to be honest: I have not yet seen a real customer use the
webhook feature end-to-end. The signature math is covered by a unit
test, but I cannot tell you the `9c5b…` ID format won't change in
v1.

## Sandboxing

Conversion subprocesses run with:

- `setsid` — own process group, signals stay where they should
- `RLIMIT_AS` — virtual memory cap, default 1 GiB
- `RLIMIT_CPU` — soft + hard, default 60 s
- `RLIMIT_NPROC` — fork bomb mitigation
- `RLIMIT_FSIZE` — output file cap
- Wall-clock timeout, default 300 s, then `SIGKILL`
- No outbound network from the conversion subprocess (configurable
  per environment)
- Scratch dir owned by the worker, cleaned up on exit

LibreOffice is started with `-env:UserInstallation=file:///<scratch>`
so concurrent workers never share a profile. Without this, two
workers writing to the default profile will corrupt it in
entertaining ways. Took me a Saturday to find this.

### What this does not protect against

- A LibreOffice macro that tries to read `/etc/passwd` from inside
  the subprocess: blocked by the lack of network and the rlimits,
  but *not* by a namespace. We do not run the workers in a separate
  user namespace. If you care about this (you should), the fix is
  to add `runsc` (gVisor) at the container level. K8s manifests have
  a commented-out stanza for this; I have not enabled it in CI
  because the test suite doubles in wall time.
- Resource exhaustion by a *legitimate* user running 100 concurrent
  conversions. The per-user concurrency limit is set to 4 in
  `services/quota.py`. Bump with care.

## Antivirus

If `ANTIVIRUS_ENABLED=1`, every upload is streamed to ClamAV (`clamd`
over `INSTREAM`) before any further work. Quarantined files get
`scan_status='infected'` and no downstream work. Disabled by default
because the ClamAV image is ~1 GB and most dev environments don't
need it. The `docker-compose.dev.yml` enables it for staging.

## Rate limiting

`slowapi` with a Redis backend. Per-route limits live next to the
route, not in a central config file, so when you read a route you
can see its limit. When the limit hits, the response is `429` with
`Retry-After: <seconds>` and a `X-RateLimit-Reset` header.

The defaults are conservative (login 5/min/IP, conversion create
30/min/user). If you raise them for one tenant, do it via the
`tenant_limits` table, not by editing code.

## Audit log

Every privileged action (admin route hit, role change, file delete,
API key revoke, login) writes a row to `audit_log`:
`(actor_id, action, target_type, target_id, ip, user_agent, request_id, ts)`.
The list endpoint is admin-only. Logs are kept for 1 year, then
truncated to a daily count.

This is not signed. If someone with admin access wants to hide that
they did a thing, they can. I am open to suggestions on cheap ways
to make this harder (write-once storage to S3 with object lock,
probably).

## Secrets management

- Production secrets live in the platform's secret store (K8s Secret
  or SSM). They are not in the image and not in `.env` files that
  get baked.
- `.env` is git-ignored. The shipped `.env.example` is a template;
  replace every `CHANGE_ME`.
- JWT private keys are generated on first start and persisted to a
  mounted volume (`/data/keys`). To rotate, run
  `python -m app.scripts.generate_jwt_keys --force`, restart API
  replicas, and accept that refresh tokens signed with the old key
  remain valid until their own expiry. There is no overlap window
  because the key is a single RSA key, not a JWKS — see FIXME in
  `services/auth_service.py`.

## Compliance notes

- **GDPR**: `users.email` is the only required PII. Right-to-erasure
  via `DELETE /v1/users/{id}` (admin) soft-deletes the user,
  anonymises owned rows, and hard-deletes files + tasks after 30
  days (so we can still recover from a fat-fingered deletion).
- **SOC 2**: admin actions are logged; key rotation is in
  [operations.md](operations.md). I do not have a SOC 2 report to
  point you at.

## Reporting a vulnerability

Email `security@docformatconverter.example.com` — GPG key is on the
repo homepage. I aim to acknowledge within 48 hours. I will not
sue you. If you are looking for a paid bug bounty program, there
isn't one.

— [@badhope](https://github.com/badhope)
