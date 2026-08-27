# Visioret — Pre-Defense Review Plan

Structured review of the whole project before the thesis defense, split into
checkpoints so it can be run over several sessions rather than one large pass.

**Rules for this review**
- One checkpoint at a time. Stop and report after each; wait for a go-ahead.
- Findings are recorded here under each checkpoint as they're confirmed.
- Every claim must be verified against the running system or the actual file,
  never asserted from memory.
- Severity: 🔴 blocks deployment/defense · 🟠 should fix · 🟡 worth knowing ·
  ⚪ informational.

**Status legend:** ⬜ not started · 🔄 in progress · ✅ done

---

## R1 — Repository & configuration hygiene ✅

Files, secrets, dead code, dependency pinning, git state, Docker/compose
config, `.gitignore`, `.dockerignore`, stale documentation.

## R2 — Model & ML pipeline ✅

Training script correctness, data splitting and leakage, checkpoint handling,
evaluation scripts, reproducibility (seeds, persisted splits), the OOD gate,
Grad-CAM generation, and whether the reported numbers can actually be
regenerated from the repo.

## R3 — Backend API ✅

Every endpoint: request validation, error handling, status codes, response
shapes, DB session handling, migration chain integrity, and whether the ORM
models match the migrations and the live schema.

## R4 — Frontend ✅

Build integrity, routes, component structure, state management, API
integration, loading/error/empty states, and dead code.

## R5 — Security & privacy ✅

Full authorization matrix re-verified end to end, secret handling, CORS,
password storage, JWT handling, input validation, file-upload safety, and
data exposure (including the anonymous-session boundary).

## R6 — Accessibility & responsive ✅

Heading structure, keyboard operation, focus management, contrast in both
themes, reduced motion, and layout from 320px to wide desktop.

## R7 — End-to-end functional test ⬜

Walk every real user flow against the running stack as each role
(anonymous / viewer / reviewer / admin), including the failure paths:
non-OCT rejection, bad credentials, permission denials, empty states.

## R8 — Deployment readiness ⬜

What actually happens on a fresh machine: clean-clone startup, migrations,
model/CLIP weight acquisition, environment variables, data persistence,
resource needs, and an honest list of what is *not* production-ready.

## R9 — Documentation & defense readiness ⬜

README accuracy, stale docs, reproducibility instructions, and a short list
of the questions a professor is most likely to ask with where the evidence
lives.

---

# Findings

## R6 — Accessibility & responsive

Scope covered: heading structure, landmarks, keyboard operation, focus
management, contrast in both themes, reduced motion, touch targets, and
layout from 320px upward. Measured in the browser.

### 🟠 R6-1 — The animation-gating guard was used in 1 of 5 places

`frontend/src/lib/motion.ts` exists specifically for one hazard: browsers
pause `requestAnimationFrame` in hidden tabs, so any animation starting from
a "zero" state can leave content showing something wrong. Its own docstring
says components animating *from* an empty state must skip the animation when
`canAnimate()` returns false.

It was called in exactly **one** component (`ProbabilityDistribution`). Four
others checked only `useReducedMotion` — including **`App.tsx`'s route
wrapper, which starts at `opacity: 0` and therefore gates every page's entire
content**.

Measured, not theorised — with `document.visibilityState === "hidden"`:

```
#main > div   inline style: "opacity: 0; transform: translateY(6px);"
              computed opacity: 0     (indefinitely)
```

A page opened in a background tab (ctrl-click, or a session restore with
several tabs) mounts with its content present in the DOM and invisible on
screen. `reduceMotion` alone is the trap: it looks like it covers the "don't
animate" case and covers only half of it.

**Fixed** — `App.tsx`, `ScanAnalysis`, `MetricsSection` and `UserMenu` now all
route through `canAnimate()`. The guidance in `motion.ts` was extended to say
that `opacity: 0` is the same hazard wearing a different hat.

### 🟡 R6-2 — Two touch targets below the WCAG 2.2 minimum

At 320px, measured heights:

| Target | Before | After |
|---|---|---|
| Header "Sign in" link | **16px** | 24px |
| Login page "Need an account? Register" | **16px** | 24px |

WCAG 2.2 AA (2.5.8 Target Size) asks for 24×24. Both were bare text links
with no vertical padding — a thin strip to hit on a phone. Fixed with
`inline-flex min-h-6 items-center`, which grows the hit area without changing
the type size. Re-verified at 320px: **zero targets below the minimum**.

### ✅ Verified correct

- **No horizontal overflow at 320px on any route** — `/`, `/history`,
  `/login`, `/profile`, `/metrics`, `/404`. `scrollWidth` equals the viewport
  and no element exceeds it.
- **Contrast passes in both themes**, on clean page loads, across all six
  routes — zero failures against 4.5:1 (3:1 for large text), computed from
  composited backgrounds rather than eyeballed.
- **Heading structure**: exactly one `<h1>` per route, no skipped levels
  anywhere.
- **Landmarks**: one `<main>`, one `<nav>`, one `<header>` per page, plus a
  working "Skip to content" link.
- **Zero clickable `<div>`s**, zero images without `alt`, zero buttons or
  links without an accessible name, across every route.
- **Focus indicator** is defined globally in `index.css`:
  `:where(a, button, input, select, textarea, [tabindex]):focus-visible {
  outline: 2px solid var(--vr-accent); outline-offset: 2px }` — one rule
  covering every interactive element rather than per-component utilities.
- **Reduced motion** handled globally: decorative animations disabled and all
  transitions collapsed to 0.01ms under `prefers-reduced-motion: reduce`.
- The hidden file input is correctly `aria-hidden="true"` + `tabIndex={-1}` +
  `sr-only`, driven by a visible "Browse files" button — the right pattern,
  not an unlabelled control.

### Three false alarms, and what caused them

Recorded because the measurement mistakes are more instructive than the
findings:

1. **"Contrast fails in ~6 places per route."** My first contrast script
   parsed colours with a regex, which cannot read Tailwind v4's `oklab()`
   backgrounds — it read `oklab(0.999994 …)` (white) as near-black and
   reported the site logo at 1.13:1. Rewritten to resolve colours through a
   canvas, which handles any CSS colour syntax; the failures disappeared.
2. **"The 'Online' label fails at 2.56–2.81:1."** An artifact of driving
   navigation with `pushState` in a loop: `ThemeContext` re-applied its own
   `data-theme` on re-render, so measurements ran against a mixed state
   (light-theme text colour on a dark background). On clean page loads the
   same element measures **7.6:1**.
3. **"The theme toggle does nothing."** `button.click()` did not flip it, and
   I reported that before finishing the diagnosis. A properly constructed
   `MouseEvent` with `view: window` toggles it correctly — light → dark,
   persisted, `aria-label` updated. **The toggle is not broken.**

### Not verified

Keyboard `Tab` traversal could not be exercised: key events do not reach the
page while the browser pane is not displayed, and programmatic `.focus()`
does not trigger `:focus-visible`. The global focus rule is confirmed present
in the stylesheet and every interactive element is confirmed focusable, but
the ring was not observed rendering under real keyboard navigation. Worth one
manual pass before the defense.

### R6 verdict

Structure, contrast, landmarks and responsive behaviour are in good shape and
were already solid before this pass. The one substantive finding is R6-1 —
not a styling issue but the same animation-gating class that has now produced
seven separate defects in this project, which is the argument for the guard
being mandatory rather than optional.

---

## R5 — Security & privacy

Scope covered: the authorization matrix end to end, the anonymous-session
boundary, JWT handling, secret handling, CORS, password storage, injection,
XSS, file-upload safety, rate limiting, and security headers. Everything
below was **executed against the running stack**, not reasoned about.

### 🟠 R5-1 — No security headers on any response

`curl -I` on both the frontend and the API returned none of
`X-Frame-Options`, `Content-Security-Policy`, `X-Content-Type-Options`,
`Referrer-Policy` or `Permissions-Policy`. The `Referrer-Policy` gap
compounds R3-6: `/media/scans/<uuid>.jpg` *is* the capability for that image,
so leaking it in a `Referer` header to any third-party link is a real
disclosure.

**Fixed** in `frontend/nginx.conf`: `X-Frame-Options: DENY` (this app has
reviewer action controls — framing it is a clickjacking route to them),
`nosniff`, `strict-origin-when-cross-origin`, a `Permissions-Policy` denying
camera/mic/geolocation, and a CSP with `script-src 'self'` and
`frame-ancestors 'none'`. `server_tokens off` also drops the nginx version
banner.

Two mistakes made and corrected while writing it, both worth recording:

1. **The headers were declared once at server level and applied to nothing.**
   nginx's `add_header` does not merge across levels — a `location` block
   containing *any* `add_header` discards every inherited one. Both locations
   here set `Cache-Control`, so the security headers would have silently
   vanished from every response the site actually serves. They are now
   repeated in each block, with the rule written down above them.
2. **The CSP broke the app, and my own comment asserted it wouldn't.** The
   comment claimed "no inline scripts are used"; `index.html` had an inline
   theme-bootstrap script, and the Google Fonts stylesheet was blocked too.
   Verified in the browser:
   `Executing inline script violates ... script-src 'self'` and
   `Loading the stylesheet 'https://fonts.googleapis.com/...' violates ...`.
   Rather than weaken `script-src` to `'unsafe-inline'`, the script moved to
   `public/theme-init.js` (external, same-origin, still synchronous so the
   no-flash behaviour is preserved); `fonts.googleapis.com` and
   `fonts.gstatic.com` were added to `style-src`/`font-src`. Re-verified:
   **zero CSP violations**, `data-theme="dark"` applied, Inter and IBM Plex
   Mono both loaded.

### 🟠 R5-2 — Authentication was completely unthrottled

Measured: **20 failed logins in 4.1 seconds, all 401, no back-off**. bcrypt's
~200ms cost is the only brake, which still permits thousands of guesses per
hour against a known address and does nothing about cheap address
enumeration.

**Fixed** with `backend/rate_limit.py` — a fixed-window limiter, no new
dependency: 10 failed logins per 5 minutes, 5 registrations per hour, per
client address. Successful logins **clear** the counter, so only failures
accumulate and somebody signing in and out repeatedly is never locked out.
The module states its own limits honestly: process-local state is correct for
a single-instance deployment and would need shared storage behind multiple
workers; a fixed window can allow up to 2x the limit across a boundary, which
at these numbers is still far below what makes online guessing viable.

Verified: `401 ×10 → 429 ×4`, `retry-after: 280`, and 3 failures → success →
9 further failures all 401, proving the reset works.

### 🟡 R5-3 — API docs are publicly reachable

`/docs`, `/redoc` and `/openapi.json` all return 200 to anonymous callers,
exposing the full endpoint surface and schemas.

**Left as-is, deliberately.** For a research demo this is a feature — the
README points examiners at it, and every endpoint behind it is authorization-
checked independently. Noted here so it is a decision rather than an
oversight; a deployment with real patient data should gate or disable it.

### ✅ Verified correct — nothing found

- **JWT handling.** Every forgery attempt rejected with 401: tampered
  signature, `alg=none`, HS256 signed with a guessed key, expired-but-validly-
  signed, a token for a nonexistent user id, and garbage. Only the genuine
  token returned 200.
- **Anonymous session isolation** — the privacy boundary added earlier this
  project, now proven rather than asserted. Two sessions each submitted a
  scan:

  | Caller | Sees |
  |---|---|
  | session A | `[52]` — its own only |
  | session B | `[53]` — its own only |
  | no session header | `[]` — nothing |
  | signed-in viewer | `[39]` — own scans only |
  | viewer **+ A's session header** | `[39]` — the header does not widen access |
  | reviewer | all 20 — by design |

  Direct IDOR also blocked: A requesting B's scan by id → **404**, its own →
  200, no header → 404.
- **Privilege escalation is impossible through the API.** Admin granting
  admin → 400. Admin demoting another admin → 400. Admin changing own role →
  400. Viewer `PATCH /api/auth/me {"role":"admin"}` → 400, role unchanged.
- **SQL injection** via `X-Anon-Session` (`' OR '1'='1`, `'; DROP TABLE
  scans;--`, LIKE-wildcard abuse) and via the login email: all returned
  0 scans / 401, and the `scans` table still holds its 20 rows. SQLAlchemy
  parameterises throughout.
- **XSS proven inert by execution, not by trusting React.** Stored
  `<img src=x onerror=alert(1)><script>alert(2)</script>` as a feedback
  comment, then rendered the page and counted: **0 injected `<img>` tags, 0
  injected `<script>` tags**, payload present as literal text. No
  `dangerouslySetInnerHTML`, `innerHTML`, `eval` or `new Function` anywhere
  in `frontend/src`.
- **CORS** allows only `http://localhost:5173`; `evil.example.com` and `null`
  receive no `Access-Control-Allow-Origin` at all.
- **Password storage**: every row is a 60-char `$2b$12$` bcrypt hash. No
  plaintext, and no endpoint echoes a hash — `/api/auth/me` returns only id,
  name, email, role.
- **Over-long session ids** (500 chars) are truncated to the column width and
  handled, not 500'd.
- **No secrets in the built frontend bundle** — searched for the JWT secret,
  database credentials, and the strings `secret`/`postgres`: zero hits.
- **`/.env`, `/.git/config`, `/nginx.conf` are not exposed.** These return
  200, which looks alarming until you read the body: it is `index.html` via
  the SPA fallback, and none of those files exist in the frontend image at
  all (it contains only `index.html`, `favicon.svg`, `theme-init.js`,
  `50x.html` and `assets/`). Checked rather than reported.
- Static-file path traversal blocked (re-confirmed from R3).

### R5 verdict

No exploitable vulnerability found. The parts that matter most for a medical
demo — authorization, the anonymous privacy boundary, JWT integrity, and
injection resistance — are all correct under direct attack. The two real gaps
were *missing defences* rather than broken ones (no headers, no throttling),
and both are now in place and verified.

---

## R4 — Frontend

Scope covered: build integrity, routes, component structure, state
management, API integration, loading/error/empty states, dead code. Findings
were reproduced **in the running app** via the browser, not read off the
source.

### 🔴 R4-1 — Every validation error rendered as `[object Object]` *(regression from R3)*

Caused by the R3 fixes in this same review. FastAPI returns two different
error bodies:

```
HTTPException   -> { detail: "Some message" }              (string)
422 validation  -> { detail: [{loc, msg, type}, ...] }     (array)
```

`handleResponse` did `detail = body.detail ?? detail` and passed the result
straight to `new ApiError(...)`. Before R3 those inputs produced 500s with a
string body, so the array shape never arose. After R3 they are 422s — and
every one of them reached the user as literally `[object Object]`. Confirmed
in the browser, not inferred:

> Password
> At least 8 characters.
> **[object Object]**

**Fixed** with `extractErrorDetail()`, which handles both shapes and turns
`loc: ["body","password"]` into a field name. Same probe now reads:

> **password: String should have at most 72 characters**

This is the cost of changing an API contract without checking the consumer.
The backend fix was correct in isolation and made the product worse.

### 🟠 R4-2 — `index.html` was served with no `Cache-Control`

Found while trying to verify R4-1 and getting stale results. `nginx.conf`
sent only `ETag`/`Last-Modified` for `index.html`, so browsers applied
**heuristic caching** (roughly 10% of the document's age) and could serve it
without revalidating. Observed directly: the container was serving
`index-CYwRzeL-.js` while the browser kept running `index-C0D7cNFv.js`.

This is a deployment bug, not a test annoyance. Vite emits content-hashed
bundle names, so a stale `index.html` points at a filename that **no longer
exists** after the next deploy — the failure mode is not "slightly old code",
it is a blank page with `Failed to load module script`.

**Fixed**: `index.html` → `Cache-Control: no-cache` (store, but always
revalidate — the ETag makes that a cheap 304); `/assets/*` → `public,
max-age=31536000, immutable`, which is safe precisely because those names are
content-hashed. Verified both headers on the live server.

### 🟠 R4-3 — Unknown routes rendered a blank page

No catch-all `<Route>`. `/this-route-does-not-exist` rendered the header and
an empty `<main>` — measured `innerText.length === 0`. A mistyped URL or a
stale bookmark produced a blank screen with no message and no way onward.
**Fixed** with `NotFoundPage`.

### 🟠 R4-4 — No error boundary anywhere

React unmounts the whole tree when a render throws, so any single component
error blanked the entire application — header, nav and all. That is the worst
possible failure during a live demonstration: no message, no route, no way
back except knowing to reload. **Fixed** with `ErrorBoundary`, keyed on
pathname so navigating away clears a latched error, offering both "Try again"
and "Reload".

### 🟠 R4-5 — The metrics page asserted something untrue

The footnote under the results read:

> "Test splits are patient-disjoint: no patient contributing to a training set
> appears in the corresponding test set."

R2 measured that this is **not true** of the Kermany split. Leaving it would
have meant asserting a disproved claim in the place a reader trusts most —
directly beneath the numbers. **Rewritten** to state the grouping caveat, the
41% figure, and the measured 0.9750-vs-0.9180 comparison showing the numbers
understate rather than overstate.

### 🟡 R4-6 — Authorization outcomes were rendered as errors

An anonymous visitor opening `/metrics` saw **"Error. Not authenticated."** —
a correct authorization decision presented as a fault, on the page an
examiner is most likely to open first. **Fixed**: 401 and 403 are now
distinguished from real failures and rendered as explanatory empty states
("Sign in to view evaluation results" / "Reviewer access required", the
latter explaining *why* the role gates it).

### 🟡 R4-7 — `fetchMe()` fired on every load, and a blip signed you out

`AuthProvider` called `fetchMe()` unconditionally, so every anonymous visit
made a guaranteed-401 request — and *any* failure, including a transient one
while the backend restarts, cleared the user while leaving the token in
localStorage, so the app showed signed-out until a manual reload.

**Fixed**: skip the call entirely when there is no token, and only clear the
token on a genuine 401. Verified — an anonymous page load now issues **zero**
`/api/auth/me` requests (backend request count unchanged across a reload).

### ✅ Verified correct

- **`tsc -b` passes clean.** `oxlint` reports only two `only-export-components`
  fast-refresh warnings in the context files — dev ergonomics, not defects.
- **No dead code.** Swept every module for unreferenced files and every
  exported symbol for unused exports; the six flagged candidates
  (`getToken`, `Identicon`, the four request interfaces) are all used
  internally.
- **`api/types.ts` matches `backend/schemas.py` exactly** — every response
  model, field name and nullability lines up.
- The `AnimatedRoutes` comment documenting why `AnimatePresence mode="wait"`
  was rejected is accurate and worth keeping: it is the fix for the
  navigation-gating bug class.
- `AdminPage` is a good model for the rest — loading, error, empty and busy
  states all handled, non-admins redirected, accessible table with `scope`
  and a `<caption>`.
- History empty state renders honest copy about session-scoped anonymous
  history.
- Reviewer view of `/metrics` renders both splits correctly, with the
  hash-keyed model label `resnet50_oct_91dfa561392c432c` and a
  row-normalised confusion matrix.

### R4 verdict

The component structure, typing and state handling are in good shape, and
there is no dead code — but the review found **one regression it had caused
itself**, plus a caching misconfiguration that would have shipped stale or
broken bundles to returning users. Both were only visible by running the app.

---

## R3 — Backend API

Scope covered: all 12 endpoints, `schemas.py`, `auth.py`, `db/models.py`,
`db/session.py`, `storage.py`, the migration chain, and ORM-vs-live schema
drift. Findings below were **probed against the running API**, not inferred
from reading.

### 🟠 R3-1 — Input that exceeds a column length returns 500, not 400

`RegisterRequest` and `FeedbackCreate` declare bare `str` fields with no
length limits, but the columns behind them are bounded. Postgres raises
`StringDataRightTruncation`, which nothing catches.

| Probe | Column | Result |
|---|---|---|
| `POST /api/auth/register` with a 200-char name | `users.name` `String(120)` | **HTTP 500** |
| `PUT /api/scans/{id}/feedback` with a 2000-char comment | `feedback.comment` `String(1000)` | **HTTP 500** |

Worth noting `PATCH /api/auth/me` *does* validate name length (≤120) and
returns a clean 400 — so the rule exists, it just isn't applied at
registration. The validation belongs in the Pydantic schema
(`Field(max_length=...)`), where it covers every endpoint at once and shows
up in the OpenAPI docs.

### 🟠 R3-2 — `GET /api/scans?limit=` is unvalidated

| Probe | Result |
|---|---|
| `?limit=-1` | **HTTP 500** (SQL `LIMIT -1`) |
| `?limit=999999` | **HTTP 200** — no upper bound |
| `?limit=abc` | HTTP 422 (FastAPI's int coercion, correct) |

The unbounded case compounds with **R3-3**: 999,999 rows is also ~2 million
lazy-load queries.

### 🟠 R3-3 — N+1 queries in `GET /api/scans`

The loop touches `scan.predictions` and `scan.user` per row, both lazy. At
the default limit of 50 that is ~101 queries for one request. Fix is
`selectinload(Scan.predictions)` / `joinedload(Scan.user)`.

Related, and separately visible to users: scans without predictions are
filtered out **after** the limit is applied, so `?limit=50` can return fewer
than 50 rows while more exist.

### 🟠 R3-4 — Decompression bomb returns 500 and allocates freely

A **459 KB** PNG expanding to 22000×22000 (484 megapixels) was accepted, and
`Image.open(...).load()` raised past the handler:

```
POST /api/predict  (bomb.png, 459 KB)  ->  HTTP 500
```

`except UnidentifiedImageError` is too narrow — Pillow raises
`DecompressionBombError` here, and truncated files raise `OSError`. The
container was already OOM-killed once today by ordinary work, so an unbounded
allocation triggered by a half-megabyte upload is a live risk, not a
theoretical one. Fix: catch `Exception` around image decode and return 400,
and set an explicit `Image.MAX_IMAGE_PIXELS`.

### 🟠 R3-5 — No upload size limit anywhere in the stack

An 80 MB body was read fully into memory before being rejected:

```
POST /api/predict  ->  HTTP 400, uploaded 83,886,278 bytes in 0.49s
```

`await file.read()` buffers the whole request. Rejection happens only after
the entire body has been accepted. A handful of concurrent large uploads is
enough to exhaust container memory.

### 🟡 R3-6 — `/media` is served with no authentication

Scan images are public to anyone with the URL:

```
GET /media/scans/<uuid>_original.jpg   (no token)  ->  HTTP 200
```

Filenames are `uuid4().hex`, so they are not guessable, and **path traversal
is correctly blocked** (`/media/../main.py` and the percent-encoded variant
both 404 — Starlette's `StaticFiles` is safe here). But the ownership rules
that `_visible_scans_query` enforces so carefully on metadata do not apply to
the images themselves: a URL shared or logged anywhere grants permanent
access to a medical image. Worth a deliberate decision rather than an
accident.

### 🟡 R3-7 — Migration `e96f48ad79fb` cannot run against existing rows

`op.add_column('users', sa.Column('password_hash', ..., nullable=False))`
with no `server_default` and no backfill. Verified by replaying the chain on
a scratch database with one user row present:

```
Running upgrade 53b8feed0825 -> e96f48ad79fb, add users.password_hash
psycopg2.errors.NotNullViolation: column "password_hash" of relation
"users" contains null values
```

It worked originally because the table happened to be empty. Anyone restoring
a backup from before that revision cannot upgrade. The standard shape is: add
nullable with a `server_default`, backfill, then `alter_column` to NOT NULL.

### 🟡 R3-8 — Smaller items

- **No `pool_pre_ping`** in `create_engine`. After the database container
  restarts — which happened today — pooled connections are dead and requests
  fail until the pool turns over. One argument fixes it.
- **`register` reveals whether an email exists** ("An account with this email
  already exists"), while `login` correctly does not distinguish. Login is
  also measurably faster for an unknown email, since `verify_password` is
  skipped — a timing oracle for the same information.
- **No email format validation.** `POST /api/auth/register` with
  `"definitely-not-an-email"` returned **HTTP 200** and created the account.
  `EmailStr` is one import.
- **Files are written to disk before the DB commit** in `/api/predict`, so a
  failed commit leaves orphaned JPEGs.
- **`Prediction` has no cascade from `Scan`**, so deleting a scan orphans its
  predictions — `purge_anonymous.py` already works around this by hand, which
  is the tell.
- **`users.role` is NOT NULL with no server default** — the `default="viewer"`
  is Python-side only, so raw SQL inserts must supply it.

### ✅ Verified correct

- **Authorization matrix, probed end to end** — every cell is right:

  | Endpoint | anon | viewer | reviewer | admin |
  |---|---|---|---|---|
  | `GET /api/metrics` | 401 | 403 | 200 | 200 |
  | `GET /api/admin/users` | 401 | 403 | **403** | 200 |
  | `PUT /api/scans/{id}/feedback` | 401 | 403 | 200 | 200 |
  | `GET /api/auth/me` | 401 | 200 | 200 | 200 |
  | `GET /api/health` | 200 | 200 | 200 | 200 |

  Note reviewers correctly get **403** on admin endpoints — the privilege
  split is real, not cosmetic.
- **Migration chain**: 7 revisions, linear, exactly one head, no branches.
- **Replays cleanly onto a brand-new database** — all 7 applied, all 7 tables
  created.
- **Zero schema drift**, checked with `alembic.autogenerate.compare_metadata`
  against both the live database *and* a freshly-migrated one. The ORM models
  and the migrations agree exactly.
- **Path traversal blocked** on the static mount; the mount points at
  `backend/media/`, not at the source tree.
- Non-image bytes sent with `image/png` are correctly rejected as 400.
- `_visible_scans_query` is applied to **both** the list and the detail
  endpoint, so a scan hidden from history cannot be opened by guessing its id.
- Roles are resolved from the database on every request, not baked into the
  token, so a demotion or deletion takes effect immediately.
- `JWT_SECRET_KEY` has no fallback; the module refuses to import without it.
- Admin cannot be self-assigned, granted via the API, or used to modify
  another admin — all three refusals are enforced server-side.

### R3 remediation

| # | Finding | Resolution |
|---|---|---|
| 🟠 R3-1 | Over-length input → 500 | Length bounds moved into `schemas.py` as `Field(max_length=...)`, mirroring the column widths, with the constants named and a header explaining why they belong there rather than in each handler. Covers every endpoint at once and appears in the OpenAPI docs. The duplicated ad-hoc checks in `register`/`update_me` were removed |
| 🟠 R3-1b | **Password > 72 bytes → 500** (found while fixing) | bcrypt 5.x *raises* rather than truncating past 72 bytes, so any long passphrase 500'd at registration. `PASSWORD_MAX = 72` in the schema, plus a byte-accurate guard in `auth.py` — bytes not characters, since non-ASCII hits the limit sooner than the length suggests. `verify_password` now returns `False` instead of raising for an over-long password or an empty/malformed hash |
| 🟠 R3-2 | `?limit=` unvalidated | `Query(default=50, ge=1, le=MAX_SCAN_LIMIT)` |
| 🟠 R3-3 | N+1 queries | `selectinload(Scan.predictions)` + `joinedload(Scan.user)`, and the "has a prediction" filter moved into SQL (`Scan.predictions.any()`) so the limit is applied *after* the filter, not before |
| 🟠 R3-4 | Decompression bomb → 500 | `Image.MAX_IMAGE_PIXELS = 64_000_000` (the largest genuine scan across all four datasets is ~0.8 MP) and explicit handling for `DecompressionBombError` plus a catch-all → 400. Truncated files and broken EXIF are covered by the same change |
| 🟠 R3-5 | No upload size limit | `MAX_UPLOAD_BYTES = 12 MB`, checked against `file.size` *before* reading and against the actual bytes after, since a hand-rolled multipart request can understate its size. Returns **413** |
| 🟡 R3-6 | `/media` unauthenticated | **Kept, and documented as a decision.** The frontend renders these through plain `<img>` tags, which cannot attach an Authorization header; making them private needs signed URLs or an authenticated proxy. The comment in `main.py` now states the actual trade-off — uuid4 filenames mean possession of the link is the capability, and that link stays live indefinitely — and says any deployment holding real patient data must close this first |
| 🟡 R3-7 | Migration fails on populated tables | Rewritten as add-nullable → backfill `''` → set NOT NULL. The empty hash is deliberate: rows predating the migration never had a password, and `verify_password` treats `''` as a non-match, so those accounts simply cannot sign in — better than inventing a credential |
| 🟡 R3-8a | No `pool_pre_ping` | Added, with a note that the db container really has restarted mid-session |
| 🟡 R3-8b | Login timing oracle | `spend_password_verification_time()` burns one bcrypt verification when the email doesn't exist, so both paths cost the same |
| 🟡 R3-8c | No email validation | `EmailStr` on `RegisterRequest` (+ `email-validator` pinned in requirements). `LoginRequest` deliberately keeps plain `str` — validating the format there would let the *validation error* reveal which addresses are even possible, undoing the vague "Incorrect email or password" |
| 🟡 R3-8d | Orphaned files on failed commit | `/api/predict` wraps the DB writes; on failure it rolls back and calls the new `discard_scan_images()`, which resolves basenames only so a database value can never point outside `MEDIA_DIR` |
| 🟡 R3-8e | No cascade `Scan` → `Prediction` | `cascade="all, delete-orphan"` added; combined with Prediction's existing cascades, deleting a scan now removes its predictions, Grad-CAM rows and feedback |

#### Verification — every failing probe re-run

| Probe | Before | After |
|---|---|---|
| register, 200-char name | 500 | **422** |
| register, 100-char password | 500 | **422** |
| feedback, 2000-char comment | 500 | **422** |
| register, invalid email | **200 (account created)** | **422** |
| `?limit=-1` | 500 | **422** |
| `?limit=999999` | 200 | **422** |
| decompression bomb (459 KB / 484 MP) | 500 | **400** |
| 80 MB upload | 400, after buffering 83.9 MB | **413** |

No regressions: register/login/predict all 200, wrong password 401, unknown
email 401, `?limit=50` 200, non-image 400.

| Check | Result |
|---|---|
| Authorization matrix | unchanged — all 16 cells still correct |
| Login timing | known email **0.180s** vs unknown **0.177s** — equalized (previously the unknown path skipped bcrypt entirely) |
| N+1 | **2 queries** for 18 scans, down from ~37 |
| Migration with an existing user row | all 3 remaining revisions apply; legacy row survives with an empty, unusable hash |
| Schema drift | **none**, re-checked after the cascade change |

### R3 verdict

The security model is genuinely sound — the authorization matrix is correct
in every cell, the schema is drift-free, and the migration chain replays
cleanly. What's missing is **input hardening**: four separate inputs produce
500s that should be 400s, and two of them (the decompression bomb and the
unbounded upload) are cheap denial-of-service vectors rather than cosmetic
error-code problems.

---

## R2 — Model & ML pipeline

Scope covered: `train_full.py`, `dataset.py`, `evaluate.py`,
`evaluate_cross_dataset.py`, `inference.py`, `explanations.py`,
`backend/db/write_evaluation.py`, `backend/db/model_version.py`; splitting
and leakage, checkpoint handling, reproducibility, Grad-CAM generation, and
whether the reported numbers can be regenerated.

### 🟠 R2-1 — Patient grouping is keyed on class+id, so it does not group a patient

`model/dataset.py:48` builds the grouping key as:

```python
patient_id = f"{class_name}-{match.group(2)}" if match else entry.name
```

The class name is **prefixed onto the patient id**. Kermany patient `1016042`,
who has images in the CNV, DRUSEN *and* NORMAL folders, becomes three
separate "patients" that `GroupShuffleSplit` may scatter across train, val and
test. The module's own docstring says the opposite —
*"CNV-1016042-155.jpeg -> patient 1016042"* — which is why this reads as
unintentional rather than a considered decision.

Measured over all 84,484 images:

| | |
|---|---|
| Distinct numeric patient ids | 4,657 |
| Ids appearing under more than one class | **896 (19.2%)** |
| Test-split numeric ids also in train | 213 of 825 (25.8%) |
| Test images whose patient was seen in train or val | **5,375 of 13,146 (40.9%)** |

The co-occurrence pattern is clinically coherent — CNV+DRUSEN+NORMAL
dominates, consistent with wet AMD in one eye, drusen in the fellow eye, and
normal slices from both — so the numeric id really does look like one
patient rather than an id collision.

**Impact, measured rather than assumed.** The deployed checkpoint was scored
separately on the two subsets:

| Subset | n | Accuracy | Macro F1 | DRUSEN F1 |
|---|---|---|---|---|
| Full test set (as reported) | 13,146 | 0.9517 | 0.9233 | 0.817 |
| **Leaked** (patient seen in train/val) | 5,375 | **0.9180** | **0.8878** | 0.752 |
| **Clean** (patient never seen) | 7,771 | **0.9750** | **0.9541** | 0.882 |

**The effect runs opposite to memorization.** The model does *worse* on the
leaked patients, not better, so the published 95.17% is **conservative, not
inflated**. The explanation is that leaked patients are by construction the
multi-class patients — a patient carrying both CNV and DRUSEN labels is a
clinically ambiguous case sitting exactly on the boundary the model is
weakest at, which is why DRUSEN F1 drops to 0.752 there.

Two things follow, and they are separate:
1. **The claim needs correcting.** "Patient-disjoint" is not literally true of
   the 13,146-image figure. The defensible patient-disjoint result is the
   clean subset: **97.50% accuracy / 0.9541 macro F1 on 7,771 images**.
2. **No retraining is required to be honest.** Both numbers can be reported
   with the grouping bug disclosed and its direction stated. Fixing the key
   and re-splitting *would* require a retrain, and would move patients
   between splits — worth doing if time allows, but it is not what stands
   between this project and a defensible claim.

Caveat worth stating in the write-up: the clean subset is not a clean
counterfactual either — it is a different population (single-diagnosis
patients, and a higher NORMAL share), so 97.50% should be presented as
"performance on single-diagnosis patients never seen in training", not as a
drop-in replacement for the headline.

**Unaffected:** the external evaluation. OCTDL keys on the numeric id with no
class prefix, Duke keys on the per-patient volume folder, and Noor's class
prefix is *correct* there because patient folders are numbered independently
inside each class folder. The **88.1% / 0.90 cross-dataset result is clean.**

### 🔴 R2-2 — Metrics page is permanently empty on any fresh machine

`backend/db/model_version.py:23` keys `ModelVersion` on the checkpoint file's
**mtime**; `backend/main.py:320` filters `/api/metrics` strictly by that
version id. A `git clone` writes a new mtime, producing a new version label
that matches no stored rows — and the rows cannot be regenerated, because
`evaluate.py` needs the 84k-image dataset that is deliberately not in the
repo.

So an examiner who clones and runs `docker compose up` sees an **empty
metrics page**: the project's headline evidence, missing, on the machine
where it matters most.

Fix direction: key `ModelVersion` on a content hash (sha256 of the
checkpoint) so it is stable across clones and copies, and add a seed path
that loads the committed evaluation results into a fresh database.

### 🟠 R2-3 — Grad-CAM overlays are geometrically distorted

`model/inference.py:145` resizes the *original* down to 224×224 instead of
resizing the *heatmap* up to the original's size. Confirmed against stored
files:

```
original (768, 496)   gradcam (224, 224)   aspect 1.548 -> 1.000
original (512, 496)   gradcam (224, 224)   aspect 1.032 -> 1.000
```

A 768×496 scan's overlay is squashed ~35% horizontally, so in Compare mode
the heatmap does not spatially align with the scan next to it. The model's
reasoning is unaffected — it genuinely saw a squashed 224×224 tensor — but
the *presentation* mislocates the finding for the viewer. The correct fix is
the inverse mapping: resize the CAM to the original's dimensions and overlay
on the full-resolution image.

Note this does not affect `explanations.py`: horizontal position as a
*fraction* of width is preserved under uniform scaling, so left/centre/right
stays correct.

### 🟠 R2-4 — Training is not reproducible

No `torch.manual_seed`, `np.random.seed`, or DataLoader generator seed
anywhere in `train_full.py`. Splitting *is* deterministic
(`GroupShuffleSplit(random_state=42)`, plus the persisted JSON), which is the
part that matters most — but head initialisation, shuffle order and
augmentation are unseeded, so a retrain will not reproduce 95.17%.

### 🟡 R2-5 — Smaller items

- `CLASS_NAMES = ["CNV","DME","Drusen","Normal"]` (`inference.py:12`)
  disagrees in casing with the checkpoint's actual
  `["CNV","DME","DRUSEN","NORMAL"]`. Latent only — both callers pass
  `class_names=` explicitly — but it is a live default parameter and
  `evaluate_cross_dataset.py` has to `.upper()` around it.
- A persisted split silently **drops** any patient added to the dataset
  afterwards, since `filter_by_patients` keeps only listed ids. Safe (it
  cannot cause leakage) but silent — no warning that images were skipped.
- Per-source blocks in the cross-dataset report show `macro avg 0.66` for
  Noor purely because DME has support 0 there. Only the COMBINED block should
  ever be quoted; the per-source macro averages are artefacts.
- `robust_torch_save` retries only `RuntimeError`; a `PermissionError` or
  `OSError` from the same Windows file-locking cause would not be retried.

### ✅ Verified correct

- Kermany's official train/test split really does leak — independently
  reconfirmed. Pooling and re-splitting is the right call.
- `evaluate.py` uses the reserved test patients and a transform matching
  `inference.py` exactly.
- The external collectors pull **only** image files (`.jpg`/`.tif`) — checked
  for stray CSV/README files; there are none. Counts: Noor 16,803 / 441
  patients, OCTDL 479 / 217, Duke 2,508 / 30.
- AMD exclusion (OCTDL, Duke) and Noor's per-B-scan filename labelling are
  implemented exactly as documented.
- Smoke-test checkpoint isolation and the fresh-baseline warm-start
  re-measurement are both correctly in place — the two training bugs recorded
  in TODO.md are genuinely fixed in code.
- `write_evaluation.py` is properly best-effort and never raises into the
  evaluation scripts.
- Grad-CAM hooks (`layer4`, full backward hook) and the CAM computation are
  textbook-correct.
- `explanations.py` makes no anatomical claim it cannot support.
- Reported figures match their source reports: `evaluation_report.txt`
  0.9517/0.9233 and the COMBINED cross-dataset block 0.88/0.90.

### R2 remediation

Constraint set by the user: fix everything that does **not** require
retraining the model.

| # | Finding | Resolution |
|---|---|---|
| 🟠 R2-1 | Class-prefixed patient grouping | **Documented, not silently changed** — changing the key invalidates the persisted split the deployed checkpoint was trained against, which is a retrain. Instead: the contradictory docstring in `dataset.py` is corrected and replaced with a KNOWN LIMITATION section carrying the measured numbers; `collect_samples` carries a warning against changing the key in place; `kermany_numeric_patient_id()` added as the correct key for future use; **`model/audit_patient_leakage.py` added** so the leaked/clean measurement is reproducible by anyone with the dataset instead of being a number I once quoted; `evaluate.py`'s stdout and report header now state the caveat; README and FEATURES both report **two rows** (95.17% full / 97.50% clean) with the direction of the effect explained |
| 🔴 R2-2 | Metrics empty on a fresh clone | `ModelVersion` now keyed on **SHA-256 of the checkpoint's contents** instead of file mtime, so the same weights are the same version on every machine. Evaluation results are additionally exported to **`model/checkpoints/evaluation_metrics.json`** (1.6 KB, committed next to the weights) and seeded into an empty database at startup by **`backend/db/seed_metrics.py`**. The seeder only inserts *missing* splits, so a real local evaluation always beats the committed export, and it refuses to seed when the export's fingerprint doesn't match the checkpoint on disk |
| 🟠 R2-3 | Grad-CAM overlay distorted | `overlay_gradcam` now resizes the **heatmap up to the original's dimensions** instead of shrinking the original to 224×224. The overlay is the same shape as the scan beside it, so a hot region maps back to the right place |
| 🟠 R2-4 | Training unseeded | `SEED = 42` with `seed_everything()` (Python/NumPy/torch/CUDA), a seeded `DataLoader` generator for shuffle order, and `seeded_worker_init` which seeds each worker *and* keeps the OpenCV thread limit that stops CPU oversubscription |
| 🟡 R2-5a | `CLASS_NAMES` casing | Fallback list corrected to upper case to match what training produces, with a comment on why the casing is load-bearing |
| 🟡 R2-5b | Persisted split silently drops patients | `get_or_create_patient_split` now warns with the exact patient and image counts being ignored, and says how to re-split |
| 🟡 R2-5c | Misleading per-source macro averages | Cross-dataset report now opens with a HOW TO READ THIS block explaining that per-source macro averages include zero-support classes as 0.00 and only the COMBINED block should be quoted |
| 🟡 R2-5d | `robust_torch_save` retry scope | Now retries `OSError`/`PermissionError` as well as `RuntimeError` — the same Windows file lock surfaces as any of them, and catching one meant a lock could kill a multi-hour run |

**Not fixed, and deliberately so:** the grouping key itself. It needs a
re-split and a full retrain. The measurement shows the current claim is
conservative rather than overstated, so this is a documentation problem, not
a correctness emergency.

#### Verification

| Check | Result |
|---|---|
| `evaluate.py` re-run | **0.951696 / 0.923307** — reproduces the committed report exactly |
| `evaluate_cross_dataset.py` re-run | **0.881268 / 0.895484** — reproduces exactly (this is the 88.1% in the README) |
| Grad-CAM on 512×496 | overlay 512×496 — matches |
| Grad-CAM on **1536×496** (3.10:1) | overlay 1536×496 — matches; would have been 224×224 before, a 3× horizontal compression |
| Metrics export | `evaluation_metrics.json`, 1.6 KB, both splits, fingerprint `91dfa561392c432c` |
| **Fresh-clone simulation** | metrics table emptied → restart → `Seeded 2 evaluation metric row(s)` → `/api/metrics` serves both splits with per-class metrics and confusion matrices |
| All edited modules | import cleanly |

#### Two things learned during verification, worth recording

1. **`backend/` is baked into the image, `model/` is bind-mounted.** The
   first seeding test failed silently because `docker compose restart` reuses
   the existing image — editing `backend/db/seed_metrics.py` had no effect
   until `docker compose build backend`. Changes under `model/` take effect
   on restart alone. Easy to lose an hour to.
2. **Switching the version key leaves the old rows behind.** The mtime-keyed
   `ModelVersion` row still exists alongside the new hash-keyed one, and the
   predictions made before the switch remain attached to it. That is
   harmless and arguably correct — those predictions really were served under
   that label — and `/api/metrics` filters by the active version, so nothing
   stale is ever displayed.

### R2 verdict

One 🔴 that will embarrass a live demo (empty metrics on a fresh clone) and
one 🟠 that requires a **correction to how the headline result is described**
— though the correction is favourable, since the true patient-disjoint number
is higher, not lower. No evidence of any result being overstated.

---

## R1 — Repository & configuration hygiene

Scope covered: git state, secret handling, `.gitignore` / `.dockerignore`,
`docker-compose.yml`, both Dockerfiles, dependency pinning, tracked data,
dead code, debug leftovers, and documentation accuracy.

### 🔴 R1-1 — `README.md` describes a project that no longer exists

The README still calls Visioret *"a midterm progress demo (Streamlit, single
machine, no backend/database/deployment)"*. It documents `streamlit run
app.py` and `python model/train_quick.py` as the way to use the project, and
a "Project structure" section listing 5 files.

It does not mention FastAPI, React, PostgreSQL, Docker, Alembic,
authentication, roles, `train_full.py`, the CLIP OOD gate, the four datasets,
or any measured result. It also claims the ResNet50 weight download is
*"the only network access the project makes"* — no longer true, since CLIP
weights are fetched from HuggingFace on first run.

This is the single highest-impact defect found in R1: the README is the first
thing an examiner opens, and following it produces the *old* midterm demo, not
the system being defended. **Must be rewritten before the defense.**

### 🟠 R1-2 — 25 files uncommitted, including a migration

`git status` shows 16 modified/deleted and 9 untracked files — the entire
roles / admin / avatar / theme / anonymous-session body of work, including
`backend/alembic/versions/c6c94791979f_anonymous_session_scoping.py` and six
new frontend source files. Last commit is `e9a2d18`.

Risk: an unversioned migration plus unversioned code means a clean clone of
`main` today produces a **broken, older application**. Also nothing is
recoverable if the working tree is lost. Should be committed as a few logical
commits (roles/RBAC, admin, anonymous scoping, UI polish, docs).

### 🟠 R1-3 — `JWT_SECRET_KEY` is a literal value in `docker-compose.yml`

```yaml
JWT_SECRET_KEY: af84dfee2ddbd9c73b283ab7abe5de725b990abbf5169c0a25c2543261b67299
```

It is commented as dev-only and sits beside equally hardcoded dev DB
credentials, so the intent is clear and `.env` itself is correctly untracked
(verified — no real secret leak). But it is a committed signing key: anyone
with the repo can forge a valid token against any deployment that forgets to
override it. Should move to `env_file:` / `${JWT_SECRET_KEY:?}` so compose
*fails loudly* rather than silently using the public value.

### 🟠 R1-4 — `.env.example` omits `JWT_SECRET_KEY`

`.env.example` contains only `DATABASE_URL`. `backend/auth.py` deliberately
raises `RuntimeError` when `JWT_SECRET_KEY` is unset (correct — no insecure
fallback), so a fresh clone run **outside** Docker crashes at import with no
hint that the example file is incomplete.

### 🟠 R1-5 — Dependencies are floor-pinned, not pinned

Every line in `requirements.txt` uses `>=` (`torch>=2.5.0`,
`transformers>=4.45.0`, …). A rebuild months from now resolves different
versions, and for an ML project whose reported numbers are the deliverable,
that undermines the reproducibility claim. The frontend is fine —
`package-lock.json` is tracked and the Dockerfile uses `npm ci`.

Recommended minimum: pin `torch`, `torchvision`, and `transformers` exactly,
since those three decide whether the checkpoint and the CLIP gate behave
identically.

### 🟡 R1-6 — `PROJECT_CONTEXT.md` OOD section is stale

Line 168 states the gate is *"Three stages, cheapest first, all in
`model/ood_detector.py`"* and presents `compute_ood_stats.py` /
`ood_stats.pth` as live calibration. That third stage was retired in favour
of CLIP. The file also still opens as a session-handoff document written
"right after Checkpoint 1".

### 🟡 R1-7 — `UI_REDESIGN_BRIEF.md` describes the pre-redesign UI

370 lines specifying a redesign that has since been implemented. Harmless
internally, but confusing to anyone reading the repo, since it reads as a
statement of the current UI. Either mark it historical or delete it.

### 🟡 R1-8 — Retired OOD code path still present

`model/ood_detector.py` retains `compute_ood_stats` / `ood_distance` /
`load_ood_stats`, `model/compute_ood_stats.py` is now a script for a retired
technique, and `model/checkpoints/ood_stats.pth` (24 KB) is a stale artifact.

Verified this is **inert**, not a live bug: `check_is_oct` runs only the
grayscale heuristic then `clip_is_oct`, and the module docstring explains why
the code was kept. Defensible as "evidence of the experiment", but worth
being ready to answer for. Same category: `model/train_quick.py` (legacy
400-image demo trainer) and `model/checkpoints/_deadline_watch.sh`.

### 🟡 R1-9 — 271 MB `train_full_resume_state.pth` on disk

Correctly gitignored, but it is mid-run state with no value now that training
is finished. Safe to delete; it dwarfs the 94 MB checkpoint.

### ⚪ Verified clean

- `.env` is **not** tracked. No secret leak in git history for it.
- `.gitignore` correctly excludes `venv/`, `backend/media/`, `node_modules/`,
  `dist/`, backup and resume checkpoints — while *intentionally* tracking
  `resnet50_oct.pth`, with a comment explaining why.
- `data/` — 400 images / 27 MB, tracked deliberately and attributed under
  CC BY 4.0 in the README. Reasonable.
- `.dockerignore` excludes `venv/`, `data/`, `.git/`, `__pycache__`, and
  `*.pth`; the checkpoint reaches the container via the `./model` bind mount
  instead, so image size stays small and retraining needs no rebuild. Good.
- `docker-compose.yml` — named volumes for Postgres data, the Torch cache and
  the HuggingFace cache; `pg_isready` healthcheck with `depends_on:
  condition: service_healthy`. Correct.
- `backend/Dockerfile` — slim base, `libgl1`/`libglib2.0-0` for OpenCV,
  migrations run on start. Correct.
- `frontend/Dockerfile` — multi-stage build → nginx. Correct.
- **Zero** `console.log` / `debugger` in `frontend/src`, zero stray `print()`
  in the backend request path, zero `TODO`/`FIXME`/`HACK` markers in source.
- `frontend/public/icons.svg` was deleted and has **no remaining references**.

### R1 verdict

No blocker for the *software*. One blocker for the *defense*: the README.
Nothing found that exposes a real secret or breaks the running system.

### R1 remediation — all findings resolved

| # | Finding | Resolution |
|---|---|---|
| 🔴 R1-1 | README described a Streamlit demo | **`README.md` rewritten from scratch** — Docker quick start, results with the leakage explanation, config table, role matrix, architecture diagram, full API table, non-Docker instructions, training/evaluation, dataset attribution, current file tree, and an explicit Limitations section |
| 🟠 R1-2 | 25 files uncommitted | **Committed by the user** (`6eff73e`). Working tree was clean before remediation began |
| 🟠 R1-3 | `JWT_SECRET_KEY` literal in compose | Now `"${JWT_SECRET_KEY:?...}"` — compose **aborts** if unset. Verified both paths (resolves with `.env`; refuses without). The previously-committed value was also **rotated**, since it is permanently in git history |
| 🟠 R1-4 | `.env.example` missing the key | Rewritten with `JWT_SECRET_KEY`, the generator one-liner, and *why* there is no default |
| 🟠 R1-5 | Floor-pinned dependencies | `torch`, `torchvision`, `transformers`, `numpy` pinned **exactly** (they decide model behaviour); everything else given `>=tested,<next-major`. Pinning policy documented in the file header |
| 🟡 R1-6 | Stale OOD section in `PROJECT_CONTEXT.md` | Old design marked **SUPERSEDED** and kept (the retirement reasoning is defensible material), followed by a "Current design (this is what runs)" section. Also fixed: the checkpoint status table (7 checkpoints wrongly marked "Not started"), the architecture tree, and the dataset-paths note |
| 🟡 R1-7 | `UI_REDESIGN_BRIEF.md` stale | Retitled **(HISTORICAL)** with a prominent banner pointing readers to `FEATURES.md` §6 and the actual components |
| 🟡 R1-8 | Retired OOD code path | `compute_ood_stats.py` and `train_quick.py` given loud **RETIRED** / **LEGACY** docstring banners explaining what they were, why they were dropped, and what to use instead. `ood_stats.pth` and `_deadline_watch.sh` deleted |
| 🟡 R1-9 | 271 MB resume state | Deleted |

### 🟠 R1-10 — Backend image was 10.7 GB (found *by* the remediation rebuild)

Not in the original R1 list — the verification rebuild exposed it, which is
the argument for actually running the build rather than reasoning about it.

`backend/Dockerfile` claimed *"CPU-only by default (matches requirements.txt's
plain torch install)"*. That comment is **false on Linux**: PyPI's `torch`
wheel for x86-64 *is* the CUDA build, so `pip install -r requirements.txt`
pulled `nvidia-cublas-cu12`, `nvidia-cudnn-cu12`, `nvidia-cusparse-cu12`,
`triton` and a dozen more — roughly 2.5 GB of GPU libraries into a container
that has no GPU access and never will. Measured image: **10.7 GB**.

Fixed by installing `torch==2.6.0 torchvision==0.21.0` from
`https://download.pytorch.org/whl/cpu` *before* `requirements.txt`; the second
pip run finds them already satisfied at the pinned versions and leaves them
alone. The version-coupling between the two files is called out in a comment
in both.

### 🔴 R1-11 — OOD gate accepted a chart as an OCT scan (found by end-to-end verification)

Belongs to R2/R5 by topic, but it was found here, while confirming the
rebuilt image still worked, so it is recorded here. **Fixed and validated.**

A grayscale confusion-matrix plot was pushed through `/api/predict` and came
back **HTTP 200, DRUSEN→DME at 77% confidence**, with a Grad-CAM overlay and
a clinical explanation. The gate accepted it at `p(OCT) = 0.848`.

**Root cause — structural, not a bad threshold.** `clip_is_oct` is an argmax
over a fixed prompt set, so the gate can only reject what some prompt
actually *describes*. The set covered people, objects, animals, natural
photographs, X-ray/CT, abstract art and gradients — **nothing described a
chart, plot or screenshot**, so the OCT prompt won by default. This is the
same failure mode the "abstract art or wallpaper" prompt had already been
added for; the lesson is that the negative set needs to span realistic
mis-uploads, and a figure pasted from a paper is a very realistic mis-upload.

Probing narrowed it precisely — a rendered text document (`p=0.013`) and a UI
screenshot (`p=0.035`) were **already** rejected. Only chart/plot imagery got
through.

**Fix:** two negative prompts added to `model/clip_ood.py` —
`"a chart, graph, plot, heatmap, or data visualization figure"` and
`"a screenshot of a computer screen, a document, or printed text"`.

**Validation (the important half — a stricter gate that rejects real scans is
the exact bug this gate already had once):**

| Probe | Before | After |
|---|---|---|
| grayscale chart | ACCEPT `p=0.848` | **reject** `p=0.016` |
| text document | reject `p=0.013` | reject `p=0.003` |
| UI screenshot | reject `p=0.035` | reject `p=0.014` |

| Real OCT, held against regression | Accepted |
|---|---|
| Kermany | 100 / 100 |
| Noor Eye Hospital | 41 / 41 |
| OCTDL | 30 / 30 |
| **Total** | **171 / 171** |

Confirmed through the live API after restart: the chart now returns **422**
with no diagnosis, and all four bundled OCT samples still classify correctly
(CNV 1.000, DME 0.987, DRUSEN 0.995, NORMAL 0.999).

**Verification performed:** all model modules still import and
`load_ood_stats()` degrades to `None` as designed; `docker compose config`
resolves with `.env` and aborts with a clear message without it; the backend
image rebuilds cleanly against the newly pinned `requirements.txt`.

**Bug found and fixed during remediation:** the first version of the compose
change put the `:?` error message inline unquoted, and the message contained
`run: `. YAML reads `": "` inside a bare scalar as a nested mapping key, so
`docker compose config` failed with *"mapping values are not allowed in this
context"* at L30.C96 — before any container started. Fixed by quoting the
scalar; the reason is now a comment in `docker-compose.yml` so it does not
recur.
