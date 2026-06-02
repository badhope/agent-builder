# Security

This document is the threat model and hardening checklist for
DocFormatConverter. It is meant to be read together with the OWASP
[API Security Top 10](https://owasp.org/API-Security/editions/2023/en/0x11-t10/).

## Threat model

| Asset | Threat | Mitigation |
|-------|--------|------------|
| User passwords | Credential stuffing, brute force | Argon2id, password complexity, rate limit on login, optional MFA roadmap |
| JWT signing key | Token forgery | RS256 with 4096-bit key stored outside the container; rotated quarterly |
| API keys | Database leak | Stored as SHA-256 hash, prefix shown once |
| User files | Path traversal, MIME confusion | `safe_join` + magic-byte sniff on every upload |
| Conversion sandbox | RCE via crafted document | Subprocess via `setsid` + `rlimit`; file size cap; wall-clock timeout; antivirus (optional) |
| Webhooks | Replay, spoofing | HMAC-SHA256 signature with timestamp + nonce; HTTPS-only |
| Admin endpoints | Privilege escalation | Role gate in dependency, audit log on every privileged action |
| Logs | PII leakage | Structured JSON; redact `Authorization`, `Cookie`, `X-API-Key` headers |
| Storage | Unauthorized read | S3 bucket is private; downloads are HMAC-signed; pre-signed URLs expire ≤ 24h |

## Authentication

* **Passwords** are hashed with Argon2id (time cost = 3, memory = 64 MiB,
  parallelism = 4, hash length = 32 bytes, salt length = 16 bytes).
  Re-hashing on login triggers if the cost parameters have changed.
* **JWT access tokens** are RS256, 15-minute expiry, claims: `sub`
  (user id), `iat`, `exp`, `iss`, `aud`, `type`, `role`, `scopes`.
* **Refresh tokens** are RS256, 30-day expiry, `jti` claim. The
  server records `jti` in `revoked_token` until expiry. Logout revokes
  immediately.
* **API keys** are 32 random bytes (base64url), prefixed with
  `dck_live_` (or `dck_test_` in test env). The first 12 characters
  (`prefix`) are kept verbatim in the DB for display; the rest is
  stored as `SHA-256(prefix + ":" + key)`.
* **Multi-factor authentication** is on the roadmap. Until then,
  admin-only routes are gated on `is_admin` *and* a recent
  re-authentication.

## Authorization

* **Roles**: `admin` > `user` (plans are orthogonal: `free` / `pro` / `enterprise`).
* **Scopes** (on API keys): `files:read`, `files:write`,
  `convert:read`, `convert:write`, `batches:read`, `batches:write`,
  `admin:*`. Each route advertises the required scope.
* **Plan quotas** are enforced in `services/quota.py` (per-user,
  per-day, configurable).

## Transport

* All external traffic must be served over TLS. The included nginx
  config sets HSTS (`max-age=63072000; includeSubDomains; preload`),
  redirects HTTP→HTTPS, and pins TLS 1.2+.
* Cookies, when added, will be `Secure; HttpOnly; SameSite=Lax`. (We
  don't use cookie auth today — the SPA stores the JWT in
  `localStorage`.)

## Webhook signing

Outbound webhooks carry these headers:

```
POST /your/webhook HTTP/1.1
Content-Type: application/json
X-DocConv-Delivery: 9c5b…
X-DocConv-Event:    task.succeeded
X-DocConv-Timestamp: 1730000000
X-DocConv-Signature: sha256=<hex hmac-sha256 of "ts.body" with the shared secret>
```

Replay window is 5 minutes. Verify on receipt:

```python
import hmac, hashlib, time, sys

SECRET = b"…"
ts = request.headers["X-DocConv-Timestamp"]
sig = request.headers["X-DocConv-Signature"].removeprefix("sha256=")
if abs(time.time() - int(ts)) > 300:
    abort(401)
expected = hmac.new(SECRET, f"{ts}.{request.body.decode()}".encode(), hashlib.sha256).hexdigest()
if not hmac.compare_digest(expected, sig):
    abort(401)
```

## Sandboxing

Conversion subprocesses run with:

* `setsid` — own process group, immune to signal leakage
* `RLIMIT_AS` — virtual memory cap (default 1 GiB)
* `RLIMIT_CPU` — soft + hard CPU cap (default 60 s)
* `RLIMIT_NPROC` — fork bomb mitigation
* `RLIMIT_FSIZE` — output file cap
* Wall-clock timeout (default 300 s, abort with SIGKILL)
* No network access for the conversion subprocess (configurable)
* A scratch directory owned by the worker; cleaned up on exit

LibreOffice is started with `-env:UserInstallation=file:///<scratch>`
so concurrent workers never share a profile.

## Antivirus

If `ANTIVIRUS_ENABLED=1`, every uploaded file is streamed to
ClamAV (`clamd` over `INSTREAM`) before any further processing.
Quarantined files get `scan_status='infected'` and 0 downstream work.

## Rate limiting

`slowapi` with a Redis backend. Per-route limits are documented in
[api.md](api.md). When the limit is hit, the response is `429` with
`Retry-After: <seconds>`.

## Audit log

Every privileged action (admin route hit, role change, file delete,
API key revoke, login) is written to `audit_log` with `(actor_id,
action, target_type, target_id, ip, user_agent, request_id, ts)`.
The audit log endpoint is admin-only.

## Secrets management

* Production secrets live in the deployment platform (Kubernetes
  Secret / Docker Secret / SSM). They are never baked into images.
* `.env` files are git-ignored. The `.env.example` shipped is a
  template; replace every `CHANGE_ME`.
* JWT private keys are generated on first start and persisted to a
  mounted volume. To rotate, run `python -m app.scripts.generate_jwt_keys`
  with a new `--force`, then restart API replicas; refresh tokens
  signed with the old key remain valid until their own expiry.

## Compliance notes

* **GDPR**: `users.email` is the only required PII. We support
  right-to-erasure via `DELETE /v1/users/{id}` (admin only), which
  soft-deletes the user, anonymises owned rows, and hard-deletes
  files + tasks after 30 days.
* **SOC 2**: every admin action is logged; key rotation procedures
  are documented in `docs/operations.md`.

## Reporting a vulnerability

Email `security@docformatconverter.example.com` (GPG key on the repo
homepage). We aim to acknowledge within 48h.
