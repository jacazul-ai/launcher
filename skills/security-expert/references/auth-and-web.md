# Authentication, Authorization and Web

Access control asks whether a principal may perform an operation on a
resource. The identity layer asks whether the system knows which
principal, session and assurance level the request belongs to. Review
both, and remember the effective policy is the weakest path to the same
operation.

References:
- OWASP Top 10 Proactive Controls: https://owasp.org/www-project-proactive-controls/
- OWASP ASVS: https://owasp.org/www-project-asvs/
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/

## Access Control

- Deny by default; check principal and resource on every route that
  reads or changes data.
- Enforce tenant and owner scope in the query itself, not only on the
  object after fetching it.
- Compare every door to the same operation: UI, API, batch, export,
  retry, legacy and admin routes.
- A user-controlled key that selects a record (an ID in the path or
  body) is authorization input; check the caller owns it.

## Sessions and Cookies

- Rotate the session on login, privilege change and MFA completion;
  invalidate it on logout, password change and account disable.
- Sensitive cookies: `Secure`, `HttpOnly`, a `SameSite` value that fits
  the flow, the narrowest `Domain` and `Path`.
- State-changing routes that rely on cookies need an anti-CSRF token or
  strict origin checks.

## Tokens

- **JWT:** verify the signature with a server-pinned algorithm and key,
  then `exp`, `nbf`, `iss` and `aud`. Treat `kid`, `jku` and `x5u` as
  untrusted. A valid token for another service is invalid here.
- **OAuth/OIDC:** exact `redirect_uri` matching, `state` bound to the
  session, PKCE, and ID-token issuer, audience and nonce checks.
- **API keys:** bind each key to its tenant, scope and environment on
  the server; never let request parameters widen it. Keep keys out of
  URLs, client bundles and logs.

## MFA and Recovery

- Enrolling, replacing or disabling a factor needs fresh
  authentication.
- A completed step-up upgrades only the session and action it was
  issued for.
- Password reset, account recovery and email or phone change are often
  the weakest path: random single-use tokens, short expiry, and
  invalidation of older tokens and sessions.
- Linking a new identity provider or passkey requires a current session
  and proof of ownership of the new identity.

## HTTP Boundaries

- `Host`, `Forwarded`, `X-Forwarded-*`, `Origin` and `Referer` are
  caller-supplied unless a trusted proxy strips and rewrites them. Do
  not build reset links, callbacks or tenant routing from them blindly.
- A response that varies on an input missing from the cache key can be
  poisoned for everyone.
- CORS: allowlist origins; never reflect the request origin together
  with credentials.

## What Is Not a Finding Alone

A missing header, cookie flag, MFA prompt or rate limit, without an
accepted invalid request, cross-principal impact or credential exposure.
Report it as hardening.
