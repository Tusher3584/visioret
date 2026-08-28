# Visioret — Project Mastery Document

> **Private study document.** Not a README, not documentation for users, not
> something to submit. This exists so that months from now, with no help
> available, you can open this repository and understand, explain, modify,
> debug, demonstrate and defend every part of it.

---

## 0. How to Use This Document

**Read it with the repository open.** Every claim points at a real file. When
a section names `backend/main.py` (`predict_endpoint`), open that line — the document is a map,
not a replacement for the territory.

### Evidence labels

Everything here is tagged so you know how far you can push a claim under
questioning:

| Label | Meaning |
|---|---|
| **[CONFIRMED]** | Directly observable in the repository. You can point at it. |
| **[INFERRED]** | Not stated anywhere, but strongly supported by the implementation. Safe to say "the design implies…". |
| **[SPECULATIVE]** | A reasonable reading, not provable. Say "I'd guess…" and mark it as a guess. |
| **[NOT DETERMINABLE]** | The repository does not answer this. Say so rather than inventing. |

**Why this matters:** the fastest way to lose credibility in a viva is to
assert a motive the code doesn't support and then be asked "where does it say
that?". This document deliberately refuses to guess on your behalf.

### Suggested reading order

If you are starting cold, jump to **§35 How to Study This Project** — it is a
sequenced curriculum. Otherwise use §3 (structure), §7 (code map) and §20
(experiments) as reference.

---

## 1. Executive Understanding

### 1.1 What the Project Does — [CONFIRMED]

Visioret is a web application that classifies **retinal OCT (Optical Coherence
Tomography) B-scans** into four categories and explains each prediction
visually.

The complete user-visible loop:

1. A user uploads a single OCT image (JPEG/PNG).
2. The system **checks it is actually an OCT scan**. If not, it refuses and
   returns no diagnosis.
3. A fine-tuned **ResNet-50** classifies it into `CNV`, `DME`, `DRUSEN` or
   `NORMAL`, with a probability for each.
4. **Grad-CAM** produces a heat overlay showing which image region drove the
   decision.
5. A written **interpretation** combines a per-class clinical description with
   a sentence derived from the heatmap's own geometry.
6. Everything is persisted, attributed to the exact model version that
   produced it.
7. A user with the **reviewer** role can mark the prediction correct or
   incorrect and supply the correct class.

### 1.2 The Problem It Solves — [CONFIRMED from code + docs]

Two problems, and it is worth separating them because they justify different
halves of the codebase:

**Problem 1 — classification.** Reading OCT scans requires expertise; a model
that classifies them could assist screening. This is the ResNet-50.

**Problem 2 — trust.** A four-class classifier will confidently label
*anything* as one of its four classes, including a photograph of a cat. And
even when it is right, a clinician has no reason to believe it. This is why
roughly half the system exists:

- the **OOD gate** (`model/ood_detector.py`, `model/clip_ood.py`) gives the
  system a way to say "I don't know",
- **Grad-CAM** (`model/inference.py`) shows *where* it looked,
- **explanations** (`model/explanations.py`) say *why that region matters*,
- the **review workflow** (`backend/main.py`, `ReviewPanel.tsx`) lets a
  qualified human contradict it, on the record.

**Say this in a viva:** "The classifier is the easy half. The project is
really about making a classifier's output defensible."

### 1.3 Main Features — [CONFIRMED]

| Feature | Where |
|---|---|
| 4-class OCT classification | `model/inference.py`, `model/train_full.py` |
| Out-of-distribution input rejection | `model/ood_detector.py` + `model/clip_ood.py` |
| Grad-CAM explanation | `model/inference.py:generate_gradcam` |
| Written clinical interpretation | `model/explanations.py` |
| Scan persistence + model-version attribution | `backend/db/models.py` |
| Accounts, JWT auth, 3 roles | `backend/auth.py` |
| Reviewer correction workflow | `backend/main.py` PUT feedback, `ReviewPanel.tsx` |
| Admin user management | `backend/main.py` `/api/admin/*`, `AdminPage.tsx` |
| Session-scoped anonymous history | `Scan.anon_session`, `lib/anonSession.ts` |
| In-app model metrics + confusion matrix | `/api/metrics`, `MetricsPage.tsx` |
| Light/dark themed UI | `index.css`, `ThemeContext.tsx` |
| Streamlit demo (secondary UI) | `app.py` |

### 1.4 Technology Stack — [CONFIRMED from `requirements.txt`, `frontend/package.json`]

| Layer | Technology | Pinned version |
|---|---|---|
| Model | PyTorch | `torch==2.6.0` (exact) |
| | torchvision | `0.21.0` (exact) |
| Input validation | CLIP via `transformers` | `5.15.1` (exact) |
| Numerics | NumPy | `2.5.1` (exact) |
| Image ops | Pillow, opencv-python-headless | ranged |
| Metrics | scikit-learn, matplotlib | ranged |
| API | FastAPI + Uvicorn | ranged |
| ORM / migrations | SQLAlchemy 2.x, Alembic | ranged |
| Database | PostgreSQL 16 | image tag |
| Auth | bcrypt, PyJWT | ranged |
| Frontend | React 19, TypeScript, Vite | |
| Styling | Tailwind CSS v4 | |
| Routing | React Router 7 | |
| Animation | Framer Motion 13 | |
| Static serving | nginx (alpine) | |
| Orchestration | Docker Compose | 3 services |

**Why four packages are pinned exactly and the rest are ranged**
— [CONFIRMED, `requirements.txt` header]: torch, torchvision, transformers and
numpy decide *model behaviour*; the published accuracy figures are the
deliverable, so the environment that produces them must be reconstructible.
Everything else affects plumbing, so patch/minor updates are welcome but a
breaking major is not.

---

## 2. Project Architecture

### 2.1 High-Level Architecture — [CONFIRMED]

```mermaid
flowchart TB
    subgraph browser["Browser"]
        SPA["React SPA<br/>(served by nginx :5173)"]
    end

    subgraph api["FastAPI :8000"]
        RT["Routes<br/>backend/main.py"]
        AUTH["Auth + roles<br/>backend/auth.py"]
        RL["Rate limiter<br/>backend/rate_limit.py"]
    end

    subgraph ml["Model layer (in-process)"]
        GATE["OOD gate<br/>grayscale -> CLIP"]
        CNN["ResNet-50<br/>classifier"]
        CAM["Grad-CAM<br/>+ explanation"]
    end

    DB[("PostgreSQL 16<br/>:5433")]
    FS["Disk<br/>backend/media/scans/"]

    SPA -->|"fetch + Bearer JWT"| RT
    RT --> AUTH
    RT --> RL
    RT --> GATE
    GATE -->|"accepted"| CNN
    CNN --> CAM
    RT --> DB
    RT --> FS
    SPA -->|"img src"| FS
```

**The single most important structural fact:** the model runs **in the same
process as the API**. There is no separate inference service, no queue, no
gRPC. `backend/main.py` imports directly from `model/`.

- **[CONFIRMED]** `backend/main.py` (the `from model...` imports at the top) imports `generate_gradcam`,
  `load_model`, `overlay_gradcam`, `predict`, `preprocess_image`,
  `load_clip`, `build_explanation`, `check_is_oct`.
- **[INFERRED]** This is a deliberate simplicity choice for a single-instance
  research tool. A separate model service would add deployment complexity with
  no benefit at this scale.
- **Consequence you must be able to state:** inference blocks the request. One
  Uvicorn worker means concurrent predictions serialise.

### 2.2 Runtime Architecture — [CONFIRMED, `docker-compose.yml`]

Three containers:

| Service | Image | Host port | Role |
|---|---|---|---|
| `db` | `postgres:16` | 5433 → 5432 | Database |
| `backend` | built from `backend/Dockerfile` | 8000 | API + model |
| `frontend` | built from `frontend/Dockerfile` | 5173 → 80 | nginx serving built SPA |

Three named volumes:

| Volume | Mounted at | Purpose |
|---|---|---|
| `visioret_pgdata` | `/var/lib/postgresql/data` | Database persistence |
| `visioret_torch_cache` | `/root/.cache/torch` | ImageNet ResNet-50 weights |
| `visioret_hf_cache` | `/root/.cache/huggingface` | CLIP weights |

Two bind mounts on `backend`:

- `./model:/app/model` — **the model directory is mounted, not baked in.**
  This means retraining a checkpoint does **not** require an image rebuild.
- `./backend/media:/app/backend/media` — uploaded scans persist on the host.

> **Practical fact that will cost you an hour if you forget it:**
> `backend/` source code is **COPYied into the image** (`backend/Dockerfile`:
> `COPY backend/ ./backend/`), while `model/` is **bind-mounted**. So editing
> anything under `backend/` requires `docker compose build backend`; editing
> `model/` only needs a restart. [CONFIRMED — discovered the hard way, recorded
> in `REVIEW_CHECKPOINTS.md` R2.]

**Port 5433 [CONFIRMED, comment in `docker-compose.yml`]:** "5432 was already
taken by a pre-existing local Postgres service." Nothing inside the containers
depends on the host port.

### 2.3 Component Relationships — [CONFIRMED]

```mermaid
flowchart LR
    main["backend/main.py"] --> auth["backend/auth.py"]
    main --> schemas["backend/schemas.py"]
    main --> storage["backend/storage.py"]
    main --> ratelimit["backend/rate_limit.py"]
    main --> models["backend/db/models.py"]
    main --> session["backend/db/session.py"]
    main --> mv["backend/db/model_version.py"]
    main --> seed["backend/db/seed_metrics.py"]
    main --> inf["model/inference.py"]
    main --> ood["model/ood_detector.py"]
    ood --> clip["model/clip_ood.py"]
    main --> expl["model/explanations.py"]

    evaluate["model/evaluate.py"] --> ds["model/dataset.py"]
    evaluate --> inf
    evaluate --> we["backend/db/write_evaluation.py"]
    we --> mv
    train["model/train_full.py"] --> ds
    train --> inf
    audit["model/audit_patient_leakage.py"] --> ds
    audit --> inf
```

**Note the direction of that dependency:** `model/evaluate.py` imports from
`backend/db/`, not the other way round. The evaluation scripts write their
results into the application database. **[INFERRED]** This is why
`write_evaluation.py` is written to *never raise* — the scripts must still work
when Postgres isn't running.

### 2.4 Request Lifecycle — [CONFIRMED]

For any request:

```
Browser fetch()
  → nginx (only for static assets; API calls go direct to :8000)
  → Uvicorn
  → FastAPI routing (path match)
  → Dependency resolution, in declaration order:
      get_db()                    yields a SQLAlchemy Session
      get_current_user_optional() decodes the Bearer token -> User | None
      anon_session_id()           reads X-Anon-Session header
      require_reviewer/admin      raises 403 if role insufficient
  → Pydantic validates the request body against the schema
  → Handler function body
  → Pydantic validates/serialises the response against response_model
  → JSON back to the browser
```

**There is no custom middleware except CORS** [CONFIRMED,
`backend/main.py` (`add_middleware(CORSMiddleware, ...)`)]. Everything else is done through FastAPI's
**dependency injection**, not middleware.

**Why that distinction matters in a viva:** middleware runs for *every*
request; dependencies run only for the routes that declare them. Auth as a
dependency means each endpoint states its own requirement in its signature —
`_reviewer: User = Depends(require_reviewer)` — which is self-documenting and
impossible to forget silently.

---

## 3. Repository / File Structure

### 3.1 Full tree (source only; `data/` = 400 tracked images, elided)

```text
visioret/
├── app.py                       # Streamlit demo UI (secondary, standalone)
├── docker-compose.yml           # 3 services, 3 volumes
├── requirements.txt             # Python deps, pinning policy in header
├── .env.example                 # template; real .env is gitignored
├── .dockerignore
│
├── model/                       # ML layer — no web framework imports
│   ├── inference.py             # load_model, preprocess, predict, Grad-CAM, overlay
│   ├── dataset.py               # 4 dataset collectors + patient-grouped splitting
│   ├── train_full.py            # the real training script
│   ├── evaluate.py              # in-distribution evaluation
│   ├── evaluate_cross_dataset.py# external generalization evaluation
│   ├── audit_patient_leakage.py # quantifies the grouping caveat
│   ├── ood_detector.py          # OOD gate entry point (grayscale -> CLIP)
│   ├── clip_ood.py              # CLIP zero-shot OCT check
│   ├── explanations.py          # clinical text + heatmap geometry description
│   ├── oct_preprocessing.py     # RETIRED experiment (negative result)
│   ├── compute_ood_stats.py     # RETIRED calibration for the old OOD stage
│   ├── train_quick.py           # LEGACY 400-image demo trainer
│   └── checkpoints/
│       ├── resnet50_oct.pth            # 91 MB, TRACKED IN GIT
│       ├── patient_split.json          # persisted Kermany split
│       ├── external_patient_split.json # persisted external split
│       ├── evaluation_metrics.json     # committed metrics -> seeds fresh DB
│       ├── evaluation_report.txt
│       ├── cross_dataset_evaluation_report.txt
│       ├── confusion_matrix.png
│       ├── cross_dataset_confusion_matrix.png
│       └── train_full.log
│
├── backend/
│   ├── main.py                  # FastAPI app, all 12 endpoints, lifespan
│   ├── auth.py                  # bcrypt, JWT, role constants + dependencies
│   ├── schemas.py               # Pydantic request/response models
│   ├── storage.py               # scan image write/delete on disk
│   ├── rate_limit.py            # fixed-window limiter for auth endpoints
│   ├── grant_role.py            # CLI: the ONLY way to create an admin
│   ├── purge_anonymous.py       # CLI: delete anonymous scans + files
│   ├── Dockerfile               # CPU-only torch, migrations on start
│   ├── alembic.ini              # script_location = %(here)s/alembic
│   ├── alembic/
│   │   ├── env.py               # points alembic at db.models.Base + DATABASE_URL
│   │   └── versions/            # 7 migrations, linear chain
│   └── db/
│       ├── models.py            # 7 SQLAlchemy models
│       ├── session.py           # engine + SessionLocal + get_db dependency
│       ├── model_version.py     # sha256 checkpoint fingerprint -> ModelVersion
│       ├── write_evaluation.py  # eval results -> JSON export + DB (best effort)
│       └── seed_metrics.py      # loads committed metrics into an empty DB
│
├── frontend/
│   ├── index.html               # loads /theme-init.js + /src/main.tsx
│   ├── vite.config.ts           # react + tailwind plugins only
│   ├── nginx.conf               # SPA fallback, cache policy, security headers
│   ├── Dockerfile               # node build stage -> nginx stage
│   ├── public/theme-init.js     # pre-paint theme (external, for CSP)
│   └── src/
│       ├── main.tsx             # React root
│       ├── App.tsx              # providers, routes, layout, ErrorBoundary
│       ├── index.css            # Tailwind v4 @theme design tokens
│       ├── api/
│       │   ├── client.ts        # typed fetch wrapper + ApiError
│       │   └── types.ts         # mirrors backend/schemas.py
│       ├── context/
│       │   ├── AuthContext.tsx  # user, isReviewer, isAdmin, login/register/logout
│       │   └── ThemeContext.tsx # theme state <-> data-theme attribute
│       ├── lib/
│       │   ├── anonSession.ts   # sessionStorage id for anonymous scoping
│       │   ├── classColors.ts   # per-class semantic colour tokens
│       │   ├── format.ts        # percent/date/count formatting
│       │   ├── identicon.ts     # local avatar generation (FNV-1a)
│       │   └── motion.ts        # canAnimate() guard
│       ├── pages/               # 7 pages + NotFoundPage
│       └── components/
│           ├── analysis/        # the scan workspace (7 components)
│           ├── archive/         # history list + toolbar
│           ├── layout/          # Header, Footer, UserMenu, Avatar, ThemeToggle…
│           ├── metrics/         # MetricsSection, PerClassTable, ConfusionMatrix
│           ├── states/          # Loading/Error/Empty/OODRejection + ErrorBoundary
│           ├── ui/              # Button, AnimatedNumber
│           └── upload/          # UploadWorkspace
│
├── samples/                     # 4 real OCT images, one per class
├── data/                        # 400 Kermany images (100/class), TRACKED
└── docs: README.md, FEATURES.md, TODO.md, PROJECT_CONTEXT.md,
      REVIEW_CHECKPOINTS.md, DEFENSE_NOTES.md, DEPLOYMENT.md,
      UI_REDESIGN_BRIEF.md (marked HISTORICAL)
```

### 3.2 The layering rule — [CONFIRMED by import analysis]

```
model/     imports:  torch, PIL, cv2, numpy, sklearn        (NO web framework)
backend/   imports:  fastapi, sqlalchemy  AND  model/*      (may depend on model)
frontend/  imports:  nothing from either — talks over HTTP only
```

`model/` never imports FastAPI. **[CONFIRMED]** — this is why `app.py`
(Streamlit) and `model/evaluate.py` can both reuse the same inference code
without dragging in a web server.

**The one deliberate exception:** `model/evaluate.py` and
`model/evaluate_cross_dataset.py` import `backend.db.write_evaluation`. That
is an ML script reaching *up* into the backend to record its results. It is
made safe by `write_evaluation` never raising.

### 3.3 Files you should recognise as *not* live code

| File | Status | Why it's still there |
|---|---|---|
| `model/oct_preprocessing.py` | **RETIRED** | A full OCT-specific preprocessing pipeline (speckle denoise, B-scan flattening, retinal cropping) that was built, evaluated, and **did not beat the plain baseline**. Kept as evidence the idea was tested. Only `limit_worker_cv2_threads` is still imported. |
| `model/compute_ood_stats.py` | **RETIRED** | Calibration for the old feature-distance OOD stage. Nothing calls it. |
| `model/train_quick.py` | **LEGACY** | The original 400-image head-only trainer. **Running it overwrites your good checkpoint with a weaker one.** |
| `UI_REDESIGN_BRIEF.md` | **HISTORICAL** | Describes the UI *before* the redesign. |
| `frontend/package-lock.json` | generated | Do not read. Do not edit by hand. |
| `data/`, `samples/` | data | Real Kermany images, CC BY 4.0 attributed in the README. |

---

## 4. Application Entry Points

There are **five** distinct ways this code starts running. Knowing all five is
a common viva question ("how do you run it?").

### Entry point 1 — the API server [CONFIRMED]

**File:** `backend/main.py`
**Started by:** `backend/Dockerfile` CMD:

```dockerfile
CMD ["sh", "-c", "cd backend && alembic upgrade head && cd .. && uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
```

Read that carefully — it does two things in order:

1. `alembic upgrade head` — **migrations run automatically on every container
   start.** This is why a fresh database needs no manual setup.
2. `uvicorn backend.main:app` — starts the ASGI server.

**The `lifespan` function is the real entry point of the application logic**
(`backend/main.py` (`lifespan`)). It runs *once* at startup, before any request:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, checkpoint_loaded, classes, val_macro_f1 = load_model(CHECKPOINT_PATH, device)
    model_state["model"] = model
    ...
    clip_model, clip_processor = load_clip(device)
    ...
    version = get_or_create_model_version(db, CHECKPOINT_PATH, val_macro_f1)
    model_state["model_version_id"] = version.id
    seed_evaluation_metrics(db, CHECKPOINT_PATH, version.id)
    yield          # <- application serves requests here
    model_state.clear()
```

**Line-by-line, and why each line exists:**

- `torch.device("cuda" if ... else "cpu")` — picks GPU if present. In Docker
  it is always CPU (the image installs CPU-only torch by design).
- `load_model(...)` — loads the 91 MB checkpoint **once**. If this happened
  per-request, every prediction would pay ~1s of disk + deserialisation.
- `model_state` is a plain module-level `dict` (`backend/main.py` (module-level `model_state = {}`)). It is
  the application's only global mutable state. **[INFERRED]** A dict rather
  than a class because there is exactly one instance and no behaviour to
  attach.
- `load_clip(device)` — loads CLIP for the OOD gate. This is the slow part of
  a cold start (downloads ~600 MB on first run, then cached in a volume).
- `get_or_create_model_version(...)` — resolves which `ModelVersion` row these
  weights correspond to (see §8.4). Every prediction made in this process is
  attributed to that row.
- `seed_evaluation_metrics(...)` — if the database has no metrics for this
  model version, load them from the committed JSON. This is what makes the
  metrics page work on a machine that has never run `evaluate.py`.
- `yield` — everything before is startup, everything after is shutdown.

**What happens if `lifespan` throws?** The app fails to start. `backend/auth.py`
deliberately raises at *import* time if `JWT_SECRET_KEY` is unset, so a
misconfigured deployment dies loudly instead of running with a default key.

### Entry point 2 — the frontend [CONFIRMED]

**Files:** `frontend/index.html` → `frontend/src/main.tsx` → `App.tsx`

```tsx
// main.tsx
createRoot(document.getElementById('root')!).render(
  <StrictMode><App /></StrictMode>,
)
```

- `createRoot` is the React 18+ concurrent-mode root API.
- `StrictMode` deliberately double-invokes effects and state updaters **in
  development only**, to surface side-effect bugs. It has no effect in the
  production build.
- The `!` is TypeScript's non-null assertion — "trust me, `#root` exists". It
  does, because `index.html` declares `<div id="root"></div>`.

**Before React runs at all**, `index.html` loads `/theme-init.js`
synchronously. That script reads the stored theme and sets
`data-theme` on `<html>` **before first paint**, so the page never flashes the
wrong palette. It is an external file rather than inline **because the CSP
sets `script-src 'self'`, which blocks inline scripts** [CONFIRMED, comment in
`public/theme-init.js`].

### Entry points 3–5 — the scripts

| Command | File | What it does |
|---|---|---|
| `python model/train_full.py` | `train_full.py:main()` | Full training run |
| `python model/evaluate.py` | `evaluate.py:main()` | In-distribution eval → report + PNG + DB + JSON |
| `python -m model.evaluate_cross_dataset` | | External eval |
| `python -m model.audit_patient_leakage` | | Leakage quantification (read-only) |
| `python -m backend.grant_role EMAIL ROLE` | | Role assignment |
| `python -m backend.purge_anonymous` | | Delete anonymous scans |
| `streamlit run app.py` | `app.py` | Standalone Streamlit UI |

---

## 5. Core Concepts Required to Understand the Project

This section explains the theory you need. Each concept is tied to where it
actually appears in *this* repository.

### 5.1 HTTP and REST

**What it is.** HTTP is a request/response protocol. A client sends a
**method** (GET/POST/PUT/PATCH/DELETE), a **path**, **headers**, and
optionally a **body**; the server replies with a **status code**, headers, and
a body.

**REST** is a convention for designing such APIs around *resources*
(nouns) rather than actions (verbs), using the HTTP methods to express intent.

**How this project uses it** — [CONFIRMED, `backend/main.py`]:

| Method | Used for | Example here |
|---|---|---|
| `GET` | Read, no side effects | `/api/scans`, `/api/metrics` |
| `POST` | Create a new resource | `/api/predict`, `/api/auth/register` |
| `PUT` | Replace a resource wholesale (idempotent) | `/api/scans/{id}/feedback` |
| `PATCH` | Partial update | `/api/auth/me`, `/api/admin/users/{id}/role` |

**Why `PUT` for feedback and `PATCH` for profile** — [INFERRED, but strongly
supported by the implementation]: the feedback handler **deletes any existing
row and inserts a new one** (`backend/main.py` (`submit_feedback`, the delete-then-insert)), i.e. it *replaces*.
`PUT` is the correct semantic for that and it is idempotent — submitting twice
leaves the same single row. `PATCH /api/auth/me` takes optional fields and
changes only what is present, which is exactly what PATCH means.

**Status codes used here** — [CONFIRMED]:

| Code | Meaning | Where it comes from |
|---|---|---|
| 200 | Success | default |
| 400 | Bad request — you sent something invalid | duplicate email, bad corrected_class, unreadable image |
| 401 | Not authenticated — no valid token | `get_current_user` |
| 403 | Authenticated but not allowed | `require_reviewer`, `require_admin` |
| 404 | Not found *or not visible to you* | `get_scan` |
| 413 | Payload too large | upload over 12 MB |
| **422** | **Two different things — see below** | |
| 429 | Too many requests | rate limiter |
| 500 | Server error (a bug) | uncaught exception |

> **The 422 subtlety you must be ready to explain.** In this API, 422 means
> **two** things:
> 1. FastAPI's automatic *validation* failure (body doesn't match the schema).
>    Body is `{"detail": [ {loc, msg, type}, ... ]}` — an **array**.
> 2. The **OOD gate declining the image** (`backend/main.py` (`predict_endpoint`, the 422 raise)). Body is
>    `{"detail": "This doesn't look like a retinal OCT scan..."}` — a
>    **string**.
>
> The frontend must handle both shapes. `client.ts:extractErrorDetail` does
> exactly that. **[CONFIRMED — this was a real bug: before it existed, every
> validation error rendered to the user as the literal text
> `[object Object]`.]**

**The 401 vs 403 distinction** is a classic interview question:
- **401 Unauthorized** actually means *unauthenticated* — "I don't know who
  you are."
- **403 Forbidden** means *authenticated but not permitted* — "I know who you
  are, and you may not do this."

This project gets it right: an anonymous caller hitting `/api/metrics` gets
**401**; a signed-in `viewer` gets **403**.

**404 for a scan you don't own, rather than 403** — [INFERRED]: returning 403
would confirm the scan *exists*, which leaks information. Returning 404 makes
"doesn't exist" and "not yours" indistinguishable. The code achieves this by
filtering the query itself (`_visible_scans_query`) rather than fetching then
checking.

### 5.2 JSON

JavaScript Object Notation — a text format for structured data. Both sides
speak it: FastAPI serialises Pydantic models to JSON; the browser's `fetch`
parses it with `response.json()`.

**Where it matters structurally here:** two columns are stored *as JSON inside
Postgres* — `Prediction.class_probabilities` and
`EvaluationMetric.per_class_metrics` / `confusion_matrix`
(`backend/db/models.py`, type `JSON`).

**Why store JSON in a relational database?** — [INFERRED]: the shape is
variable (number of classes could change) and it is never queried *by* — only
read back whole. Normalising it into a `prediction_probabilities` table would
add a join for no benefit. **This is a legitimate trade-off to defend**, and
the counter-argument (you cannot index or query inside it) is worth
acknowledging.

### 5.3 Authentication vs Authorization

- **Authentication** = *who are you?* → `backend/auth.py:get_current_user`
- **Authorization** = *what may you do?* → `require_reviewer`, `require_admin`

Two separate steps, and this project separates them cleanly in code.

### 5.4 Password hashing and bcrypt

**The problem.** If you store passwords as text and the database leaks,
everyone's password is exposed — including on other sites where they reused it.

**Hashing** is a one-way function: easy to compute, infeasible to reverse. You
store `hash(password)`; at login you compute `hash(attempt)` and compare.

**Why bcrypt specifically, not SHA-256** — this is a *very* common interview
question:

1. **bcrypt is deliberately slow.** SHA-256 is designed to be fast, which is
   exactly wrong for passwords — an attacker can try billions per second.
   bcrypt has a *cost factor* (here 12, the library default) meaning 2¹²
   iterations, so each guess costs ~200 ms.
2. **bcrypt salts automatically.** A random salt is generated per password and
   embedded in the output, so two users with the same password get different
   hashes, and precomputed rainbow tables are useless.

**In this repo** [CONFIRMED, `backend/auth.py`]:

```python
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
```

A stored hash looks like `$2b$12$....` — 60 characters, where `$2b$` is the
algorithm identifier, `12` the cost, and the rest salt + digest.

**The 72-byte trap** [CONFIRMED]: bcrypt only processes the first 72 **bytes**.
bcrypt 5.x *raises* rather than truncating. Before this was handled, a long
passphrase caused an HTTP 500 at registration. Now:

```python
PASSWORD_MAX_BYTES = 72

def password_too_long(password: str) -> bool:
    return len(password.encode("utf-8")) > PASSWORD_MAX_BYTES
```

Note it measures **bytes, not characters** — a non-ASCII passphrase hits the
limit sooner than its length suggests.

### 5.5 JWT (JSON Web Token)

**What it is.** A signed, self-contained token: `header.payload.signature`,
each part base64url-encoded. The signature proves the payload wasn't altered.

**Crucially: it is signed, NOT encrypted.** Anyone can decode and read the
payload. You must never put secrets in it. This project puts only
`{"sub": "<user_id>", "exp": <timestamp>}` — [CONFIRMED, `auth.py` (`create_access_token`)].

**Stateless vs session-based auth** — the key trade-off:

| | Server-side sessions | JWT (used here) |
|---|---|---|
| Server stores | session id → user | nothing |
| Scales horizontally | needs shared store | trivially |
| Revocation | delete the session | **impossible before expiry** |
| Payload readable by client | no | yes |

**This project's choice and its consequence** [CONFIRMED]:
`ACCESS_TOKEN_LIFETIME = timedelta(days=7)` with the comment "a demo/research
tool, not a bank — long-lived is fine". **There is no revocation.** If a token
leaks, it is valid for up to 7 days. Be ready to say that plainly.

**But note the mitigation that *is* present** [CONFIRMED,
`auth.py` (`get_current_user_optional`)]: the token carries only the user **id**;
the role is looked up **from the database on every request**. So demoting a
user takes effect immediately even though their token is unchanged. That is a
genuinely good design point — demonstrate it live (§20, Experiment 9).

### 5.6 CORS

**What it is.** Browsers enforce the *same-origin policy*: JavaScript on
`http://localhost:5173` may not read responses from `http://localhost:8000`
(different port = different origin) unless the server explicitly permits it
via `Access-Control-Allow-Origin`.

**Why this project needs it** [CONFIRMED]: the SPA is served from `:5173` and
the API is on `:8000` — different origins.

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Verified behaviour:** an `Origin: http://evil.example.com` request receives
**no** `Access-Control-Allow-Origin` header at all, so the browser blocks it.

**Common misunderstanding to avoid in a viva:** CORS is *not* a server-side
security control. It protects the *browser user*, not the server —
`curl` ignores it entirely. Never describe CORS as protecting your API.

**Known limitation:** the origins are hardcoded. Deploying to any other URL
requires editing `backend/main.py`.

### 5.7 ORM and SQLAlchemy

**ORM = Object-Relational Mapper.** Python classes ↔ database tables, objects
↔ rows.

```python
db.query(User).filter_by(email=body.email).first()
```
becomes
```sql
SELECT * FROM users WHERE email = %s LIMIT 1
```

**Advantages:** type safety, IDE completion, database portability, and — most
importantly here — **automatic parameterisation**, which is what makes SQL
injection structurally impossible (§26).

**Disadvantages:** the ORM hides the SQL it generates, which is exactly how
**N+1 query problems** appear (§25).

This project uses **SQLAlchemy 2.0 declarative style** with typed columns:

```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
```

`Mapped[int]` gives static type checking; `mapped_column` describes the SQL.

### 5.8 Database migrations and Alembic

**The problem.** Your models change over time, but the production database has
data in it. You cannot just drop and recreate.

**A migration** is a versioned, ordered script describing a schema change,
with `upgrade()` and `downgrade()`.

**In this repo:** 7 migrations forming a **linear chain**, each naming its
parent via `down_revision` [CONFIRMED]:

```
<base> → f0a32a0b30dd  initial schema
       → f4d872cf777a  gradcam_results.explanation
       → 263d6fc8f6f4  evaluation_metrics detail columns
       → 53b8feed0825  feedback.is_correct
       → e96f48ad79fb  users.password_hash
       → b2abbe5bc236  viewer/reviewer roles
       → c6c94791979f  scans.anon_session   (head)
```

Reading this chain **is reading the project's history**: it tells you auth was
added *after* the core schema, roles after auth, and anonymous scoping last.

### 5.9 React: components, props, state, hooks

**Component** — a function returning JSX (a description of UI). React calls it
and reconciles the result against the DOM.

**Props** — inputs, passed down from the parent, **immutable** inside the
child.

**State** — data owned by a component that, when changed, triggers a
re-render.

The distinction is a guaranteed interview question. In this repo:

```tsx
// ScanAnalysis receives everything as props — it owns no data.
export function ScanAnalysis({ scanId, predictedClass, confidence, ... }: Props)

// ReviewPanel owns state — the user interacts with it.
const [feedback, setFeedback] = useState<Feedback | null>(initialFeedback);
const [mode, setMode] = useState<"idle" | "correcting">("idle");
```

**Hooks used here** [CONFIRMED]:

| Hook | Purpose | Example |
|---|---|---|
| `useState` | local state | `ReviewPanel`, `PredictPage` |
| `useEffect` | side effects after render (fetching) | `HistoryPage`, `ScanDetailPage` |
| `useMemo` | cache an expensive derivation | `HistoryPage` filtering |
| `useCallback` | stable function identity across renders | `AdminPage.load` |
| `useRef` | mutable value that doesn't trigger re-render | `ImageLightbox` focus |
| `useContext` | read from a provider | `useAuth`, `useTheme` |
| `useParams` | read route parameters | `ScanDetailPage` |
| `useNavigate` | programmatic navigation | `AdminPage` redirect |
| `useReducedMotion` | OS accessibility preference | every animated component |

**The rule of hooks:** they must be called unconditionally, in the same order,
at the top level of a component. React tracks them positionally.

### 5.10 Asynchronous JavaScript

`fetch` returns a **Promise** — a placeholder for a value that isn't available
yet. `async/await` is syntax over promises:

```ts
export async function predict(file: File): Promise<PredictionResponse> {
  const response = await fetch(`${API_BASE_URL}/api/predict`, {...});
  return handleResponse<PredictionResponse>(response);
}
```

`await` suspends *this function* until the promise settles; it does **not**
block the browser — JavaScript is single-threaded with an event loop, and
other work continues.

**In the UI this becomes three states**, and every async surface here handles
all three: loading, success, error. See `components/states/States.tsx`.

### 5.11 Docker and containers

**A container** packages an application with its dependencies into an isolated
process. Unlike a VM it shares the host kernel, so it is far lighter.

**An image** is the immutable filesystem template; a **container** is a
running instance.

**Docker Compose** declares multiple containers, their networking, volumes and
dependencies in one file.

**Why this project genuinely needs it** [INFERRED, strongly]: the stack is
Python + PyTorch + Node + nginx + Postgres. Reproducing that by hand on a
demonstration machine is exactly the kind of thing that fails during a viva.
`docker compose up -d --build` replaces all of it.

**Key Compose concepts visible here** [CONFIRMED]:

- **Service discovery by name.** The backend reaches the DB at hostname `db`,
  not an IP: `postgresql+psycopg2://visioret:visioret@db:5432/visioret`.
  Compose provides DNS on the default network.
- **Healthcheck + `depends_on: condition: service_healthy`** — the backend
  waits until `pg_isready` succeeds, not merely until the container starts.
  Without this you get a race on first boot.
- **Named volumes** persist beyond container lifetime; `docker compose down`
  keeps them, `down -v` destroys them.

### 5.12 Grad-CAM (the explainability algorithm)

**The problem.** A CNN outputs a class. It does not say *why*.

**The idea.** In a CNN, late convolutional layers retain spatial structure
while encoding high-level semantics. If we know how much each feature channel
*mattered* for a class, we can weight those channels and collapse them into a
spatial heat map.

**The algorithm, as implemented in `model/inference.py`:**

1. Forward pass, capturing the activations `A` of the target layer
   (`model.layer4`, ResNet-50's last conv block).
2. Backward pass from the score for the chosen class, capturing gradients
   `∂y_c/∂A`.
3. Channel weights `α_k` = spatial mean of the gradient for channel `k` —
   "how much does this channel influence this class?"
4. Weighted sum over channels: `cam = Σ α_k · A_k`.
5. `ReLU` — keep only positive contributions (evidence *for* the class).
6. Normalise to [0,1], resize to the image.

**Why `layer4`** [INFERRED]: it is the last convolutional stage. Earlier layers
have finer spatial resolution but less semantic meaning; after `layer4` comes
global average pooling, which destroys spatial information entirely. `layer4`
is the standard choice and the last point where both properties coexist.

**Why ReLU** — negative values indicate evidence *against* the class; including
them would blur the map.

### 5.13 CLIP and zero-shot classification

**CLIP** (Contrastive Language–Image Pre-training) was trained on ~400M
image–text pairs to place images and their descriptions near each other in a
shared embedding space.

**Zero-shot classification** exploits that: embed the image, embed several
candidate text descriptions, and pick whichever text is closest. No training
on your categories required.

**How this project uses it** [CONFIRMED, `model/clip_ood.py`]: 10 prompts, of
which index 0 is the only "accept" prompt. The image is accepted **only if the
OCT prompt wins the argmax**.

```python
OCT_PROMPT_INDEX = 0
PROMPTS = [
    "a retinal optical coherence tomography (OCT) B-scan medical image",
    "a photograph of a person",
    ... 7 more negatives ...
]
```

**The design property that matters:** there is **no tuned probability
threshold** — deliberately. The docstring explains why (§22).

---

## 6. Backend Deep Dive

### 6.1 `backend/main.py` — the application

677 lines, and structurally it is: imports → constants → `lifespan` → app +
middleware → static mount → helper functions → 12 route handlers.

**It is intentionally not split into controllers/services/repositories.**
[INFERRED] At 12 endpoints with thin logic, the indirection would cost more
than it buys. This is a defensible position — see §14 for how to argue it, and
§24 for the counter-argument.

#### Module-level constants

```python
MAX_UPLOAD_BYTES = 12 * 1024 * 1024   # 12 MB
Image.MAX_IMAGE_PIXELS = 64_000_000   # ~64 MP
MAX_SCAN_LIMIT = 200
```

**Why each number** [CONFIRMED from comments]:
- 12 MB — an OCT B-scan is a few hundred KB; 12 MB is generous for a lossless
  PNG and small enough that a burst of uploads cannot exhaust memory.
- 64 MP — the largest genuine scan across all four datasets is ~0.8 MP. This
  makes Pillow raise `DecompressionBombError` **before** allocating.
- 200 — large enough that no real history view needs paging, small enough that
  one request cannot ask for the entire table.

#### The `/api/predict` handler — the most important function in the project

```python
@app.post("/api/predict", response_model=PredictionResponse)
async def predict_endpoint(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
    session_id: str | None = Depends(anon_session_id),
):
```

**Signature analysis, argument by argument:**

- `async def` — FastAPI runs this on the event loop. Note the model inference
  inside is **synchronous and CPU-bound**, so it *blocks the loop*. [INFERRED]
  This is acceptable for a single-user demo but is a real scalability
  limitation worth naming (§25).
- `file: UploadFile = File(...)` — multipart form upload. `...` (Ellipsis) is
  Pydantic's marker for **required**.
- `Depends(get_db)` — dependency injection; FastAPI calls `get_db()`, which is
  a generator, and closes the session after the response.
- `get_current_user_optional` — returns `User | None`. **Optional** because
  anonymous prediction is a supported feature.
- `anon_session_id` — reads the `X-Anon-Session` header.

**The body, in execution order:**

```python
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=400, detail="File must be a JPEG or PNG image.")
```
Cheapest check first. Note this trusts a **client-supplied header** — it is a
convenience filter, not security. The real validation is `Image.open` below.

```python
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, ...)
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, ...)
```
**Two checks, deliberately.** `file.size` comes from the multipart headers and
a hand-rolled request can lie or omit it; the second check measures reality.
Rejecting on the declared size first avoids buffering 80 MB before saying no.

```python
    try:
        image = Image.open(io.BytesIO(contents))
        image.load()
    except UnidentifiedImageError:
        raise HTTPException(400, "Could not read file as an image.")
    except Image.DecompressionBombError:
        raise HTTPException(400, "Image dimensions are implausibly large for an OCT scan.")
    except Exception:
        raise HTTPException(400, "Could not read file as an image.")
```
`Image.open` is **lazy** — it reads the header only. `image.load()` forces the
decode, which is where a corrupt or malicious file actually fails. The three
`except` clauses exist because there are three failure families, and **every
one of them is a client error (400), not a server error (500)**.

```python
    image_tensor = preprocess_image(image)
    is_oct, reason, detail = check_is_oct(image, model_state["clip_model"], ...)
    if not is_oct:
        raise HTTPException(status_code=422, detail="This doesn't look like a retinal OCT scan, ...")
```
**The safety gate.** Note it runs *before* the classifier and returns **no
prediction at all**. This is the single most important behaviour in the
system to demonstrate.

```python
    class_name, confidence, probabilities = predict(model, image_tensor, device, class_names=classes)
    class_index = classes.index(class_name)
    heatmap = generate_gradcam(model, image_tensor, class_index, device)
    overlay = overlay_gradcam(image, heatmap)
    explanation = build_explanation(class_name, heatmap)
```
Four model operations. Note `generate_gradcam` is given `class_index` — the
heat map explains **the predicted class specifically**, not just "the model's
attention".

```python
    file_id = new_scan_id()
    original_url, overlay_url = save_scan_images(file_id, image, overlay)

    try:
        scan = Scan(file_path=original_url,
                    user_id=current_user.id if current_user else None,
                    anon_session=None if current_user else session_id)
        db.add(scan); db.flush()
        prediction = Prediction(scan_id=scan.id, model_version_id=model_state["model_version_id"], ...)
        db.add(prediction); db.flush()
        db.add(GradcamResult(prediction_id=prediction.id, ...))
        db.commit()
    except Exception:
        db.rollback()
        discard_scan_images(original_url, overlay_url)
        raise
```

**Three things to understand here:**

1. **`db.flush()` vs `db.commit()`.** `flush()` sends the INSERT to the
   database so `scan.id` is populated, but does **not** end the transaction.
   `commit()` makes it permanent. This is why `prediction.scan_id = scan.id`
   works before any commit.
2. **The ownership expression.** `anon_session=None if current_user else session_id`
   — a signed-in scan is owned by `user_id` and must **not** also be reachable
   via a session id. Two ownership mechanisms must never overlap.
3. **The try/except.** The two JPEGs are already on disk before the commit. A
   failed commit would leave files nothing references and nobody knows to
   delete, so the handler rolls back *and* deletes them.

#### `_visible_scans_query` — the privacy boundary

This 8-line function is where the entire data-access policy lives:

```python
def _visible_scans_query(db, current_user, session_id):
    query = db.query(Scan)
    if is_reviewer(current_user):
        return query                                    # everything
    if current_user is not None:
        return query.filter(Scan.user_id == current_user.id)   # own scans
    if not session_id:
        return query.filter(sa_false())                 # NOTHING
    return query.filter(Scan.user_id.is_(None), Scan.anon_session == session_id)
```

**The critical line is `sa_false()`.** If a caller sends no session header, the
query matches **nothing**. The naive alternative — filtering on
`anon_session IS NULL` — would return every legacy anonymous scan to anyone who
simply omitted the header. That is a real vulnerability avoided by one line.

**Why it returns a query rather than results:** the caller can add further
filters and the limit, and the *same* function is used by both
`list_scans` and `get_scan`. That is what makes "a scan you can't see in
history also can't be opened by guessing its URL" true by construction rather
than by remembering to check twice.

### 6.2 `backend/auth.py` — identity and permission

**Module-level fail-fast** [CONFIRMED]:

```python
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is not set. ...")
```

This runs at **import**. There is deliberately no fallback default — the
comment says why: "that would silently make every deployment share the same
signing key."

**The dependency chain:**

```
oauth2_scheme (extracts "Authorization: Bearer <token>", auto_error=False)
   ↓
get_current_user_optional  → User | None      (None if no/invalid token)
   ↓
get_current_user           → User             (401 if None)
   ↓
require_reviewer / require_admin → User       (403 if wrong role)
```

Each level adds exactly one constraint. An endpoint declares the level it
needs and gets the right status code for free.

```python
def is_reviewer(user):
    return user is not None and user.role in (ROLE_REVIEWER, ROLE_ADMIN)
```

**Admin is a superset of reviewer** — the comment justifies it: "an
administrator who could not read the metrics they administer would be a
strange kind of administrator."

```python
ROLES = (ROLE_VIEWER, ROLE_REVIEWER, ROLE_ADMIN)
ASSIGNABLE_ROLES = (ROLE_VIEWER, ROLE_REVIEWER)     # admin deliberately absent
```

**This two-tuple design is the whole privilege-escalation defence.** Admin is
a valid role but not an assignable one, so it can never be granted through the
API — only by `backend/grant_role.py` against the database.

### 6.3 `backend/rate_limit.py`

A fixed-window limiter with **no external dependency**:

```python
_buckets: dict[str, deque[float]] = defaultdict(deque)

def enforce(request, scope, max_attempts, window_seconds):
    key = _client_key(request, scope)
    now = time.monotonic()
    bucket = _buckets[key]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()
    if len(bucket) >= max_attempts:
        retry_after = int(window_seconds - (now - bucket[0])) + 1
        raise HTTPException(429, ..., headers={"Retry-After": str(retry_after)})
    bucket.append(now)
```

- **`deque`** — a double-ended queue; `popleft()` is O(1), which a list's
  `pop(0)` is not.
- **`time.monotonic()`** not `time.time()` — monotonic time never jumps
  backwards when the system clock is adjusted. Using wall-clock time would let
  an NTP correction reset someone's limit.
- **The `while` loop** evicts expired entries lazily, on access, so there is no
  background cleanup task.
- **`clear_attempts`** is called after a *successful* login, so only failures
  accumulate.

**Documented limitations** [CONFIRMED, module docstring]: state is
process-local (breaks with >1 worker), and a fixed window can allow up to 2×
the limit across a boundary.

### 6.4 `backend/db/model_version.py` — content-addressed model identity

```python
def checkpoint_fingerprint(checkpoint_path: str) -> str | None:
    digest = hashlib.sha256()
    with open(checkpoint_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]
```

**Why a hash and not the file's mtime** [CONFIRMED — this replaced an mtime
implementation that had a real failure]: mtime changes on `git clone`, so the
same weights got a different version label on every machine, and
`/api/metrics` (which filters by version) returned an empty list. A content
hash is stable across clones, copies and machines.

- `iter(lambda: f.read(1MB), b"")` — the two-argument form of `iter`: call the
  function repeatedly until it returns the sentinel `b""`. Streams the 91 MB
  file instead of loading it into memory.
- `[:16]` — 64 bits of the digest, ample for distinguishing a handful of
  checkpoints.

### 6.5 `backend/db/write_evaluation.py` and `seed_metrics.py`

These two exist as a pair, and understanding *why* is one of the better
things you can explain in a viva.

**The problem:** `/api/metrics` filters strictly by the active model version.
The rows are produced by `model/evaluate.py`, which needs the 84,000-image
dataset that is **not in the repository**. So on any machine that just clones
the project, the metrics page would be permanently empty and unfixable
locally.

**The solution, in two halves:**

1. `write_evaluation.py` writes results to **two** places: the database
   (best-effort) *and* `model/checkpoints/evaluation_metrics.json`, a 1.6 KB
   file **committed to git alongside the weights**.
2. `seed_metrics.py` runs at startup and inserts any *missing* splits from that
   JSON.

**Two safety properties in the seeder** [CONFIRMED]:

```python
if fingerprint is None or exported_fingerprint != fingerprint:
    print("Skipping metric seeding: ... describes checkpoint ... but the checkpoint on disk is ...")
    return 0
...
if dataset_split in existing_splits:
    continue        # never overwrite a real local evaluation
```

It refuses to seed metrics that describe a *different* model, and it never
overwrites a genuine local evaluation. Showing numbers from the wrong model
would be worse than showing none.

---

## 7. Code Map — "If I need to change X, where do I go?"

| Task | Files, in the order you'd touch them |
|---|---|
| **Add an API endpoint** | 1. `backend/schemas.py` (request/response models) → 2. `backend/main.py` (`@app.<method>` handler) → 3. `frontend/src/api/types.ts` → 4. `frontend/src/api/client.ts` → 5. the calling component |
| **Change who can do what** | `backend/auth.py` (`is_reviewer`, `require_*`) and the `Depends(...)` in the relevant `backend/main.py` handler. UI hiding is separate: `AuthContext.tsx` `isReviewer`/`isAdmin` |
| **Add a database column** | 1. `backend/db/models.py` → 2. generate a migration → 3. `backend/schemas.py` if exposed → 4. `frontend/src/api/types.ts` |
| **Change the model / retrain** | `model/train_full.py` (hyperparameters at the top), then `model/evaluate.py` **and** `model/evaluate_cross_dataset.py` to refresh the reports and `evaluation_metrics.json` |
| **Change what the OOD gate accepts** | `model/clip_ood.py` `PROMPTS` — **then re-validate against real OCT images**, because a stricter gate that rejects genuine scans is the failure this design already had once |
| **Change the explanation text** | `model/explanations.py` `CLINICAL_EXPLANATIONS` (static per-class) or `describe_heatmap_location` (per-image) |
| **Change a page's layout** | `frontend/src/pages/<Page>.tsx`; shared result layout is `components/analysis/ScanAnalysis.tsx` |
| **Change colours / theme** | `frontend/src/index.css` — tokens under `:root` (light) and `[data-theme="dark"]`. Per-class colours: `frontend/src/lib/classColors.ts` |
| **Change validation rules** | `backend/schemas.py` (`Field(max_length=...)`) — **not** in the handlers |
| **Change error presentation** | `frontend/src/components/states/States.tsx`; error *parsing* is `client.ts:extractErrorDetail` |
| **Change upload limits** | `backend/main.py` `MAX_UPLOAD_BYTES`, `Image.MAX_IMAGE_PIXELS` |
| **Change rate limits** | `backend/rate_limit.py` constants |
| **Change Docker setup** | `docker-compose.yml` (ports/volumes/env), `backend/Dockerfile`, `frontend/Dockerfile` |
| **Change security headers / caching** | `frontend/nginx.conf` — remember `add_header` must be repeated per `location` block |
| **Add an environment variable** | `.env.example` → `docker-compose.yml` `environment:` → read it with `os.environ.get` |
| **Make someone an admin** | `python -m backend.grant_role EMAIL admin` — there is no other way |

---

## 8. Database Deep Dive

### 8.1 Technology — [CONFIRMED]

PostgreSQL 16, accessed through SQLAlchemy 2.x with the `psycopg2` driver.
Schema is managed by Alembic; nothing calls `Base.metadata.create_all()`, so
migrations are the single source of truth.

### 8.2 Entity-Relationship diagram — [CONFIRMED from `backend/db/models.py`]

```mermaid
erDiagram
    USERS ||--o{ SCANS : "uploads (nullable)"
    USERS ||--o{ FEEDBACK : "authors (nullable)"
    SCANS ||--o{ PREDICTIONS : "has"
    MODEL_VERSIONS ||--o{ PREDICTIONS : "produced"
    MODEL_VERSIONS ||--o{ EVALUATION_METRICS : "measured by"
    PREDICTIONS ||--o| GRADCAM_RESULTS : "explained by (1:1)"
    PREDICTIONS ||--o| FEEDBACK : "reviewed by (1:1)"

    USERS {
        int id PK
        string name "String(120)"
        string email UK "String(255), unique"
        string password_hash "String(255)"
        string role "String(30), default viewer"
        datetime created_at
    }
    SCANS {
        int id PK
        int user_id FK "NULLABLE - anonymous scans"
        string anon_session "String(64), indexed, NULLABLE"
        string file_path "String(500)"
        datetime uploaded_at
    }
    MODEL_VERSIONS {
        int id PK
        string version_label UK "sha256 fingerprint"
        string checkpoint_path
        datetime trained_at
        float val_macro_f1 "NULLABLE"
    }
    PREDICTIONS {
        int id PK
        int scan_id FK
        int model_version_id FK
        string predicted_class "String(30)"
        float confidence
        json class_probabilities
        datetime predicted_at
    }
    GRADCAM_RESULTS {
        int id PK
        int prediction_id FK "UNIQUE - enforces 1:1"
        string heatmap_path
        float alpha "default 0.45"
        string explanation "String(1000)"
    }
    FEEDBACK {
        int id PK
        int prediction_id FK "UNIQUE - one review per prediction"
        int reviewed_by FK "NULLABLE"
        bool is_correct
        string corrected_class "NULLABLE"
        string comment "NULLABLE String(1000)"
        datetime reviewed_at
    }
    EVALUATION_METRICS {
        int id PK
        int model_version_id FK
        string dataset_split "String(30)"
        float accuracy
        float precision_macro
        float recall_macro
        float f1_macro
        json per_class_metrics
        json confusion_matrix
        datetime evaluated_at
    }
```

### 8.3 Why each table exists — and the design questions each invites

#### `users`

`email` is `unique=True`, which creates a unique index and is what makes
`filter_by(email=...)` fast and duplicate registration impossible at the
database level (not just in application code).

`role` is `String(30)` with a Python-side default of `"viewer"`.
**[CONFIRMED gap]** the default is Python-side only — there is **no** server
default — so a raw SQL `INSERT` must supply it. This is fine because only the
ORM writes users.

> **Likely question: "Why not an enum type or a separate roles table?"**
> Honest answer: three fixed roles that are unlikely to change; a lookup table
> would add a join to every authorization check for no gain. A Postgres `ENUM`
> would be more type-safe but makes adding a role a migration. **[INFERRED]**
> `String` + a validated tuple in `auth.py` is a reasonable middle ground —
> and the validation genuinely exists (`ASSIGNABLE_ROLES`).

#### `scans` — the interesting one

Two nullable ownership columns, and the relationship between them *is* the
privacy model:

| `user_id` | `anon_session` | Meaning |
|---|---|---|
| set | `NULL` | Owned by a signed-in account |
| `NULL` | set | Anonymous, visible to that browser session only |
| `NULL` | `NULL` | **Visible to nobody** (legacy rows predating the column) |

That third row is the migration's deliberate design [CONFIRMED, migration
`c6c94791979f` docstring]: existing anonymous rows got `NULL`, "which no
session id can ever match, so the previously-pooled history becomes visible to
nobody."

`anon_session` is **indexed** — because it appears in a `WHERE` clause on
every anonymous history request.

#### `predictions` and `model_versions`

The `model_version_id` foreign key is the project's answer to a serious
question: **"which model said this?"** Retraining produces new weights → a new
fingerprint → a new `model_versions` row → new predictions point at it, while
historical predictions still point at the model that actually made them.

> **Likely question: "What happens to old predictions when you retrain?"**
> They keep their original `model_version_id`. They are never silently
> re-attributed. That is the point of the table.

#### `gradcam_results` and `feedback` — the `unique=True` trick

Both have `prediction_id` with `unique=True`. **That single flag is what makes
these one-to-one rather than one-to-many.** Combined with `uselist=False` on
the ORM relationship, `prediction.feedback` is a single object or `None`, not a
list.

This is *why* the feedback endpoint can implement "one review per prediction"
by deleting and re-inserting — the database would reject a second row anyway.

#### `feedback.is_correct`

Added later (migration `53b8feed0825`). **Why it was needed** [CONFIRMED,
model comment]: without it you cannot distinguish "a reviewer confirmed this
was right" from "nobody has looked at this". The presence of a `Feedback` row
now means *reviewed*; `is_correct` says *what the verdict was*.

### 8.4 Cascade behaviour — [CONFIRMED]

```python
class Scan(Base):
    predictions: Mapped[list["Prediction"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )

class Prediction(Base):
    gradcam_result: Mapped["GradcamResult | None"] = relationship(
        back_populates="prediction", uselist=False, cascade="all, delete-orphan")
    feedback: Mapped["Feedback | None"] = relationship(
        back_populates="prediction", uselist=False, cascade="all, delete-orphan")
```

Deleting a `Scan` deletes its `Prediction`s, and via their cascades the
`GradcamResult` and `Feedback`. **This is ORM-level cascade, not database-level
`ON DELETE CASCADE`** — it only happens when SQLAlchemy performs the delete.
A raw SQL `DELETE FROM scans` would leave orphans.

> **Historical note [CONFIRMED]:** the `Scan → Prediction` cascade was missing
> originally, which is why `backend/purge_anonymous.py` still walks and deletes
> children by hand. That workaround is now redundant but harmless — and it is a
> good example of "the workaround is the tell that the cascade was missing".

### 8.5 Tracing a database operation end-to-end

**Operation: a reviewer records a correction.**

```
HTTP  PUT /api/scans/52/feedback
      Authorization: Bearer eyJ...
      {"is_correct": false, "corrected_class": "DME", "comment": "Reads as DME."}
  │
  ├─ FastAPI matches @app.put("/api/scans/{scan_id}/feedback")
  ├─ Depends(get_db)          → opens a Session
  ├─ Depends(require_reviewer)→ get_current_user → get_current_user_optional
  │      → oauth2_scheme extracts the token
  │      → jwt.decode verifies signature + expiry → sub = "1"
  │      → SELECT * FROM users WHERE id = 1
  │      → is_reviewer(user)?  no → 403 and stop
  ├─ Pydantic validates the body against FeedbackCreate
  │      corrected_class max_length=30, comment max_length=1000
  │
  ├─ Handler body:
  │    SELECT * FROM scans WHERE id = 52          → 404 if missing
  │    validate corrected_class ∈ model_state["classes"]  → 400 if not
  │    latest = max(scan.predictions, key=predicted_at)   (in Python)
  │    SELECT * FROM feedback WHERE prediction_id = <latest.id>
  │    DELETE FROM feedback WHERE id = ...        (if one existed)
  │    db.flush()
  │    INSERT INTO feedback (prediction_id, reviewed_by, is_correct,
  │                          corrected_class, comment, reviewed_at) VALUES (...)
  │    COMMIT
  │    db.refresh(feedback)                       → re-SELECT to get defaults
  │
  ├─ _feedback_response(feedback) builds FeedbackResponse
  │      (touches feedback.reviewer → lazy SELECT on users)
  └─ 200 {"is_correct": false, "corrected_class": "DME", ...,
          "reviewer_name": "Test Researcher"}
  │
Frontend: ReviewPanel.send() awaits submitFeedback()
  → setFeedback(result)   → state change
  → setMode("idle")       → state change
  → React re-renders → the "done" branch shows
    "Marked incorrect — recorded as DME · Test Researcher · <timestamp>"
```

**Note `latest = max(scan.predictions, key=...)` happens in Python, not SQL.**
[INFERRED] Because a scan has exactly one prediction in practice, so loading
them all is trivial. If a scan could have hundreds this would be an
`ORDER BY predicted_at DESC LIMIT 1`.

---

## 9. API Deep Dive

### 9.1 Complete endpoint reference — [CONFIRMED, `backend/main.py`]

Auth column: 🔓 open · 🔑 any signed-in · 👁 reviewer · 🛡 admin

| Method | Endpoint | Auth | Input | Output | Error cases |
|---|---|---|---|---|---|
| `GET` | `/api/health` | 🔓 | — | device, checkpoint_loaded, classes, ood_gate_active | — |
| `POST` | `/api/auth/register` | 🔓 | name, email, password | token + user | 400 duplicate, 422 validation, 429 rate limit |
| `POST` | `/api/auth/login` | 🔓 | email, password | token + user | 401 bad creds, 429 rate limit |
| `GET` | `/api/auth/me` | 🔑 | — | user | 401 |
| `PATCH` | `/api/auth/me` | 🔑 | name?, current_password?, new_password? | user | 400 empty/wrong password/nothing to update, 422 |
| `POST` | `/api/predict` | 🔓 | multipart file | prediction + urls + explanation | 400 bad image, 413 too large, **422 not an OCT scan** |
| `GET` | `/api/scans` | 🔓 scoped | `?limit=1..200` | list of summaries | 422 bad limit |
| `GET` | `/api/scans/{id}` | 🔓 scoped | — | full detail | 404 not found *or not visible* |
| `PUT` | `/api/scans/{id}/feedback` | 👁 | is_correct, corrected_class?, comment? | feedback | 400, 401, 403, 404 |
| `GET` | `/api/metrics` | 👁 | — | list of evaluation metrics | 401, 403 |
| `GET` | `/api/admin/users` | 🛡 | — | list of accounts | 401, 403 |
| `PATCH` | `/api/admin/users/{id}/role` | 🛡 | role | updated account | 400 (admin/self/other-admin), 403, 404 |

### 9.2 Worked example — `POST /api/predict`

**Request:**

```http
POST /api/predict HTTP/1.1
Host: localhost:8000
X-Anon-Session: 7f3c1a2e-...
Content-Type: multipart/form-data; boundary=----X

------X
Content-Disposition: form-data; name="file"; filename="scan.jpg"
Content-Type: image/jpeg

<binary>
------X--
```

**Success (200):**

```json
{
  "scan_id": 55,
  "predicted_class": "CNV",
  "confidence": 0.9999,
  "probabilities": {"CNV": 0.9999, "DME": 0.00001, "DRUSEN": 0.00005, "NORMAL": 0.00004},
  "original_image_url": "/media/scans/2d2d0054...ary_original.jpg",
  "gradcam_overlay_url": "/media/scans/2d2d0054...ary_gradcam.jpg",
  "explanation": "CNV (choroidal neovascularization) occurs when abnormal blood vessels grow ... For this image, the model's attention was tightly concentrated in the central region of the scan."
}
```

**OOD rejection (422)** — note this is the *string* form of `detail`:

```json
{"detail": "This doesn't look like a retinal OCT scan, so no diagnosis was made. Please upload an OCT B-scan image (JPEG/PNG)."}
```

**Validation failure (422)** — the *array* form:

```json
{"detail": [{"type": "string_too_long", "loc": ["body", "name"],
             "msg": "String should have at most 120 characters", "input": "AAA..."}]}
```

**Image URLs are returned as paths, not absolute URLs.** The frontend prefixes
them with the API base via `client.ts:mediaUrl`. **[INFERRED]** This keeps the
backend ignorant of its own public hostname.

---

## 10. Authentication & Authorization

### 10.1 Registration flow — [CONFIRMED]

```
POST /api/auth/register {name, email, password}
  → enforce(request, "register", 5, 3600)        rate limit: 5/hour
  → Pydantic RegisterRequest validates:
       name      1..120 chars
       email     EmailStr  (RFC-valid, rejects reserved domains like .test)
       password  8..72 chars
  → SELECT users WHERE email = ?  → 400 if exists
  → hash_password(password)  → bcrypt, cost 12, random salt
  → INSERT INTO users (..., role DEFAULT 'viewer')
  → create_access_token(user.id)  → JWT signed HS256, exp = now + 7 days
  → 200 {access_token, token_type: "bearer", user}

Frontend: AuthContext.register()
  → setToken(result.access_token)   → localStorage["visioret_token"]
  → setUser(result.user)            → context state → whole app re-renders
```

**Registration always creates a `viewer`.** [CONFIRMED] There is no code path
in the API that creates any other role.

### 10.2 Login flow, and the timing defence

```python
user = db.query(User).filter_by(email=body.email).first()
if user is None:
    spend_password_verification_time()      # <- the interesting line
    raise HTTPException(401, "Incorrect email or password.")
if not verify_password(body.password, user.password_hash):
    raise HTTPException(401, "Incorrect email or password.")
```

**Both branches return the identical message** — so the response body doesn't
reveal whether the email exists.

**But that isn't sufficient on its own.** If the email doesn't exist, bcrypt is
never called, so the response returns in ~1 ms instead of ~200 ms. An attacker
timing the responses can enumerate valid addresses. `spend_password_verification_time()`
burns one bcrypt verification against a dummy hash so both paths cost the same.

**Measured** [CONFIRMED]: known email 0.180 s vs unknown 0.177 s — within noise.

**This is an excellent thing to raise unprompted in an interview.** It shows
you understand that a side channel can undo a correct-looking defence.

### 10.3 Authenticated request flow

```
Browser: authHeaders() reads localStorage → {Authorization: "Bearer eyJ..."}
  → fetch
  → oauth2_scheme (auto_error=False) extracts the token, or None
  → _decode_user_id: jwt.decode(token, SECRET, algorithms=["HS256"])
        verifies signature AND expiry; returns int(payload["sub"])
        any PyJWTError / KeyError / ValueError → None
  → SELECT * FROM users WHERE id = <sub>       ← role read fresh, every request
  → require_reviewer / require_admin           ← 403 if insufficient
```

**Two consequences worth stating:**

1. **A deleted user's token stops working immediately** — the DB lookup returns
   `None` → 401.
2. **A role change takes effect on the very next request** — the role is never
   in the token.

**`algorithms=["HS256"]` is a security-critical detail.** Passing a whitelist
prevents the classic `alg: none` attack, where an attacker submits an unsigned
token claiming no algorithm. **Verified** [CONFIRMED]: an `alg=none` forgery
returns 401.

### 10.4 The anonymous session boundary

**Client** (`frontend/src/lib/anonSession.ts`):

```ts
const existing = sessionStorage.getItem("visioret_anon_session");
if (existing) return existing;
const id = crypto.randomUUID();
sessionStorage.setItem("visioret_anon_session", id);
```

**`sessionStorage`, not `localStorage` — that choice is the entire feature.**
`sessionStorage` is cleared when the browser/tab closes, so anonymous history
lasts exactly as long as the session and then becomes unreachable. It is also
per-tab, so two tabs are two sessions.

**Server** — the header is capped to the column width:

```python
def anon_session_id(x_anon_session: str | None = Header(default=None)) -> str | None:
    if not x_anon_session: return None
    value = x_anon_session.strip()
    return value[:64] or None
```

**Verified isolation** [CONFIRMED, tested]:

| Caller | Sees |
|---|---|
| session A | its own scan only |
| session B | its own scan only |
| no header | nothing |
| viewer + A's header | own scans only — the header does **not** widen access |
| reviewer | all scans (by design) |

### 10.5 Privilege escalation — all paths closed [CONFIRMED by testing]

| Attempt | Result | Enforced by |
|---|---|---|
| Register with `role: admin` in the body | ignored | `RegisterRequest` has no `role` field |
| `PATCH /api/auth/me {"role":"admin"}` | 400 | `ProfileUpdate` has no `role` field → "Nothing to update" |
| Admin grants admin to someone | 400 | `role not in ASSIGNABLE_ROLES` |
| Admin demotes another admin | 400 | `target.role == ROLE_ADMIN` check |
| Admin changes own role | 400 | `target.id == current.id` check |

**The privilege chain always terminates in someone with database access.**

---

## 11. Error Handling

### 11.1 Backend strategy — [CONFIRMED]

There is **no global exception handler**. FastAPI's default behaviour is used:
`HTTPException` → that status code; anything else → 500.

**The discipline that makes this work:** every *expected* failure is raised as
an explicit `HTTPException` with the right code. The catch-all in
`/api/predict` is the clearest example:

```python
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read file as an image.")
```

Broad `except Exception` is usually a smell. Here it is correct and the comment
says why: "Truncated files, unsupported PNG variants and broken EXIF all raise
their own types here. Every one of them is a bad upload, i.e. a 400, and
letting any escape turns a client error into a 500."

### 11.2 Deliberately non-raising modules

Two modules are written to **never** propagate an exception:

- `backend/db/write_evaluation.py` — so `model/evaluate.py` still produces its
  `.txt` and `.png` reports when Postgres isn't running.
- `backend/db/seed_metrics.py` — so a seeding failure never prevents the API
  from starting.

Both print a diagnostic to `stderr` and return a falsy value.

**This is a real design principle: fail loudly where correctness depends on
it, fail quietly where it does not.** `auth.py` refuses to even import without
a secret; `seed_metrics.py` shrugs and carries on.

### 11.3 Frontend strategy

**Three layers:**

1. **`ApiError`** (`client.ts`) — a custom `Error` subclass carrying `status`,
   so callers can branch on the code:

```ts
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}
```

That `status` field is what lets `PredictPage` distinguish a *rejection* from
a *failure*:

```ts
if (err instanceof ApiError && err.status === 422) {
  setRejection(err.message);      // amber notice — a valid system decision
} else {
  setError(...);                  // red error — something went wrong
}
```

**This distinction is a genuine design insight worth articulating:** the OOD
gate declining an image is the system working correctly. Presenting it as an
error would misrepresent it.

2. **Per-component state** — every async surface holds `loading`/`error` and
   renders `LoadingState` / `ErrorState` / `EmptyState` from `States.tsx`.

3. **`ErrorBoundary`** (`components/states/ErrorBoundary.tsx`) — catches
   *render-time* exceptions. Without it, one component throwing blanks the
   entire application, because React unmounts the whole tree.

```tsx
export class ErrorBoundary extends Component<Props, State> {
  static getDerivedStateFromError(error: Error): State { return { error }; }
  componentDidCatch(error, info) { console.error(...); }
}
```

**It must be a class component** — error boundaries are the one React feature
with no hook equivalent. It is keyed on `location.pathname` in `App.tsx` so
navigating away clears a latched error.

---

## 12. Validation

### 12.1 Where validation lives, and why there

**All length and format validation is in `backend/schemas.py`, not in the
handlers.** [CONFIRMED]

```python
NAME_MAX = 120        # mirrors users.name String(120)
EMAIL_MAX = 255       # mirrors users.email String(255)
COMMENT_MAX = 1000    # mirrors feedback.comment String(1000)
PASSWORD_MIN = 8
PASSWORD_MAX = 72     # bcrypt's hard limit
```

**Why the schema and not the handler** — three concrete reasons:

1. **It covers every endpoint at once.** The same `ProfileUpdate` bound applies
   wherever it is used.
2. **It appears in the OpenAPI docs automatically**, so `/docs` documents the
   limits without anyone writing them twice.
3. **It produces a 422 with the field name**, not a 500. Without it, an
   over-length value reaches Postgres, raises `StringDataRightTruncation`, and
   surfaces as a server error — *an input mistake reported as a server
   failure*.

**Every bound mirrors a column width.** If a column grows, the bound must grow
with it — that coupling is stated in a comment.

### 12.2 The `EmailStr` asymmetry — a deliberate, defensible choice

```python
class RegisterRequest(BaseModel):
    email: EmailStr = Field(max_length=EMAIL_MAX)      # validated

class LoginRequest(BaseModel):
    email: str = Field(max_length=EMAIL_MAX)           # NOT validated
```

**Registration validates the format; login does not.** [CONFIRMED, comment]:
validating at login would let the *validation error itself* reveal which
addresses are even possible — undoing the deliberately vague "Incorrect email
or password". Login must treat a malformed address exactly like a wrong
password.

**This is a first-class example of security reasoning overriding consistency.**

### 12.3 Business-rule validation — in the handler, correctly

Rules that need application state stay in the handler:

```python
if not body.is_correct:
    if not body.corrected_class:
        raise HTTPException(400, "corrected_class is required when is_correct is false.")
    if body.corrected_class not in model_state["classes"]:
        raise HTTPException(400, f"corrected_class must be one of {model_state['classes']}.")
```

The valid classes come from the *loaded model*, not a hardcoded list. Pydantic
cannot express that, so it belongs here.

---

## 13. Important Algorithms / Logic

### 13.1 Patient-grouped splitting — the project's central methodological claim

**The problem.** Multiple OCT images come from the same patient. A random
image-level split puts some of a patient's images in train and others in test.
The model can then recognise *the patient* rather than *the disease*, and the
test score is inflated.

**The mechanism** (`model/dataset.py`):

```python
def patient_grouped_three_way_split(samples, val_fraction=0.15, test_fraction=0.15, random_state=42):
    groups = [s[2] for s in samples]                      # patient id per sample
    test_splitter = GroupShuffleSplit(n_splits=1, test_size=test_fraction, random_state=random_state)
    remainder_idx, test_idx = next(test_splitter.split(samples, groups=groups))
    remainder = [samples[i] for i in remainder_idx]
    test_samples = [samples[i] for i in test_idx]

    remainder_val_fraction = val_fraction / (1 - test_fraction)   # 0.15/0.85 = 0.176
    ...
```

- **`GroupShuffleSplit`** guarantees no *group* spans the split.
- **The `remainder_val_fraction` arithmetic** is worth understanding: after
  removing 15% for test, taking 15% of the *remainder* would give 12.75% of
  the whole. Dividing by `(1 - test_fraction)` corrects it so val really is 15%
  of the original.
- **`random_state=42`** makes the split deterministic.
- **The split is then persisted to JSON**, so it never moves across reruns —
  determinism *and* durability.

**Why the official Kermany split is not used** [CONFIRMED]: it "leaks ~85% of
test patients into train (verified)".

### 13.2 The known limitation in that grouping — be ready for this

```python
patient_id = f"{class_name}-{match.group(2)}" if match else entry.name
```

**The class name is prefixed onto the patient id.** So Kermany patient
`1016042`, who has images under CNV, DRUSEN *and* NORMAL, becomes three
"patients".

**Measured consequences** [CONFIRMED, regenerable with
`python -m model.audit_patient_leakage`]:

| | |
|---|---|
| Numeric ids appearing under >1 class | **896 of 4,657 (19.2%)** |
| Test images from a patient seen in training | **5,375 of 13,146 (40.9%)** |

| Subset | n | Accuracy | Macro F1 | DRUSEN F1 |
|---|---|---|---|---|
| Full test set | 13,146 | 0.9517 | 0.9233 | 0.817 |
| Leaked | 5,375 | 0.9180 | 0.8878 | 0.752 |
| **Clean** | 7,771 | **0.9750** | **0.9541** | 0.882 |

**The direction is the point.** The model scores *worse* on leaked patients —
the opposite of memorisation — because those are the multi-diagnosis cases on
the CNV/DRUSEN boundary. So 95.17% is **conservative**, and 97.50% is the
genuinely patient-disjoint figure.

**Why it isn't fixed:** changing the key changes which patients land in which
split, invalidating the persisted split the deployed checkpoint was trained
against. It requires a full retrain.

**The external evaluation is unaffected** — OCTDL keys on the bare numeric id,
Duke on the per-patient volume folder, and Noor's class prefix is genuinely
correct there because its patient folders are numbered independently inside
each class.

### 13.3 Class weighting for imbalance

```python
def compute_class_weights(train_counts, class_names, device):
    total = sum(train_counts.values())
    num_classes = len(class_names)
    weights = [total / (num_classes * max(train_counts[name], 1)) for name in class_names]
    return torch.tensor(weights, dtype=torch.float32, device=device)
```

Standard inverse-frequency weighting. A class with half the average count gets
twice the weight, so the loss doesn't let the model win by ignoring rare
classes. `max(..., 1)` guards against division by zero.

Passed to `nn.CrossEntropyLoss(weight=class_weights)`.

### 13.4 Grad-CAM implementation

```python
class _GradCAMHook:
    def __init__(self, target_layer):
        self.fwd_handle = target_layer.register_forward_hook(self._save_activation)
        self.bwd_handle = target_layer.register_full_backward_hook(self._save_gradient)
```

**Hooks** let you observe a layer's inputs/outputs/gradients without modifying
the model. `register_full_backward_hook` is the modern API (the older
`register_backward_hook` had documented correctness issues).

```python
    weights = gradients.mean(dim=(1, 2))          # (C,) global-average-pooled gradients
    cam = torch.zeros(activations.shape[1:], ...)
    for i, w in enumerate(weights):
        cam += w * activations[i]
    cam = torch.relu(cam).cpu().numpy()
    if cam.max() > 0:
        cam = cam / cam.max()
    cam = cv2.resize(cam, (224, 224))
```

`hook.remove()` is called — **not removing hooks leaks memory and corrupts
later passes**, because they stay attached to the module for every subsequent
forward/backward.

### 13.5 The overlay geometry fix — a good "what went wrong" story

```python
def overlay_gradcam(original_pil_image, heatmap, alpha=0.45):
    original = original_pil_image.convert("RGB")
    original_np = np.array(original)
    height, width = original_np.shape[:2]
    heatmap_resized = cv2.resize(heatmap, (width, height), interpolation=cv2.INTER_LINEAR)
```

**It resizes the heatmap up to the original's dimensions.** The earlier version
shrank the *original* to 224×224 instead. Both "work", but only this one is
geometrically honest: OCT B-scans are not square (512×496 and 768×496 are both
common, and 1536×496 exists), so squashing a 1536×496 scan into a 224×224
overlay compresses it 3× horizontally. The overlay would then be a different
shape from the original beside it in Compare view, and a reader mapping a hot
region back onto the scan would **mislocate the finding**.

`cv2.resize` takes `(width, height)` while numpy arrays are `(rows, cols)` =
`(H, W)`. Getting that backwards is a classic bug; the code has a comment
about it.

### 13.6 The identicon — a small algorithm worth understanding

```ts
function hashString(value: string): number {
  let hash = 2166136261;                       // FNV offset basis
  for (let i = 0; i < value.length; i++) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 16777619);          // FNV prime
  }
  return hash >>> 0;                           // force unsigned 32-bit
}
```

- **FNV-1a** — small, fast, well-distributed for short strings. Not
  cryptographic, and doesn't need to be.
- **`Math.imul`** — genuine 32-bit integer multiplication. Plain `*` on large
  values loses precision because JS numbers are 64-bit floats.
- **`>>> 0`** — unsigned right shift by zero, the idiomatic way to coerce to a
  uint32.

The grid is 5×5 mirrored about the centre column, so only 15 cells are decided
by the hash.

**Why not Gravatar** [CONFIRMED, comment]: "that would send a hash of every
user's email address to a third party on each page load, which is not a
reasonable thing for a medical research tool to do just to draw an avatar."

---

## 14. Design Patterns & Principles

For each: the principle, the code that demonstrates it, and — honestly —
whether it is followed consistently.

### 14.1 Separation of concerns — **followed, with one deliberate exception**

`model/` has no web framework imports; `backend/` may import `model/`;
`frontend/` talks HTTP only. This is what lets `app.py` (Streamlit) and
`model/evaluate.py` reuse inference without a web server.

**The exception:** `model/evaluate*.py` imports `backend.db.write_evaluation`.
An ML script reaching up into the backend. **Mitigated** by that module never
raising. **[Honest assessment]** it is a pragmatic violation; a cleaner design
would have the *backend* import results the scripts wrote to disk.

### 14.2 Single Responsibility — **mostly followed**

Good examples: `storage.py` only touches files; `rate_limit.py` only limits;
`model_version.py` only resolves versions.

**Violation:** `backend/main.py` is 677 lines holding routing, business logic
and data access. **[Honest assessment]** at this size it is navigable, but it
*is* the file that would need splitting first.

### 14.3 DRY — **followed, visibly**

- `ScanAnalysis.tsx` is used verbatim by both `PredictPage` and
  `ScanDetailPage`, so "what a result looks like" has exactly one
  implementation.
- `States.tsx` gives every async surface the same loading/error/empty
  treatment.
- `_visible_scans_query` is the single definition of scan visibility.
- `lib/format.ts` means numbers and dates read identically everywhere.

**Near-violation:** the scan/review count aggregation is duplicated in
`admin_list_users` and `admin_set_role`. Small, but real (§24).

### 14.4 Fail-fast — **followed where it matters**

```python
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise RuntimeError(...)
```

Refuses to import. Mirrored in `docker-compose.yml` with
`${JWT_SECRET_KEY:?...}`, so Compose aborts too. **Two layers, both loud.**

### 14.5 Defensive programming — **followed, with judgement**

`verify_password` returns `False` rather than raising for an empty hash or an
over-long password — because callers use it to decide 401 vs 200, and letting
bcrypt's `ValueError` escape turned "wrong password" into "500".

But note it is *selective*: the code does not defensively check everything. It
defends at the boundaries (input, auth, file handling) and trusts internally.

### 14.6 Configuration over hard-coding — **partially followed**

**Follows:** `JWT_SECRET_KEY`, `DATABASE_URL`, `VITE_API_BASE_URL` are all
environment-driven.

**Violates:** ports, CORS origins, CSP origins, and database credentials are
hardcoded. **[Honest assessment]** acceptable for a local research tool,
explicitly listed as a deployment blocker.

### 14.7 Dependency injection — **followed, idiomatically**

FastAPI's `Depends` is DI. `get_db` yields a session; the framework provides
and closes it. Handlers never construct their own session, which is what makes
them testable — you can override the dependency in a test.

### 14.8 Component-based architecture (frontend) — **followed**

A clear hierarchy: pages compose feature components compose UI primitives.
Data flows down as props; events flow up as callbacks. `ScanAnalysis` owns no
state at all — it is a pure presentation component.

### 14.9 The project's own stated principle

From `FEATURES.md`, and enforced in code:

> **An animation may decorate a transition, but must never decide whether
> content exists, what it says, or whether navigation occurred.**

Implemented as `lib/motion.ts:canAnimate()`, used by every entrance animation.
**Seven separate bugs of this class were found and fixed** — a metrics readout
frozen at 0.0%, empty probability bars, a stranded theme icon, an
invisible-but-focusable menu, a stale review panel, route changes that silently
didn't render, and the route wrapper leaving pages at `opacity: 0` in a
background tab.

**This is the single best "engineering judgement" story in the project**,
because the rule was *derived from repeated failures* rather than adopted from
a style guide.

---

## 15. Dependency Analysis

### 15.1 Python — [CONFIRMED, `requirements.txt`]

| Package | Pin | Type | What it provides | Where used | Without it |
|---|---|---|---|---|---|
| `torch` | **==2.6.0** | runtime | Tensors, autograd, `nn.Module` | `model/*` | No model. Autograd is what makes Grad-CAM possible |
| `torchvision` | **==0.21.0** | runtime | `resnet50` + ImageNet weights, `transforms` | `inference.py`, `train_full.py` | Hand-implement ResNet-50, lose pretrained weights |
| `transformers` | **==5.15.1** | runtime | `CLIPModel`, `CLIPProcessor` | `clip_ood.py` | No OOD gate |
| `numpy` | **==2.5.1** | runtime | Array maths | heatmaps, `explanations.py` | Pervasive |
| `pillow` | ranged | runtime | Image open/convert/save | everywhere images appear | No image I/O |
| `opencv-python-headless` | ranged | runtime | `resize`, `applyColorMap`, `cvtColor` | `overlay_gradcam` | No JET colormap. `-headless` = no GUI deps |
| `scikit-learn` | ranged | runtime* | `GroupShuffleSplit`, `classification_report`, `f1_score` | `dataset.py`, `evaluate*.py` | Hand-implement grouped splitting and metrics |
| `matplotlib` | ranged | runtime* | Confusion-matrix PNGs | `evaluate*.py` | No saved matrix images |
| `kagglehub` | ranged | dev | Dataset download helper | not on any live path | nothing |
| `fastapi` | ranged | runtime | Routing, DI, validation, OpenAPI | `backend/main.py` | Hand-roll an ASGI app |
| `email-validator` | ranged | runtime | Backs Pydantic's `EmailStr` | `schemas.py` | `EmailStr` raises at import |
| `uvicorn[standard]` | ranged | runtime | ASGI server | Dockerfile CMD | Nothing serves the app |
| `python-multipart` | ranged | runtime | Parses `multipart/form-data` | required by `UploadFile` | File upload fails |
| `sqlalchemy` | ranged | runtime | ORM | `backend/db/*` | Raw SQL everywhere |
| `alembic` | ranged | runtime | Migrations | `backend/alembic/` | Manual schema management |
| `psycopg2-binary` | ranged | runtime | PostgreSQL driver | via `DATABASE_URL` | No DB connection |
| `python-dotenv` | ranged | runtime | Loads `.env` | `db/session.py` | Manual env export |
| `bcrypt` | ranged | runtime | Password hashing | `auth.py` | No safe password storage |
| `pyjwt` | ranged | runtime | JWT encode/decode | `auth.py` | No stateless sessions |
| `streamlit` | ranged | runtime* | Secondary UI | `app.py` | No Streamlit demo |

`runtime*` = needed by scripts, not by the API request path.

> **Critical packaging note** [CONFIRMED, `backend/Dockerfile`]: torch and
> torchvision are installed from `https://download.pytorch.org/whl/cpu`
> **before** `requirements.txt`. On Linux x86-64, PyPI's `torch` wheel is the
> **CUDA** build and drags in ~2.5 GB of `nvidia-cu12-*` libraries into a
> container with no GPU. That made the image **10.7 GB**; with the CPU index it
> is **3.06 GB**. The versions in both files must stay identical or the CUDA
> wheel comes back.

### 15.2 Frontend — [CONFIRMED, `frontend/package.json`]

| Package | Type | Provides | Where |
|---|---|---|---|
| `react`, `react-dom` | dependency | Component model, DOM renderer | everywhere |
| `react-router-dom` | dependency | Client-side routing | `App.tsx`, `Link`, `useParams` |
| `framer-motion` | dependency | Declarative animation, `useReducedMotion` | analysis + layout |
| `vite` | dev | Dev server + production bundler | `npm run dev` / `build` |
| `@vitejs/plugin-react` | dev | JSX transform, Fast Refresh | `vite.config.ts` |
| `tailwindcss`, `@tailwindcss/vite` | dev | Utility CSS, `@theme` tokens | `index.css` |
| `typescript` | dev | Static types | `tsc -b` |
| `oxlint` | dev | Linter (Rust, fast) | `npm run lint` |
| `@types/*` | dev | Type definitions | compile-time only |

**dependency vs devDependency:** dependencies ship in the browser bundle;
devDependencies exist only at build time. Vite and TypeScript *produce* the
bundle but are not *in* it.

**Notably absent:** no Redux/Zustand, no React Query/SWR, no component library.
**[INFERRED]** Context + `useState` suffices at this size. The cost is manual
loading/error state in every component, which the codebase manages by
centralising the *presentation* in `States.tsx`.

---

## 16. Configuration

### 16.1 Environment variables — [CONFIRMED]

| Variable | Required | Read by | Purpose |
|---|---|---|---|
| `JWT_SECRET_KEY` | **yes, no default** | `backend/auth.py` | Token signing |
| `DATABASE_URL` | has a default | `backend/db/session.py` | Connection string |
| `VITE_API_BASE_URL` | build-time | `frontend/src/api/client.ts` | API origin |

```python
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg2://visioret:visioret@localhost:5433/visioret"
)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
```

**`pool_pre_ping=True`** issues a cheap liveness check before handing out a
pooled connection. Without it, every pooled connection is dead after the
database restarts and requests fail until the pool turns over. Not hypothetical
— the db container has been restarted mid-session more than once.

**`VITE_API_BASE_URL` is baked in at build time:**

```ts
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";
```

Vite performs *static replacement* during the build. Retargeting the API
therefore requires **rebuilding the image**, not changing an env var. A real
deployment constraint.

### 16.2 The secret-handling posture

```yaml
JWT_SECRET_KEY: "${JWT_SECRET_KEY:?not set - copy .env.example to .env and put a generated key in it, see README}"
```

The `:?` form makes Compose **abort** with that message if unset. Note the
value is **quoted** — a bare YAML scalar cannot contain `": "`, which the
message would otherwise include. (Getting that wrong produced
`mapping values are not allowed in this context` before any container started.)

**Three layers of the same defence:** `.env` gitignored → `auth.py` raises at
import → Compose refuses to start.

---

## 17. Docker / Infrastructure

### 17.1 `backend/Dockerfile` — annotated

```dockerfile
FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
```

- **`-slim`** — Debian without build tools or docs.
- **`libgl1 libglib2.0-0`** — OpenCV's runtime shared libraries. Even the
  `-headless` build needs these; without them `import cv2` fails with
  `libGL.so.1: cannot open shared object file`.
- **`rm -rf /var/lib/apt/lists/*` in the SAME `RUN`** — apt's index is ~40 MB.
  Deleting it in a *later* layer would leave it in the earlier one and the
  image would still carry it. Docker layers are additive; you cannot remove
  bytes from a previous layer.

```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.6.0 torchvision==0.21.0 \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
```

- **`COPY requirements.txt` before `COPY backend/`** — layer-cache ordering.
  Docker caches each layer keyed on its inputs. Dependencies change rarely,
  source changes constantly, so installing deps *first* means an ordinary code
  edit reuses the cached (slow) install layer.
- **`--no-cache-dir`** — pip's download cache is dead weight in an image.

### 17.2 `frontend/Dockerfile` — multi-stage

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

**Why two stages.** The build needs Node, npm and ~300 MB of `node_modules`.
The *result* is static files needing none of it. Stage 2 starts fresh from
nginx and copies only `dist/` — final image **94 MB** instead of ~400 MB, and
it ships no build tooling for an attacker to use.

- **`npm ci`** not `npm install` — installs exactly what `package-lock.json`
  specifies and fails if they disagree. Reproducible builds.
- **`ARG` then `ENV`** — the build arg becomes an env var so Vite can read it
  during `npm run build`.

### 17.3 `frontend/nginx.conf` — three things worth knowing

**(a) SPA fallback**

```nginx
location / { try_files $uri $uri/ /index.html; }
```

React Router owns `/history`, `/scans/5`. No such file exists on disk, so nginx
serves `index.html` and lets the JS router handle it. Without this, a direct
load or refresh of any non-root URL 404s.

*This also explains why `/.env` and `/.git/config` return **200** on the
frontend — they return `index.html` via this fallback. Nothing is leaked;
those files are not in the image at all. Check the body before panicking.*

**(b) The cache policy — a real deployment bug, found and fixed**

```nginx
location /assets/ { add_header Cache-Control "public, max-age=31536000, immutable" always; }
location /        { add_header Cache-Control "no-cache" always; }
```

Vite emits content-hashed filenames (`index-CYwRzeL-.js`), so those URLs can
never change contents → cache for a year.

`index.html` is the file that *names* which hashed bundle to load. nginx sends
only `ETag`/`Last-Modified` by default, with no `Cache-Control` — browsers then
apply **heuristic caching** (roughly 10% of the document's age) and can serve
it without asking the server. Observed: the container serving a new bundle
while the browser kept running the previous one. Worse, after the next deploy
the old bundle's filename no longer exists, so a stale `index.html` produces a
**blank page** with `Failed to load module script`.

`no-cache` does **not** mean "don't store" — it means "always revalidate before
use". The ETag makes that a cheap 304.

**(c) The `add_header` inheritance trap**

> nginx's `add_header` does **not** merge across levels. If a `location` block
> contains **any** `add_header`, every one inherited from the enclosing
> `server` block is **discarded**.

Both locations here set `Cache-Control`, so a single server-level declaration
of the security headers would have applied to **neither** — they would have
silently vanished from every response the site actually serves. That is why
the five headers are repeated in both blocks.

### 17.4 Security headers — [CONFIRMED]

| Header | Value | Why |
|---|---|---|
| `X-Frame-Options` | `DENY` | The app has reviewer action controls; framing it invisibly is a clickjacking route to them |
| `X-Content-Type-Options` | `nosniff` | Stop MIME sniffing re-interpreting a response as HTML/script |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | `/media/scans/<uuid>.jpg` **is** the capability for that image — a referrer leak is a real disclosure |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Nothing uses these |
| `Content-Security-Policy` | `script-src 'self'`, `frame-ancestors 'none'`, … | Blocks injected scripts and framing |
| `server_tokens off` | | Don't advertise the nginx version |

**The CSP forced a real code change.** `script-src 'self'` blocks inline
scripts, and `index.html` had an inline theme-bootstrap script. Rather than
weaken the policy to `'unsafe-inline'`, the script moved to
`public/theme-init.js` — external, same-origin, still synchronous so the
no-flash behaviour survives. `style-src` still needs `'unsafe-inline'` because
Tailwind and Framer Motion set inline styles on elements.

---

## 18. Testing

### 18.1 The honest state — [CONFIRMED]

**There is no automated test suite.** No `pytest`, no `vitest`, no test files,
no CI configuration. `git ls-files` returns zero test files.

**Do not claim otherwise.** The truthful answer to "how did you test it?":

> "There is no unit-test suite — that's a real gap. Verification was manual and
> script-driven: the evaluation scripts are reproducible and I re-ran them to
> confirm the published numbers to six decimals, and I ran a structured
> pre-defense review that probed every endpoint, the full authorization matrix,
> injection, XSS, JWT forgery, and every user flow as each role. The findings
> are in `REVIEW_CHECKPOINTS.md`."

That is a **much** stronger answer than pretending, and it comes with evidence.

### 18.2 What verification does exist

| Mechanism | What it proves | Command |
|---|---|---|
| `model/evaluate.py` | In-distribution numbers are regenerable | `python model/evaluate.py` |
| `model/evaluate_cross_dataset.py` | External generalization is regenerable | `python -m model.evaluate_cross_dataset` |
| `model/audit_patient_leakage.py` | The leakage caveat is measured, not asserted | `python -m model.audit_patient_leakage` |
| `train_full.py --smoke-test` | Training code runs before a long job | `python model/train_full.py --smoke-test` |
| `tsc -b` | Frontend types consistent | `cd frontend && npx tsc -b` |
| `oxlint` | Frontend lint | `cd frontend && npx oxlint` |
| Alembic autogenerate diff | ORM matches live schema | Experiment 12 |

**Reproducibility result** [CONFIRMED]: both evaluation scripts reproduced their
committed numbers exactly — `0.951696 / 0.923307` and `0.881268 / 0.895484`.

### 18.3 What a test suite should cover first

1. **`_visible_scans_query`** — the privacy boundary. A regression leaks medical
   images. Highest value per line of test.
2. **`auth.py` role helpers** — pure functions, trivial, security-critical.
3. **`rate_limit.enforce`** — pure logic over a clock; inject time to test the
   window boundary.
4. **`explanations.describe_heatmap_location`** — pure function of a numpy
   array; feed synthetic heatmaps with known centroids.
5. **`identicon.buildIdenticon`** — deterministic; same seed → same grid.
6. **Endpoint integration tests** with FastAPI's `TestClient`, overriding
   `get_db` with a throwaway database.

---

## 19. Debugging Guide

### 19.1 What is actually running

```bash
docker compose ps
docker compose logs -f backend
docker compose logs --tail=50 db
```

Inside the backend container: one Uvicorn process holding ResNet-50 and CLIP in
memory, plus a SQLAlchemy connection pool.

### 19.2 If X breaks, check Y

| Problem | First things to check |
|---|---|
| **Frontend can't reach the API** | Backend up (`curl localhost:8000/api/health`)? Is the browser origin exactly `localhost:5173`? CORS allows only `:5173` — Vite starting on **5174** because 5173 was busy silently breaks everything. Check the console for a CORS message |
| **Everything 401 after a restart** | `JWT_SECRET_KEY` changed. Tokens signed with the old key no longer verify. Sign in again |
| **API won't start, mentions JWT** | `JWT_SECRET_KEY` unset; `.env` missing at the project root |
| **DB connection fails** | Is `db` healthy? Is `DATABASE_URL` pointing at host `db` (in Docker) or `localhost:5433` (outside)? |
| **Container exits 137** | SIGKILL — out of memory. Check Docker Desktop's memory allocation |
| **Container exits 255** | Usually the Docker daemon stopped, not an app fault. Did all containers die simultaneously with clean logs? |
| **API returns 500** | `docker compose logs backend` — the traceback is there. 500 always means a bug; every expected failure has a 4xx |
| **Metrics page empty for a reviewer** | Look for `Seeded N evaluation metric row(s)` at startup. `Skipping metric seeding` means the checkpoint fingerprint doesn't match `evaluation_metrics.json` — re-run `evaluate.py` |
| **A code change has no effect** | **Is it under `backend/`?** That's COPYied into the image → `docker compose build backend`. `model/` is bind-mounted → restart suffices |
| **A frontend change has no effect** | Stale `index.html` in the browser cache. Hard-reload or append `?cb=<timestamp>`. Compare the served bundle hash to the container's |
| **Build fails on `pip install`** | Usually a network timeout pulling torch. Re-run; cached layers make the retry short |
| **"Too many attempts" on login** | The rate limiter working (10 failures / 5 min). Wait, or restart the backend — state is in-process |
| **Registration rejects a valid-looking email** | `.test`, `.local`, `localhost` are RFC 2606 reserved and correctly refused by `EmailStr` |
| **Every OCT scan rejected as non-OCT** | Check `ood_gate_active` in `/api/health` |

### 19.3 Inspecting state

```bash
# Database, interactively
docker compose exec db psql -U visioret -d visioret
#   \dt          list tables
#   \d scans     describe a table
#   SELECT id, user_id, anon_session, uploaded_at FROM scans ORDER BY id DESC LIMIT 5;

# Database, through the ORM
docker compose exec backend python -c "
from backend.db.session import SessionLocal
from backend.db.models import User, Scan
db = SessionLocal()
print([(u.id, u.email, u.role) for u in db.query(User).all()])
print('scans:', db.query(Scan).count())
db.close()"

# Which migration is applied?
docker compose exec backend sh -c "cd backend && alembic current"

# Stored images
docker compose exec backend ls -la backend/media/scans | head
```

### 19.4 Frontend debugging

- **React DevTools** — inspect `AuthProvider`'s value; most auth confusion is
  visible there.
- **Network tab** — confirm `Authorization` and `X-Anon-Session` are actually
  sent. A missing header is the classic cause of "I see the wrong scans".
- **Console** — `ErrorBoundary` logs the component stack of a render crash.
- Add a `console.log` inside `handleResponse` in `client.ts` to see every API
  status in one place.

### 19.5 Where to put breakpoints

| To understand | Breakpoint |
|---|---|
| Auth | `backend/auth.py:_decode_user_id` |
| Visibility rules | `backend/main.py` (`_visible_scans_query`) |
| The OOD decision | `model/ood_detector.py:check_is_oct` |
| Classification | `model/inference.py:predict` |
| Grad-CAM | `model/inference.py:generate_gradcam`, after `score.backward()` |
| Any API error | `frontend/src/api/client.ts:handleResponse` |
| Auth state | `frontend/src/context/AuthContext.tsx` `useEffect` |

---

## 20. Independent Experiments

Objective → command → expected → what it proves → what to check if it fails.
**All safe to run.**

### Experiment 1 — Is the stack alive?

```bash
docker compose ps && curl -s http://localhost:8000/api/health
```

**Expect:** three services `Up`, and
`{"status":"ok","device":"cpu","checkpoint_loaded":true,"classes":["CNV","DME","DRUSEN","NORMAL"],"ood_gate_active":true}`

**Proves:** API up, the trained checkpoint loaded (not the random-head
fallback), CLIP loaded so the gate is armed.
**If it fails:** `docker compose logs backend`. `checkpoint_loaded:false` means
the `.pth` wasn't found — check the `./model` bind mount.

### Experiment 2 — A real prediction end to end

```bash
curl -s -X POST http://localhost:8000/api/predict -F "file=@samples/cnv_sample.jpg"
```

**Expect:** `predicted_class: "CNV"`, high confidence, two `/media/scans/...`
URLs, a paragraph of explanation.
**Proves:** the entire chain — preprocessing, OOD gate, classifier, Grad-CAM,
explanation, disk write, three database inserts.

### Experiment 3 — The safety gate refuses a non-OCT image

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/api/predict \
  -F "file=@model/checkpoints/confusion_matrix.png;type=image/png"
```

**Expect:** `422`.
**Proves:** the gate rejects a non-OCT image and returns **no diagnosis**. The
most important behaviour in the system. *(This exact image — a chart — was once
accepted at p=0.848 and classified DME at 77%; two CLIP prompts fixed it.)*

### Experiment 4 — Anonymous session isolation

```bash
A="probe-aaa"; B="probe-bbb"
curl -s -X POST localhost:8000/api/predict -H "X-Anon-Session: $A" -F "file=@samples/cnv_sample.jpg" >/dev/null
curl -s -X POST localhost:8000/api/predict -H "X-Anon-Session: $B" -F "file=@samples/dme_sample.jpg" >/dev/null
echo "A:";  curl -s "localhost:8000/api/scans" -H "X-Anon-Session: $A"
echo "B:";  curl -s "localhost:8000/api/scans" -H "X-Anon-Session: $B"
echo "none:"; curl -s "localhost:8000/api/scans"
```

**Expect:** A sees only its scan, B only its own, no-header sees `[]`.
**Proves:** the privacy boundary — including that a missing session id matches
**nothing** rather than everything.

### Experiment 5 — The authorization matrix

```bash
mk(){ docker compose exec -T backend python -c "from backend.auth import create_access_token; print(create_access_token($1), end='')" 2>/dev/null | tr -d '\r\n'; }
docker compose exec backend python -m backend.grant_role --list   # get real ids
VIEWER=$(mk 4); REVIEWER=$(mk 1); ADMIN=$(mk 2)
for name in VIEWER REVIEWER ADMIN; do
  eval T=\$$name
  printf "%-9s metrics=%s admin=%s\n" "$name" \
    "$(curl -s -o /dev/null -w '%{http_code}' localhost:8000/api/metrics -H "Authorization: Bearer $T")" \
    "$(curl -s -o /dev/null -w '%{http_code}' localhost:8000/api/admin/users -H "Authorization: Bearer $T")"
done
```

**Expect:** viewer `403/403`, reviewer `200/403`, admin `200/200`.
**Proves:** 401 vs 403 used correctly, and **a reviewer is not an admin**.

### Experiment 6 — Roles are read per request, not baked into the token

```bash
curl -s -o /dev/null -w "before: %{http_code}\n" localhost:8000/api/metrics -H "Authorization: Bearer $VIEWER"
docker compose exec backend python -m backend.grant_role viewer@example.com reviewer
curl -s -o /dev/null -w "after:  %{http_code}\n" localhost:8000/api/metrics -H "Authorization: Bearer $VIEWER"
```

**Expect:** `403` then `200` — **with the same token**.
**Proves:** the JWT carries only the user id; the role is looked up fresh each
request. The best live demonstration of the auth design. *(Demote afterwards.)*

### Experiment 7 — JWT forgery is rejected

```bash
GOOD=$(mk 1)
echo -n "tampered: "; curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/api/auth/me \
  -H "Authorization: Bearer $(echo $GOOD | sed 's/.$/X/')"
echo -n "alg=none: "; curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/api/auth/me \
  -H "Authorization: Bearer $(python -c "
import base64,json
b=lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b'=').decode()
print(b({'alg':'none','typ':'JWT'})+'.'+b({'sub':'2','exp':9999999999})+'.')")"
```

**Expect:** `401` both times.
**Proves:** the signature is verified, and `algorithms=["HS256"]` blocks the
`alg: none` attack.

### Experiment 8 — Validation returns 4xx, not 5xx

```bash
LONG=$(python -c "print('A'*200)")
echo -n "long name: "; curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8000/api/auth/register \
  -H 'Content-Type: application/json' -d "{\"name\":\"$LONG\",\"email\":\"a@b.com\",\"password\":\"password123\"}"
echo -n "bad email: "; curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8000/api/auth/register \
  -H 'Content-Type: application/json' -d '{"name":"x","email":"not-an-email","password":"password123"}'
echo -n "limit=-1:  "; curl -s -o /dev/null -w "%{http_code}\n" "localhost:8000/api/scans?limit=-1"
```

**Expect:** `422` for all three.
**Proves:** input errors are reported as input errors. *(All three returned
**500** before schema bounds were added.)*

### Experiment 9 — Rate limiting

```bash
for i in $(seq 1 13); do
  curl -s -o /dev/null -w "%{http_code} " -X POST localhost:8000/api/auth/login \
    -H 'Content-Type: application/json' -d '{"email":"test@example.com","password":"wrong"}'
done; echo
```

**Expect:** ten `401`s then `429`s.
**Proves:** the fixed-window limiter works. Restart the backend to reset —
which is itself the documented limitation.

### Experiment 10 — Grad-CAM geometry is honest

```bash
curl -s -X POST localhost:8000/api/predict -F "file=@data/CNV/CNV-1112835-143.jpeg" -o /dev/null
docker compose exec backend python -c "
import glob, os
from PIL import Image
f = sorted(glob.glob('backend/media/scans/*_original.jpg'), key=os.path.getmtime)[-1]
o, g = Image.open(f).size, Image.open(f.replace('_original','_gradcam')).size
print('original', o, 'gradcam', g, 'MATCH' if o == g else 'MISMATCH')"
```

**Expect:** both `(1536, 496)` and `MATCH`.
**Proves:** the overlay is rendered at the scan's own dimensions. That image is
3.1:1 — the old implementation produced a 224×224 overlay, compressing it 3×.

### Experiment 11 — Reproduce the published numbers

```bash
python model/evaluate.py                 # needs the Kermany dataset on disk
python -m model.evaluate_cross_dataset
python -m model.audit_patient_leakage
```

**Expect:** `0.9517 / 0.9233`, `0.88 / 0.90`, and CLEAN > FULL > LEAKED.
**Proves:** results are regenerable, not merely recorded.

### Experiment 12 — The ORM matches the live schema

```bash
docker compose exec backend python -c "
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from backend.db.models import Base
from backend.db.session import engine
c = engine.connect()
d = compare_metadata(MigrationContext.configure(c), Base.metadata)
print('NO DRIFT' if not d else d)
c.close()"
```

**Expect:** `NO DRIFT`.
**Proves:** models and migrations agree — nobody hand-edited the database.

### Experiment 13 — XSS is inert

As a reviewer, store `<img src=x onerror=alert(1)>` as a feedback comment, open
that scan, then in the browser console:

```js
document.querySelectorAll('img[src="x"]').length   // expect 0
```

**Proves:** React escapes interpolated text. The payload is stored verbatim
(correct — storage shouldn't mangle data) and rendered as literal text.

### Experiment 14 — Interrogate the OOD gate directly

```bash
docker compose exec backend python -c "
import torch
from PIL import Image
from model.clip_ood import load_clip, clip_is_oct
d = torch.device('cpu'); m, p = load_clip(d)
for f in ['samples/cnv_sample.jpg','model/checkpoints/confusion_matrix.png']:
    ok, prob = clip_is_oct(Image.open(f), m, p, d)
    print(f'{f:<45} accept={ok}  p(OCT)={prob:.4f}')"
```

**Proves:** you can query the gate's confidence directly, independent of the
API. Useful when tuning prompts.

### Experiment 15 — Watch the SQL the ORM generates

```bash
docker compose exec backend python -c "
from sqlalchemy import event
from backend.db.session import engine, SessionLocal
from backend.db.models import Scan
from sqlalchemy.orm import selectinload, joinedload
n=[0]
@event.listens_for(engine, 'before_cursor_execute')
def _c(*a, **k): n[0]+=1
db=SessionLocal()
scans=(db.query(Scan).options(selectinload(Scan.predictions), joinedload(Scan.user))
       .filter(Scan.predictions.any()).limit(50).all())
for s in scans: _=s.user.name if s.user else None; _=len(s.predictions)
print(f'{len(scans)} scans rendered in {n[0]} queries')
db.close()"
```

**Expect:** **2 queries**, not ~2N+1.
**Proves:** the eager-loading fix for the N+1 problem.

---

## 21. Feature Modification Guide

### 21.1 Add an API endpoint — e.g. `GET /api/scans/{id}/history`

1. **`backend/schemas.py`** — define the response model first. It forces you to
   decide the contract before the implementation.
2. **`backend/main.py`** — add the handler:
   ```python
   @app.get("/api/scans/{scan_id}/history", response_model=list[PredictionHistoryItem])
   def scan_history(scan_id: int, db: Session = Depends(get_db),
                    current_user: User | None = Depends(get_current_user_optional),
                    session_id: str | None = Depends(anon_session_id)):
       scan = _visible_scans_query(db, current_user, session_id).filter(Scan.id == scan_id).first()
       if not scan:
           raise HTTPException(404, "Scan not found.")
       ...
   ```
   **Follow the existing pattern exactly:** always go through
   `_visible_scans_query`, never `db.query(Scan).filter_by(id=...)`, or you
   create an IDOR hole.
3. **`frontend/src/api/types.ts`** — mirror the response type.
4. **`frontend/src/api/client.ts`** — add the fetch function, using
   `scanHeaders()` (not `authHeaders()`) if visibility is identity-scoped.
5. **Component** — call it; handle loading/error/empty via `States.tsx`.

**What could break:** forgetting `scanHeaders()` means the anonymous session
header isn't sent and the caller sees nothing.

### 21.2 Add a database column — e.g. `scans.notes`

1. **`backend/db/models.py`**
   ```python
   notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
   ```
2. **Generate:**
   ```bash
   docker compose exec backend sh -c "cd backend && alembic revision --autogenerate -m 'add scans.notes'"
   ```
   **Read the generated file before applying.** Autogenerate is a draft, not an
   oracle — it misses server defaults, data migrations and constraint renames.
3. **Make it safe for existing rows.** If it must be `NOT NULL`, use the
   three-step pattern: add nullable → backfill → `alter_column`. **This project
   has a real example of getting it wrong:** migration `e96f48ad79fb`
   originally added `password_hash` as `NOT NULL` with no default, which fails
   on any populated table with `NotNullViolation`. It was later rewritten.
4. **Apply:** `docker compose exec backend sh -c "cd backend && alembic upgrade head"`
5. **Expose it:** `schemas.py` — **with a `Field(max_length=500)` matching the
   column** → `types.ts` → component.
6. **Verify no drift:** Experiment 12.

### 21.3 Add a new disease class

The change that touches the most layers — a good interview answer.

1. **Data** — the class needs labelled images in `model/dataset.py`'s collectors.
2. **Delete `patient_split.json`** so the split is recomputed. *This changes the
   held-out test set, so all previously reported numbers stop being comparable.*
3. **Retrain** — `class_names` derives from folder names, so the `fc` layer
   resizes automatically.
4. **Re-run both evaluation scripts** to regenerate the reports and
   `evaluation_metrics.json`.
5. **`model/explanations.py`** — add a `CLINICAL_EXPLANATIONS` entry, or the
   explanation is empty for that class.
6. **`frontend/src/lib/classColors.ts`** — add colour tokens and a description,
   or it falls back to grey.
7. **`frontend/src/pages/HistoryPage.tsx`** — `KNOWN_CLASSES` is a hardcoded
   array; add it there too.
8. **CLIP prompts** — probably unchanged; the gate asks "is this an OCT scan",
   not "which disease".

**If you forget 5 or 6 nothing crashes** — the class renders grey with no
explanation. A silent failure, which is exactly why it's worth knowing.

### 21.4 Change the authorization model — e.g. let viewers review their own scans

1. **`backend/main.py`** — `submit_feedback` uses `Depends(require_reviewer)`.
   Change to `Depends(get_current_user)` plus an explicit ownership check:
   ```python
   if not is_reviewer(current_user) and scan.user_id != current_user.id:
       raise HTTPException(403, ...)
   ```
2. **`ScanDetail.can_review`** must reflect the new rule, or the UI hides a
   control the server would allow.
3. **`ReviewPanel.tsx`** — the "requires the reviewer role" copy becomes wrong.

**Think hard before doing this.** The current rule exists because a correction
is a training-grade label. Weakening it weakens the argument for having roles
at all — and that argument is one of the better things to defend in a viva.

### 21.5 Add a test suite from nothing

```bash
./venv/Scripts/python.exe -m pip install pytest httpx
mkdir tests
```

```python
# tests/test_auth_roles.py — start with pure functions; no fixtures needed
from backend.auth import is_reviewer, is_admin, ROLE_VIEWER, ROLE_ADMIN

class FakeUser:
    def __init__(self, role): self.role = role

def test_admin_is_also_reviewer():
    assert is_reviewer(FakeUser(ROLE_ADMIN))

def test_viewer_is_not_reviewer():
    assert not is_reviewer(FakeUser(ROLE_VIEWER))

def test_none_user_is_nothing():
    assert not is_reviewer(None) and not is_admin(None)
```

```bash
./venv/Scripts/python.exe -m pytest tests/ -v
```

Then move up to `TestClient` integration tests, overriding `get_db`.

---

## 22. Important Design Decisions

Each: what, where, alternatives, trade-offs, and **whether the repository
records a motive**.

### D1 — The model runs inside the API process

**Where:** `backend/main.py` imports `model/` directly; `lifespan` loads once.
**Alternatives:** separate inference microservice, TorchServe, serverless.
**Gained:** no network hop, no serialisation, one deployable, trivial ops.
**Paid:** inference blocks the event loop; API and model scale together; a model
reload needs an API restart.
**Motive recorded?** **[NOT EXPLICITLY]**. **[INFERRED]** from the
single-instance framing throughout — e.g. `storage.py`: "an object store would
be overkill for a single-instance app like this."

### D2 — CLIP zero-shot for OOD instead of feature distance

**Where:** `model/clip_ood.py`; the retired code remains in `ood_detector.py`.
**Motive recorded?** **[CONFIRMED, extensively]** — the docstring states the
original was calibrated on Kermany-only images and rejected **3 of 5** genuine
Noor scans, because "is this an OCT scan?" had become "does this look like a
*Kermany* OCT scan?".
**Gained:** no per-dataset calibration; generalises to unseen scanners.
**Paid:** ~600 MB of weights; slower; can only reject what a prompt describes.
**The second failure, also recorded:** a grayscale chart accepted at p=0.848.
Two prompts added; re-validated **171/171** on real OCT across three sources.

### D3 — Argmax, not a tuned threshold

**Where:** `clip_is_oct`.
**Motive recorded?** **[CONFIRMED]**: "deliberately not a tunable probability
threshold, since threshold-tuning against any particular calibration set is
exactly the brittleness this replaces."
**Paid:** you cannot trade precision for recall.

### D4 — The trained checkpoint is committed to git

**Where:** `.gitignore` explicitly *un*-ignores it, with a comment.
**Gained:** clone-and-run; no external hosting; the demo works offline.
**Paid:** a 91 MB binary in git history forever; needs Git LFS for some hosts.
**Motive recorded?** **[CONFIRMED]** — "intentionally tracked".

### D5 — Roles are not self-assignable; admin only via the database

**Where:** `ASSIGNABLE_ROLES` in `auth.py`; `grant_role.py`.
**Motive recorded?** **[CONFIRMED]**: "A correction writes
`feedback.corrected_class`: a human label asserting the model got it wrong.
Those labels are exactly what would feed back into retraining, so they need
provenance and a qualified author."
**Paid:** you cannot bootstrap an admin through the UI — deliberately.

### D6 — `sessionStorage` for anonymous scoping

**Where:** `lib/anonSession.ts`, `Scan.anon_session`.
**Motive recorded?** **[CONFIRMED]**: cleared when the browser closes, so
anonymous history "lasts exactly as long as their session".
**Alternatives:** a cookie (automatic, but invites CSRF thought); IP address
(breaks behind NAT); `localStorage` (persists indefinitely — the wrong default
for medical images).

### D7 — Metrics committed to JSON and seeded at startup

**Where:** `write_evaluation.py` + `seed_metrics.py`.
**Motive recorded?** **[CONFIRMED]**: `/api/metrics` filters by model version,
and the rows can only be produced by a script needing an 84k-image dataset not
in the repo — so a fresh clone could never populate the page.
**Paid:** committed numbers could drift from the checkpoint. **Mitigated** by
the fingerprint check, which refuses to seed a mismatch.

### D8 — Semantic colour tokens rather than raw Tailwind colours

**Where:** `index.css` `@theme`, `lib/classColors.ts`.
**Motive recorded?** **[CONFIRMED]**: so light and dark are "two intentional
palettes rather than an inverted one", and per-class colours are "*data
indicators*, not decoration".
**Notable sub-decision:** `imaging` is dark in **both** themes, because
grayscale OCT is read on dark surfaces in radiology practice.

### D9 — No global exception handler

**Where:** its absence in `backend/main.py`.
**Gained:** each handler states its own failure modes; nothing hidden.
**Paid:** an unhandled exception in a new endpoint becomes a bare 500 with no
structured logging.
**Motive recorded?** **[NOT DETERMINABLE]** — no comment addresses it.

### D10 — Probabilities and confusion matrices as JSON columns

**Where:** `backend/db/models.py`.
**Gained:** flexible shape; no join to read.
**Paid:** cannot index or query inside; no referential integrity on class names.
**Motive recorded?** **[NOT EXPLICITLY]**. **[INFERRED]** they are always read
whole and never filtered on.

### D11 — Content-hash model versioning

**Where:** `backend/db/model_version.py`.
**Motive recorded?** **[CONFIRMED]** — the docstring records the failure that
forced it: mtime changes on `git clone`, so the same weights got a different
version label on every machine and `/api/metrics` returned an empty list.

---

## 23. Trade-offs — the honest ledger

| Decision | Gained | Paid |
|---|---|---|
| Model in-process | Simplicity, no network hop | Blocking inference, coupled scaling |
| Stateless JWT | No session store, trivial scaling | **No revocation for 7 days** |
| Content-hash versioning | Stable across machines | Hashes 91 MB at every startup |
| CLIP OOD gate | Generalises to unseen scanners | +600 MB, slower, prompt-dependent |
| Committed checkpoint | Clone-and-run | 91 MB binary in git forever |
| No service/repository layers | Less indirection, easy to follow | `main.py` at 677 lines |
| Tailwind utilities | Fast iteration, no CSS naming | Verbose JSX |
| Context, not Redux | No dependency, no boilerplate | Manual loading/error state everywhere |
| SPA + separate API | Clean separation, independent deploys | CORS config, two origins |
| `/media` unauthenticated | `<img>` tags just work | **Anyone with a link can view a scan** |
| Class-prefixed patient id | (unintended) | 40.9% of the test set shares patients with train — though *conservatively* |
| In-process rate limiter | No Redis | Resets on restart; wrong behind >1 worker |

---

## 24. Technical Debt & Weaknesses

**Being able to discuss these fluently is worth more in an interview than the
features.**

### High severity

**W1 — No automated tests.** Every refactor is unverified. The privacy boundary
in `_visible_scans_query` has no regression test despite being the most
security-critical function in the codebase. *Fix:* start with §18.3's list.

**W2 — `/media` served without authentication.** uuid4 filenames make URLs
unguessable, but possession of a link is permanent access to a medical image.
Deliberate and documented; on a public URL it is the first thing to close.
*Fix:* an authenticated proxy endpoint or short-lived signed URLs.

**W3 — The patient-grouping key includes the class name.** Undermines the
literal "patient-disjoint" claim for 40.9% of the test set. *Mitigated:* the
effect is measured and runs in the conservative direction. *Fix:* re-split and
full retrain.

### Medium

**W4 — `backend/main.py` is 677 lines** holding routing, business logic and
data access. Navigable now; first thing to split as it grows.

**W5 — No JWT revocation.** A leaked token is valid up to 7 days. *Fix:* short
access tokens + refresh tokens, or a denylist.

**W6 — Hardcoded configuration.** Ports, CORS origins, CSP origins, DB
credentials. Blocks deployment anywhere but localhost without editing source.

**W7 — Rate limiting is process-local and auth-only.** `/api/predict` — the
most expensive endpoint — is unthrottled entirely.

**W8 — `VITE_API_BASE_URL` baked in at build time.** Retargeting requires an
image rebuild.

**W9 — Single Uvicorn worker, synchronous inference.** Concurrent predictions
serialise. No queue, no batching.

### Low

**W10 — Duplicated aggregation.** The scans/reviews count query is repeated
verbatim in `admin_list_users` and `admin_set_role`.

**W11 — Retired code in the tree.** `oct_preprocessing.py`,
`compute_ood_stats.py`, `train_quick.py`. All clearly labelled — a deliberate
choice to keep evidence of experiments — but a reader must know they are inert.
**`train_quick.py` is actively dangerous: running it overwrites the good
checkpoint with a leakage-inflated weaker model.**

**W12 — `max(scan.predictions, ...)` in Python.** Fine at one prediction per
scan; would need `ORDER BY ... LIMIT 1` at scale.

**W13 — No structured logging.** `print()` to stdout; no request ids, levels or
correlation.

**W14 — `users.role` has no server-side default.** Only the ORM supplies it.

**W15 — No confidence calibration.** Softmax outputs sit near 1.0 and are
presented as "confidence" with no calibration analysis.

---

## 25. Performance

> **Only the measurements below were actually taken. Anything not listed here
> was not measured — say so rather than estimating.**

### 25.1 Measured — [CONFIRMED]

| Metric | Value |
|---|---|
| Cold start (fresh clone, empty volumes, incl. weight downloads) | **66 s** |
| Warm restart to healthy | **17 s** |
| Backend image | **3.06 GB** (was 10.7 GB with the CUDA wheel) |
| Frontend image | 94 MB |
| Backend memory, idle | **525 MB** |
| Backend memory, during inference | **686 MB peak** |
| `GET /api/scans?limit=50` | **2 queries** (was ~37) |
| Login response | ~180 ms (bcrypt cost 12, both branches) |

### 25.2 Complexity of the important paths

**Inference** — one forward pass (classification) + one forward and one
backward pass (Grad-CAM) through ResNet-50 at 224×224, plus a CLIP forward pass
for the gate. On CPU this dominates request time.

**The N+1 fix:**

```python
.options(selectinload(Scan.predictions), joinedload(Scan.user))
.filter(Scan.predictions.any())
```

- `selectinload` — one extra `WHERE scan_id IN (...)` for all predictions.
- `joinedload` — folds the owner into the main query with a `JOIN`.
- `.filter(Scan.predictions.any())` — moves "has a prediction" into SQL, so the
  `LIMIT` applies *after* the filter. Previously the filter ran in Python
  *after* the limit, so `?limit=50` could return fewer than 50 while more
  existed.

**Indexes present:** primary keys, `users.email` (unique),
`scans.anon_session` (explicit), unique constraints on
`gradcam_results.prediction_id` and `feedback.prediction_id`.

**Indexes absent that might matter:** `scans.user_id`, `scans.uploaded_at`.
Every history request filters on the first and orders by the second.
Irrelevant at current volume; not at 100k scans. **[INFERRED — not measured.]**

### 25.3 Bottlenecks

1. **CPU inference** — inherent, and blocking. The single largest cost.
2. **CLIP runs on every accepted upload**, doubling model work.
3. **`checkpoint_fingerprint` hashes 91 MB at startup** — a few hundred ms, once.
4. **`db.refresh()` after commits** — an extra SELECT per write.

### 25.4 What to measure if it became a concern

- Wrap `/api/predict` stages with `time.perf_counter()` to split gate vs
  classify vs Grad-CAM vs disk vs DB.
- `create_engine(..., echo=True)` to see every SQL statement.
- Browser DevTools Performance panel for render cost.
- `docker stats` for container memory under load.

---

## 26. Security Review

### 26.1 What is genuinely well done — [CONFIRMED by testing]

| Area | Evidence |
|---|---|
| Password storage | bcrypt cost 12, per-password salt, 60-char `$2b$12$` hashes verified in the DB |
| SQL injection | Impossible via the ORM — `' OR '1'='1`, `'; DROP TABLE scans;--` parameterised; table intact |
| XSS | React escapes by default; **no** `dangerouslySetInnerHTML`, `innerHTML`, `eval` or `new Function` anywhere in `frontend/src`. Stored payload rendered as literal text; 0 injected tags |
| JWT integrity | Tampered, `alg=none`, wrong-key, expired, nonexistent-user tokens all → 401 |
| Authorization | Full matrix verified; reviewer correctly 403 on admin endpoints |
| Privilege escalation | All five paths closed and tested |
| Path traversal | `/media/../main.py` and the percent-encoded form both 404 |
| Secret handling | `.env` gitignored; no secrets in the built frontend bundle |
| Timing attacks | Login timing equalised (0.180 s vs 0.177 s) |
| User enumeration (login) | Identical message *and* timing |

### 26.2 Weaknesses — state these plainly

| Weakness | Severity | Detail |
|---|---|---|
| `/media` unauthenticated | **High on a public URL** | uuid4 filenames only; a shared link is permanent access |
| No JWT revocation | Medium | 7-day window after a leak |
| Registration reveals existing emails | Low–Medium | "An account with this email already exists" — a deliberate UX trade-off, unlike login |
| Rate limiting only on auth | Medium | `/api/predict` unthrottled; limiter resets on restart |
| Hardcoded DB credentials | Medium in deployment | `visioret:visioret` in compose |
| No HTTPS | Medium in deployment | A reverse proxy's job; none configured |
| `/docs`, `/redoc`, `/openapi.json` public | Low | Deliberate for a research demo; every endpoint behind them is still authorization-checked |
| **No CSRF protection** | **Not applicable** | Auth is an `Authorization` header, not a cookie — browsers don't attach it automatically, so classic CSRF does not apply. **Know this reasoning; it is a common interview trap.** |

### 26.3 Threat model — what this is *not* designed to resist

**[INFERRED]** from the documented scope: a cooperative, small user base on a
trusted network. Not designed against a determined attacker; handles no PHI;
links no scan to a patient identity; makes no HIPAA/GDPR claim.

---

## 27. Deployment

### 27.1 The pipeline end to end — [CONFIRMED]

```
Source code
  ├─ frontend/Dockerfile stage 1: npm ci -> tsc -b -> vite build -> /app/dist
  ├─ frontend/Dockerfile stage 2: copy dist into nginx:alpine     -> 94 MB image
  ├─ backend/Dockerfile: apt libs -> pip (CPU torch first) -> COPY backend/ -> 3.06 GB
  └─ docker compose up -d
        db starts        -> healthcheck pg_isready
        backend waits for db healthy
        backend CMD: alembic upgrade head     <- schema created/updated
                     uvicorn backend.main:app
        lifespan: load ResNet-50 -> load CLIP -> resolve ModelVersion -> seed metrics
        frontend starts -> nginx serves /usr/share/nginx/html
  Browser -> :5173 (SPA)  and  :8000 (API)
```

### 27.2 Exact reproduction

```bash
git clone <repo> && cd visioret
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # paste into .env
docker compose up -d --build
curl http://localhost:8000/api/health
docker compose exec backend python -m backend.grant_role you@example.com admin
```

**Verified on a genuinely fresh clone:** a working system in ~66 s, all 7
migrations applied automatically, metrics seeded from the committed JSON, and
the same numbers as the source machine.

### 27.3 What is *not* production-ready — [CONFIRMED]

- CPU-only, single worker, no batching or queue — concurrent users serialise.
- Single-instance assumptions: process-local rate limiter, local-disk images.
- No HTTPS; CORS and CSP pinned to `localhost`.
- Database credentials hardcoded.
- `VITE_API_BASE_URL` fixed at build time.
- No backups, no backend healthcheck, no monitoring or log aggregation.
- Anonymous images accumulate until `purge_anonymous.py` is run by hand.
- **686 MB peak / 3 GB image exceeds common free PaaS tiers.** See
  `DEPLOYMENT.md` for the Hugging Face Spaces + Neon path.

---

## 28. Git / Development History — [CONFIRMED]

**15 commits, 2026-08-02 → 2026-08-28, single branch `main`.**

| Commit | Date | What it reveals |
|---|---|---|
| `83c1dc8` Add Visioret OCT classification demo with Grad-CAM | 08-02 | **Started as a Streamlit-only demo.** `app.py` predates the whole web stack |
| `ef12fe0` bring significant backend changes, added db and docker | 08-06 | FastAPI + Postgres + Docker arrive together |
| `3488a74` implemented frontend and connected with backend and db | 08-06 | React added the same day |
| `e29db1a` added validation for oct vs non-oct images | 08-20 | The OOD gate, v1 (feature-distance) |
| `f93dce7` added oct special pre processing pipeline | 08-21 | The experiment later **reverted** |
| `33913b4` added 3 more datasets | 08-23 | Noor + OCTDL + Duke; the generalization work |
| `2d6aa6d` enhanced the ui | 08-23 | |
| `292bcc5` metrics section | 08-23 | `/api/metrics` + metrics page |
| `16a728b` fixed the ood gate | 08-23 | **feature-distance → CLIP** |
| `e9a2d18` last overhaul on this whole project | 08-26 | |
| `6eff73e` added admin logic | 08-26 | The third role |
| `ae23ed2`, `b44bf5f`, `68be2f3` | 08-26/27 | Pre-defense review fixes |
| `c9ef8f7` project ready for deployment | 08-28 | HEAD |

**What the history proves, and it is worth saying:** the architecture was **not
designed up front**. It began as a single-file Streamlit demo and grew a
backend, a database, a frontend, a safety gate, more datasets, roles and an
admin layer — in that order. The migration chain tells the same story
independently (auth after the core schema, roles after auth, anonymous scoping
last).

**Limitation of this evidence:** commit messages are short and
non-conventional ("rafactored more"). They establish *sequence*, not *motive*.
Motive is recovered from code comments and `TODO.md`, not from git.

---

## 29. Common Failure Scenarios

| Scenario | What happens | Why | Recovery |
|---|---|---|---|
| Checkpoint file missing | API starts, `checkpoint_loaded: false`, predictions come from an **untrained random head** | `load_model` falls back to the ImageNet backbone + random `fc` | Restore the `.pth`; check the `./model` bind mount |
| CLIP fails to download | `load_clip` raises → `lifespan` fails → app won't start | No network on first run | Restore network; weights then cache in `visioret_hf_cache` |
| Database unreachable at startup | `lifespan` raises at `get_or_create_model_version` | No `db` container | `docker compose up -d db` |
| Database dies *while running* | Requests 500 until the pool turns over | Dead pooled connections | `pool_pre_ping=True` mitigates this |
| Two reviewers review the same prediction simultaneously | Last writer wins; possibly a unique-constraint error on `feedback.prediction_id` | Delete-then-insert is not atomic under concurrency | **[INFERRED]** Not handled. A real race. A transaction with `SELECT ... FOR UPDATE`, or an upsert, would fix it |
| Disk fills | `save_scan_images` raises → the `except` rolls back and deletes partial files | No quota management | Run `purge_anonymous.py` |
| `evaluation_metrics.json` describes a different checkpoint | Seeding is **skipped** with a message | Fingerprint mismatch guard | Re-run `evaluate.py` |
| Retrain without re-running evaluation | Metrics page empty for the new version | New fingerprint, no rows | Re-run both evaluation scripts |
| `train_quick.py` run by accident | **The good checkpoint is overwritten** by a weaker, leakage-inflated model | It writes to the same path | Restore from git: `git checkout model/checkpoints/resnet50_oct.pth` |

**The concurrency question is a favourite in vivas.** The honest answer:
*"Two reviewers reviewing the same prediction at the same moment is a real
race — the delete-then-insert isn't atomic. The unique constraint means the
database would reject the second insert rather than silently duplicate, so it
fails safe, but it isn't handled gracefully. A transaction with row-level
locking, or a proper upsert, would fix it."*

---

## 30. Professor / Viva Questions

### Basic

**Q: What does your project do?**
Classifies retinal OCT scans into CNV, DME, DRUSEN or NORMAL, and explains each
prediction with a Grad-CAM heatmap and a written interpretation. It refuses
images that aren't OCT scans, and lets qualified reviewers correct predictions
on the record.

**Q: Why did you build it this way — why not just a model?**
A four-class classifier will confidently label anything as one of its four
classes. The classifier is the easy half; the project is about making its
output defensible — hence the OOD gate, Grad-CAM, the written explanation, and
the review workflow with provenance.

**Q: Why these four classes?**
They are the classes in the Kermany OCT2017 dataset, the primary training
source. Two external datasets also carry an `AMD` class, which is **excluded**
because it isn't split into CNV vs DRUSEN and mapping it would require a
clinician's relabelling rather than a guess.

### Dataset and methodology

**Q: How do you know your test set isn't contaminated?**
Kermany's official split leaks ~85% of test patients into train — verified, so
it isn't used. Everything is pooled and re-split by patient with
`GroupShuffleSplit`, persisted to JSON so it never moves.
**Then volunteer the caveat:** the grouping key includes the class name, so a
patient with images under two classes counts as two patients. 40.9% of test
images come from a patient seen in training. **But the effect was measured and
runs the conservative way** — 0.9180 on leaked vs 0.9750 on clean, because
leaked patients are the multi-diagnosis, clinically ambiguous cases. So 95.17%
understates rather than overstates. `python -m model.audit_patient_leakage`
regenerates it.

**Q: Isn't 95% just memorising one dataset?**
No, and there's a number. Trained on Kermany alone: **82.0% / 0.78** on
external data with DRUSEN recall **0.48**. After training across four datasets:
**88.1% / 0.90**, DRUSEN recall **0.79**, while in-distribution barely moved
(95.42% → 95.17%). The external set is 2,712 images from three other
hospitals/scanners, and **the grouping caveat doesn't affect it**.

**Q: Why is DRUSEN your worst class?**
Precision 0.739 in-distribution. DRUSEN and CNV are adjacent stages of AMD —
drusen are sub-retinal deposits, CNV adds abnormal vessel growth and fluid.
The confusion matrix shows the errors concentrating there, and the Grad-CAM
overlays for those cases still localise to the right tissue, which says it's a
decision-boundary problem rather than the model looking in the wrong place.

### Model

**Q: Why ResNet-50, and why unfreeze only layer3, layer4 and fc?**
Transfer learning: early layers learn generic edges and textures that transfer
from ImageNet, later layers learn dataset-specific structure. Unfreezing
`layer3`/`layer4`/`fc` gives 22.1M of 23.5M parameters trainable — enough to
adapt to OCT texture without discarding useful low-level features or
overfitting.

**Q: Explain Grad-CAM.**
Forward pass capturing `layer4` activations; backward pass from the predicted
class score capturing gradients; average the gradients spatially per channel to
get importance weights; weighted-sum the activation maps; ReLU to keep only
positive evidence; normalise and resize. `layer4` because it's the last point
with both spatial structure and semantic meaning — after it comes global
average pooling, which destroys spatial information.

**Q: Why is confidence always ~100%?**
Raw softmax, which is characteristically overconfident. **No calibration
analysis was done** — that's a real gap. Temperature scaling or reliability
diagrams would be the standard next step.

**Q: What stops it diagnosing a photo of a cat?**
A two-stage gate before the classifier: a grayscale heuristic, then a CLIP
zero-shot check against 10 prompts where the OCT prompt must win the argmax.
Rejection is **422 with no diagnosis at all**.
**Then tell both failure stories** — the original feature-distance gate
rejected 3 of 5 genuine Noor scans because it was calibrated on one dataset;
and later a grayscale chart was accepted at p=0.848 because argmax over a
fixed prompt set can only reject what a prompt *describes*, and nothing
described a chart.

**Q: Is the training reproducible?**
The **split** always was — `random_state=42` plus a persisted JSON. The **run**
wasn't until recently: there was no `torch.manual_seed`, so head init, shuffle
order and augmentation varied. It's seeded now, but **the deployed checkpoint
predates that fix**, so it can't be bit-reproduced — only the methodology can.
Both evaluation scripts *do* reproduce their published numbers exactly.

### Architecture

**Q: Why separate the model, backend and frontend?**
`model/` imports no web framework, which is why the same inference code serves
the FastAPI app, the Streamlit demo and the evaluation scripts. The frontend
talks HTTP only, so it could be replaced entirely without touching Python.

**Q: Why not a service/repository layer in the backend?**
At 12 endpoints with thin logic, the indirection would cost more than it buys —
you'd be writing pass-through methods. I'd add one when a handler needs logic
reused across endpoints. **The honest counter:** `main.py` is 677 lines and is
the first file I'd split.

**Q: Why is the model in the same process as the API?**
Simplicity: no network hop, no serialisation, one deployable. **The cost is
real** — inference is synchronous and blocks the event loop, so concurrent
predictions serialise. For a single-user demo that's the right trade; for
production you'd want a queue or a separate inference service.

### Database

**Q: Why a `model_versions` table?**
So every prediction is attributable to the exact weights that produced it.
Retraining creates a new fingerprint → a new row → new predictions point at it,
while historical predictions still point at the model that actually made them.
They're never silently re-attributed.

**Q: Why is `scans.user_id` nullable?**
Anonymous use is a supported feature. A scan is owned either by `user_id` **or**
by `anon_session`, never both — that's enforced in the handler:
`anon_session=None if current_user else session_id`.

**Q: What happens if you delete a user?**
Their scans have `user_id` set. There is **no** `ON DELETE` behaviour declared
on that FK, so a raw delete would fail on the constraint. Through the ORM you'd
delete their scans first — the `Scan → Prediction` cascade then removes
predictions, Grad-CAM rows and feedback.

**Q: Why store probabilities as JSON instead of a table?**
The shape is variable and it's always read whole, never filtered on. A
`prediction_probabilities` table would add a join for no benefit. **The
trade-off I accept:** I can't index or query inside it.

**Q: Why is `anon_session` indexed but `user_id` isn't?**
`anon_session` is in a `WHERE` clause on every anonymous history request and
was added deliberately. `user_id` arguably should be indexed too — that's an
oversight rather than a decision, though it's irrelevant at current volume.

### API

**Q: Why `PUT` for feedback and `PATCH` for profile?**
The feedback handler deletes any existing row and inserts a new one — it
*replaces*, which is exactly `PUT`, and it's idempotent. `PATCH /api/auth/me`
takes optional fields and changes only what's present.

**Q: Why 404 rather than 403 for a scan you don't own?**
403 would confirm the scan exists, which leaks information. The visibility
filter is applied to the *query*, so "doesn't exist" and "not yours" are
indistinguishable by construction.

**Q: You use 422 for two different things — isn't that confusing?**
Yes, and it caused a real bug. FastAPI uses 422 for validation failures with a
`detail` **array**; the OOD gate uses 422 with a `detail` **string**. The
frontend assumed a string, so every validation error rendered as
`[object Object]`. Fixed by normalising both shapes in `extractErrorDetail`.

### Security

**Q: How are passwords protected?**
bcrypt with a per-password salt and cost factor 12 — deliberately slow, ~200 ms
per verification, so brute force is expensive. Never SHA-256, which is fast by
design and therefore wrong for passwords.

**Q: How does authentication work?**
bcrypt verify → a stateless JWT signed HS256 carrying only `{sub, exp}`, 7-day
lifetime, stored in `localStorage`. Every request decodes it, then **looks the
role up from the database** — so a demotion takes effect immediately even
though the token is unchanged.

**Q: What are the security weaknesses?**
Volunteer these: (1) `/media` is unauthenticated — uuid4 filenames only;
(2) no JWT revocation within the 7-day window; (3) registration reveals whether
an email exists, unlike login which is deliberately vague in both message and
timing; (4) rate limiting covers only auth and resets on restart;
(5) credentials and origins are hardcoded for local use.

**Q: What about CSRF?**
Not applicable here. CSRF works because browsers attach **cookies**
automatically to cross-site requests. This app authenticates with an
`Authorization` header, which a browser never adds on its own, so a malicious
site cannot forge an authenticated request. If I moved to cookie auth I'd need
`SameSite` and CSRF tokens.

**Q: How do you prevent SQL injection?**
The ORM parameterises every query — user input never becomes SQL syntax. I
tested it: `'; DROP TABLE scans;--` as a session id returns zero scans and the
table is intact.

### Testing and quality

**Q: How did you test it?**
Be honest: no unit-test suite — a real gap. Verification was reproducible
scripts plus a structured pre-defense review recorded in
`REVIEW_CHECKPOINTS.md`, which probed every endpoint, the authorization matrix,
injection, XSS, JWT forgery and every user flow per role. Both evaluation
scripts reproduce their published numbers to six decimals.

**Q: What would you test first if you added tests?**
`_visible_scans_query` — it's the privacy boundary, and a regression there
leaks medical images. Then the role helpers and the rate limiter, which are
pure functions.

### Critical

**Q: What would you improve?**
In order: automated tests; close `/media`; fix the patient-grouping key and
retrain; split `main.py`; calibrate confidence.

**Q: What design decision would you change?**
The patient-grouping key. Everything else I'd defend — that one is a genuine
mistake, caught only because I audited a claim rather than trusting it.

**Q: What happens if the database goes down?**
Startup fails outright. Mid-flight, requests 500 until the pool recovers;
`pool_pre_ping=True` means new connections are checked before use. No
prediction is lost silently — the handler rolls back and deletes the orphaned
image files.

**Q: What happens if two users do the same thing at once?**
Two predictions are fine — separate rows, uuid4 filenames. Two reviewers
reviewing the same prediction is a **real race**: delete-then-insert isn't
atomic. The unique constraint means it fails safe rather than duplicating, but
it isn't handled gracefully. Row-level locking or an upsert would fix it.

**Q: Could this be used clinically?**
No, and the interface says so. No clinical validation, no regulatory approval,
no PHI handling, no calibration, and it reads one B-scan at a time rather than
a volume. It is a research and demonstration system.

---

## 31. Technical Interview Questions

Each: what the interviewer is really testing → a strong answer → likely
follow-up.

### "Walk me through what happens when a user uploads a scan."

*Testing:* whether you understand your own system end to end.

Request hits `POST /api/predict`. FastAPI resolves dependencies — a database
session, optionally a user from the Bearer token, the anonymous session header.
Content-type check, then a size check against the declared size *and* the
actual bytes. `Image.open` + `.load()` inside a try/except that maps every
decode failure to 400. Then the OOD gate: a grayscale heuristic, then CLIP
zero-shot — if it fails, 422 and **no diagnosis**. Otherwise preprocess to
224×224, forward pass for the class, forward+backward for Grad-CAM, overlay at
the original's dimensions, build the explanation. Write two JPEGs, then three
rows — scan, prediction, gradcam_result — in one transaction, with a rollback
that deletes the files if the commit fails. Response goes back; the frontend
swaps to the analysis workspace.

*Follow-up: "Why is the OOD check after preprocessing?"*
Preprocessing produces the tensor for the classifier; the gate takes the PIL
image. Ordering them the other way would save a little work on rejected
uploads — a fair micro-optimisation, not a correctness issue.

### "Why JWT over sessions?"

*Testing:* whether you know the trade-off or just picked the popular option.

Stateless — no session store, and horizontal scaling is trivial because any
instance can verify a token. **The cost is revocation:** I cannot invalidate a
token before it expires, and mine live 7 days. For a research tool that's
acceptable; for anything handling real patient data I'd use short access tokens
plus refresh tokens, or a denylist.

*Follow-up: "How do you handle a compromised token?"*
Honestly — I can't, within the window. The mitigation I do have is that the
token carries only the user id, so I can demote or delete the account and that
takes effect on the very next request.

### "Your bcrypt cost is 12. Why not higher?"

*Testing:* whether you understand the security/UX trade-off.

Cost 12 is ~200 ms per verification. Each increment doubles it. Higher is more
resistant to offline cracking but makes login sluggish and turns the login
endpoint into a DoS amplifier — which is also why I rate-limit it. 12 is the
current common recommendation and the library default.

*Follow-up: "How would you migrate to a higher cost?"*
Re-hash on successful login: verify with the stored hash, and if its cost is
below target, hash the plaintext again at the new cost and store it. It
migrates users gradually with no password reset.

### "You have an N+1 problem in `list_scans`. How did you find it, and how did you fix it?"

*Testing:* whether you can diagnose performance, not just write features.

I counted the queries by hooking SQLAlchemy's `before_cursor_execute` event —
50 scans produced ~37 queries because `scan.predictions` and `scan.user` were
lazy-loaded per row. Fixed with `selectinload` for the one-to-many and
`joinedload` for the many-to-one. Now 2 queries. I also moved the "has a
prediction" filter into SQL, because it was running in Python *after* the
limit, so `?limit=50` could return fewer than 50 while more existed.

*Follow-up: "Why `selectinload` for one and `joinedload` for the other?"*
`joinedload` on a one-to-many multiplies rows and can be slower for large
collections; `selectinload` issues one extra query with an `IN` clause instead.
For the many-to-one `user`, a join adds no row multiplication, so it's free.

### "How would you scale this to 1000 concurrent users?"

*Testing:* whether you know your own limits.

I wouldn't, as-is — and I can tell you exactly why. Inference is synchronous
and in-process, so it blocks the event loop and predictions serialise behind
one worker. The rate limiter keeps state in-process. Images are on local disk.
Getting there means: move inference to a separate service with a queue and
batching, move the limiter to Redis, move images to object storage, run
multiple API replicas behind a load balancer, and add a read replica or
connection pooler for Postgres.

*Follow-up: "Which would you do first?"*
Separate the inference service. It's the actual bottleneck; the rest are
consequences of assuming one instance.

### "You store medical images. Walk me through the privacy model."

*Testing:* whether you thought about data, not just auth.

Signed-in scans are owned by `user_id`; anonymous scans by an opaque
`sessionStorage` id, so history dies with the browser session. All visibility
goes through one function, so the same rule governs the list and the detail
endpoint — a scan you can't see in history can't be opened by guessing its URL.
A **missing** session id matches nothing rather than everything, which matters:
the naive `IS NULL` filter would have exposed every legacy anonymous scan.

**Then volunteer the gap:** the image *files* are served by StaticFiles without
auth. Filenames are uuid4 so they're unguessable, but possession of a link is
permanent access. That's a deliberate trade-off — `<img>` tags can't send an
Authorization header — and it's the first thing I'd close for real patient
data, with signed URLs or an authenticated proxy.

### "Tell me about a bug you found and how you fixed it."

*Testing:* debugging methodology and honesty.

Pick the OOD gate. It was accepting a grayscale confusion-matrix plot at
p=0.848 and classifying it DME at 77% confidence. I probed the gate directly
rather than guessing and found text documents and UI screenshots were *already*
rejected — only chart imagery got through. That located the cause precisely:
it's an argmax over a fixed prompt set, so it can only reject what a prompt
*describes*, and nothing described a chart. Not a threshold problem — a
coverage problem. Added two negative prompts, then re-validated the *other*
direction: 171/171 real OCT images across three datasets still accepted,
because a stricter gate that turns away real scans is the exact failure this
design already had once.

*Follow-up: "How would you prevent that class of bug?"*
A held-out set of negatives that the gate should reject, run as a test whenever
the prompts change — paired with a positive set, so both directions are
checked.

### "Why Tailwind? Why not CSS modules or styled-components?"

*Testing:* whether styling choices are reasoned.

Utilities keep styles co-located with markup and avoid inventing class names
for everything. What matters more here is that I didn't use raw Tailwind
colours — the palette is semantic tokens (`canvas`, `surface`, `ink`,
`imaging`) declared via `@theme`, so light and dark are two designed palettes
rather than an inversion, and `imaging` stays dark in both because that's how
grayscale scans are read in radiology.

*Follow-up: "What's the downside?"*
Verbose JSX, and refactoring a repeated visual pattern means finding every
copy. I mitigate it by extracting components rather than `@apply`.

### "Explain a trade-off you made that you're not fully happy with."

*Testing:* self-awareness.

Committing a 91 MB checkpoint to git. It makes the repo clone-and-run with no
external hosting, which was the point — the demo works offline. But it's in
git history forever, and it needs Git LFS to push to some hosts. If the model
were retrained often I'd move to a release artefact or a model registry and
fetch it at build time.

---

## 32. 30-Second Explanation

> Visioret classifies retinal OCT scans into four categories — CNV, DME,
> drusen, or normal — and explains each prediction with a Grad-CAM heatmap
> showing which part of the scan drove the decision. Before it classifies
> anything it checks the image really is an OCT scan and refuses if not, so it
> never gives a confident diagnosis on something it shouldn't. It's a full
> stack — PyTorch model, FastAPI backend, PostgreSQL, React frontend, all in
> Docker — with accounts and a reviewer role so a qualified person can correct
> the model on the record. It scores about 95% in-distribution and 88% on
> data from three other hospitals it never trained on.

---

## 33. 2-Minute Explanation

> **The problem.** Reading OCT scans takes expertise, so a classifier could
> help with screening. But a four-class classifier will confidently label
> *anything* as one of its four classes, and even when it's right a clinician
> has no reason to trust it. So the classifier is really the easy half.
>
> **The system.** A user uploads a scan. Before anything else it goes through
> an out-of-distribution gate — a grayscale check, then a CLIP zero-shot check
> against ten text prompts where "an OCT scan" must win. If it doesn't, the API
> returns 422 with no diagnosis at all. If it passes, a ResNet-50 fine-tuned on
> four public datasets classifies it, Grad-CAM produces a heat overlay from the
> last convolutional block, and the system writes an interpretation combining a
> per-class clinical description with a sentence derived from the heatmap's own
> geometry — deliberately only coarse position, because there's no layer
> segmentation to justify anything more specific.
>
> **The stack.** FastAPI serving the model in-process, PostgreSQL with
> SQLAlchemy and seven Alembic migrations, a React and TypeScript frontend,
> three Docker containers. Auth is bcrypt plus stateless JWTs, with three roles
> — viewer, reviewer, admin. Reviewers can record corrections, and that's
> role-gated because a correction is a training-grade label asserting the model
> was wrong, so it needs a qualified author. Admin can't be granted through the
> API at all — only directly against the database.
>
> **The results.** 95.17% accuracy in-distribution. More interestingly, trained
> on one dataset it got 82% on external data with drusen recall at 0.48;
> training across four datasets took that to 88% with drusen recall 0.79, while
> in-distribution barely moved. That generalization gap is the more meaningful
> result.

---

## 34. 10-Minute Technical Explanation

**1. Framing (1 min).** As §33, plus: the reason half the codebase is about
trust rather than accuracy.

**2. Data and methodology (2 min).**
Four public datasets: Kermany OCT2017 as primary, plus Noor Eye Hospital,
OCTDL and Duke for generalization. Three correctness decisions worth naming:
- Kermany's official split leaks ~85% of test patients into train, so it isn't
  used — everything is pooled and re-split by patient with `GroupShuffleSplit`,
  persisted to JSON so the test set never moves.
- Noor is labelled per B-scan from the *filename*, not the folder, because a
  diagnosed patient's volume still contains normal-looking slices.
- OCTDL's and Duke's `AMD` class is excluded entirely rather than guessing a
  CNV/DRUSEN mapping.

**Then volunteer the caveat** — the grouping key includes the class name, 40.9%
of test images share a patient with training, the effect was measured, and it
runs conservative (0.9180 leaked vs 0.9750 clean).

**3. The model (1.5 min).**
ResNet-50, ImageNet-pretrained, `layer3`/`layer4`/`fc` unfrozen — 22.1M of
23.5M parameters. Class-weighted cross-entropy for imbalance, Adam at 1e-4,
`ReduceLROnPlateau` on validation macro-F1, early stopping with patience 5,
mixed precision on CUDA. Full resume state saved every epoch — which mattered,
because a power cut interrupted a run and it resumed without losing progress.

**4. Explainability (1.5 min).**
Grad-CAM implemented manually with forward and backward hooks on `layer4`:
capture activations, backprop from the predicted class score, average gradients
spatially for channel weights, weighted-sum, ReLU, normalise, resize **to the
original's dimensions** — that last part matters, because an earlier version
shrank the original to 224×224 instead and a 1536×496 scan's overlay was
compressed 3× horizontally, which mislocated findings for the viewer.

The written explanation is a static per-class clinical description plus one
dynamic sentence computed from the heatmap centroid and spread. It never claims
a retinal layer, because there's no segmentation to justify it.

**5. The safety gate (1.5 min).**
Two stages, cheapest first. Grayscale heuristic, then CLIP zero-shot argmax
over ten prompts. **Two failures worth telling:** the original feature-distance
gate was calibrated on Kermany only and rejected 3 of 5 genuine Noor scans —
"is this an OCT scan?" had become "does this look like a Kermany OCT scan?".
And later, a grayscale chart was accepted at p=0.848, because argmax over a
fixed prompt set can only reject what a prompt describes.

**6. Application architecture (2 min).**
Three containers. The model runs in the API process — simple, at the cost of
blocking inference. Seven tables; `model_versions` is keyed by a **SHA-256 of
the checkpoint's contents**, so the same weights are the same version on every
machine. That replaced an mtime-based key which broke on `git clone` and left
the metrics page permanently empty on any fresh machine.

All scan visibility flows through one function, so the list and detail
endpoints share a rule by construction. A missing anonymous session id matches
*nothing* rather than everything.

**7. Results and honest limits (0.5 min).**
95.17% / 0.9233 in-distribution, 88.1% / 0.90 cross-dataset, both regenerable
by script. No test suite, no calibration, unauthenticated image files, no
revocation on tokens, and a footprint that needs a paid VPS.

---

## 35. How to Study This Project

A sequenced curriculum. Don't skip ahead — each stage assumes the last.

### Stage 1 — Understand the problem (30 min)
**Read:** `README.md` §What it does + §Results; `DEFENSE_NOTES.md` §1.
**Understand first:** what OCT is; what the four classes mean clinically.
**Experiment:** 1, 2, 3.
**You should be able to answer:** What are the four classes? What does the OOD
gate do and why does it exist? What are the two headline numbers?

### Stage 2 — Architecture (45 min)
**Read:** this document §2 and §3.
**Concepts:** client–server, REST, containers.
**Experiment:** `docker compose ps`, `docker compose logs backend`.
**Answer:** What are the three containers? Where does the model actually run?
Which directory is bind-mounted and which is baked into the image — and why
does that matter when you edit code?

### Stage 3 — The entry point (30 min)
**Read:** `backend/main.py` lines 1–135 (imports, constants, `lifespan`).
**Concepts:** ASGI, application lifespan, module-level global state.
**Answer:** What happens before the first request is served? Why is the model
loaded there and not per-request?

### Stage 4 — One request end to end (1 hr)
**Read:** `predict_endpoint` in full, then `model/inference.py`.
**Concepts:** dependency injection, multipart uploads, `flush` vs `commit`.
**Experiment:** 2 and 3, watching `docker compose logs -f backend`.
**Answer:** Trace an upload from HTTP to database. What happens if the commit
fails after the files are written?

### Stage 5 — The database (1 hr)
**Read:** `backend/db/models.py`, then all 7 migrations in order.
**Concepts:** ORM, foreign keys, cascades, migrations.
**Experiment:** 12, plus `psql` exploration from §19.3.
**Answer:** Why is `scans.user_id` nullable? What makes `feedback` one-to-one?
What does the migration order tell you about how the project grew?

### Stage 6 — Auth and authorization (1 hr)
**Read:** `backend/auth.py` in full; the `Depends` on each endpoint.
**Concepts:** hashing, salting, JWT, 401 vs 403.
**Experiment:** 5, 6, 7.
**Answer:** Why bcrypt not SHA-256? Why does demoting a user take effect
immediately despite an unchanged token? Why can't an admin create another
admin?

### Stage 7 — The frontend (1.5 hr)
**Read:** `App.tsx` → `api/client.ts` → `context/AuthContext.tsx` →
`pages/PredictPage.tsx` → `components/analysis/ScanAnalysis.tsx`.
**Concepts:** components, props vs state, hooks, context, async rendering.
**Experiment:** open DevTools, watch the Network tab during a prediction.
**Answer:** How does a token get onto a request? Why does `ScanAnalysis` hold
no state? How does the app distinguish an OOD rejection from an error?

### Stage 8 — The ML pipeline (2 hr)
**Read:** `model/dataset.py`, then `model/train_full.py`, then
`model/evaluate.py`.
**Concepts:** transfer learning, class imbalance, grouped splitting,
precision/recall/F1, confusion matrices.
**Experiment:** 11 and 14.
**Answer:** Why re-split rather than use the official split? What does
`remainder_val_fraction` correct for? Why weight the loss?

### Stage 9 — The safety gate (45 min)
**Read:** `model/ood_detector.py`, `model/clip_ood.py` (docstrings especially).
**Concepts:** out-of-distribution detection, zero-shot classification.
**Experiment:** 3 and 14; try your own images.
**Answer:** Why CLIP rather than feature distance? Why argmax rather than a
threshold? What class of image can this gate still not reject?

### Stage 10 — Infrastructure (1 hr)
**Read:** `docker-compose.yml`, both Dockerfiles, `frontend/nginx.conf`.
**Concepts:** images vs containers, layer caching, multi-stage builds, volumes,
SPA fallback, cache headers.
**Answer:** Why is `COPY requirements.txt` before `COPY backend/`? Why must
`index.html` be `no-cache` while `/assets/` is `immutable`?

### Stage 11 — Weaknesses (45 min)
**Read:** §24 of this document; `REVIEW_CHECKPOINTS.md`.
**Answer:** Name three weaknesses and how you'd fix each. Which single design
decision would you change, and why that one?

### Stage 12 — Rehearse (1 hr)
Deliver §32, §33 and §34 out loud without notes. Then have someone ask you five
questions from §30 at random.

---

## 36. Mastery Checklist

### Understanding
- [ ] I can explain what the project does in 30 seconds without notes.
- [ ] I can explain *why* the OOD gate exists, not just what it does.
- [ ] I can name the four classes and what each means clinically.
- [ ] I can state both headline numbers and what data each was measured on.
- [ ] I can explain the difference between the in-distribution and cross-dataset results, and why the second matters more.

### Architecture
- [ ] I can draw the architecture from memory.
- [ ] I know all five entry points.
- [ ] I know which directory is bind-mounted vs baked into the image.
- [ ] I can explain why the model runs in the API process and what it costs.
- [ ] I can trace a request from browser click to database row and back.

### Code
- [ ] I can find any feature's code without searching.
- [ ] I can explain `_visible_scans_query` line by line, including `sa_false()`.
- [ ] I can explain `lifespan` and why the model loads there.
- [ ] I can explain the Grad-CAM implementation step by step.
- [ ] I can explain what `flush()` does that `commit()` doesn't.
- [ ] I can explain why `overlay_gradcam` resizes the heatmap, not the image.

### Database
- [ ] I can draw the ER diagram from memory.
- [ ] I can explain every nullable column and why it's nullable.
- [ ] I can explain what makes `feedback` one-to-one.
- [ ] I can explain what the migration order reveals about the project's growth.
- [ ] I can write a migration safely for a populated table.

### Auth and security
- [ ] I can explain the full registration → login → authenticated-request flow.
- [ ] I can explain bcrypt vs SHA-256 for passwords.
- [ ] I can explain 401 vs 403 and point at where each is raised.
- [ ] I can explain why CSRF doesn't apply here.
- [ ] I can name five security weaknesses **without being prompted**.
- [ ] I can explain the login timing defence and why it's needed.

### Frontend
- [ ] I can explain props vs state with an example from this codebase.
- [ ] I can explain how the auth token reaches a request.
- [ ] I can explain what `canAnimate()` prevents and why it exists.
- [ ] I can explain the two shapes of a FastAPI 422 and how the client handles both.

### Operations
- [ ] I can run the project from a clean clone.
- [ ] I can create an admin account.
- [ ] I can find and read the backend logs.
- [ ] I can inspect the database two different ways.
- [ ] I can explain why a `backend/` edit needs a rebuild but a `model/` edit doesn't.
- [ ] I can regenerate every published number.

### Critical thinking
- [ ] I can name three weaknesses and propose fixes.
- [ ] I can explain the patient-grouping caveat *and* why it's conservative.
- [ ] I can describe a bug I found and how I diagnosed it.
- [ ] I can explain what I'd change if I started again.
- [ ] I can say "the repository doesn't record why" without discomfort.
- [ ] I can explain what the system deliberately does **not** do.

---

## 37. Glossary

| Term | Meaning in this project |
|---|---|
| **OCT** | Optical Coherence Tomography — cross-sectional retinal imaging |
| **B-scan** | A single 2D cross-sectional OCT slice. The unit this system classifies |
| **CNV** | Choroidal neovascularization — abnormal vessel growth, wet AMD |
| **DME** | Diabetic macular edema — intraretinal fluid from leaking vessels |
| **DRUSEN** | Sub-retinal deposits, an early sign of AMD |
| **AMD** | Age-related macular degeneration |
| **Grad-CAM** | Gradient-weighted Class Activation Mapping — the heatmap technique |
| **OOD** | Out-of-distribution — an input unlike anything the model was trained on |
| **CLIP** | OpenAI's image–text model, used here for zero-shot OCT detection |
| **Zero-shot** | Classifying into categories the model was never trained on |
| **Transfer learning** | Reusing ImageNet-pretrained weights, fine-tuning some layers |
| **Macro F1** | F1 averaged equally across classes — doesn't hide poor rare-class performance |
| **Confusion matrix** | Rows = true label, columns = predicted. Diagonal = correct |
| **Patient-grouped split** | Splitting so no patient's images span train and test |
| **Data leakage** | Test information reaching training, inflating scores |
| **JWT** | JSON Web Token — a signed, stateless auth token |
| **bcrypt** | Deliberately slow, salted password hashing |
| **ORM** | Object-Relational Mapper — Python classes ↔ database tables |
| **Migration** | A versioned, ordered schema change script |
| **CORS** | Cross-Origin Resource Sharing — the browser rule this API opts into |
| **CSP** | Content Security Policy — restricts what the page may load |
| **SPA** | Single-Page Application — routing happens in JavaScript |
| **N+1 query** | One query for a list, then one per item. Fixed by eager loading |
| **IDOR** | Insecure Direct Object Reference — accessing others' data by guessing ids |
| **Idempotent** | Repeating the request has the same effect as doing it once |
| **Fixed-window rate limit** | Count requests per time window; simple, allows 2× at boundaries |
| **Content-addressed** | Identified by a hash of contents, not by name or timestamp |

---

## 38. Appendix

### A. All commands in one place

```bash
# Run everything
docker compose up -d --build
docker compose down                # keeps data
docker compose down -v             # destroys volumes

# Health and logs
curl http://localhost:8000/api/health
docker compose logs -f backend
docker compose ps

# Roles
docker compose exec backend python -m backend.grant_role --list
docker compose exec backend python -m backend.grant_role you@example.com admin

# Cleanup
docker compose exec backend python -m backend.purge_anonymous --dry-run
docker compose exec backend python -m backend.purge_anonymous --all

# Migrations
docker compose exec backend sh -c "cd backend && alembic current"
docker compose exec backend sh -c "cd backend && alembic upgrade head"
docker compose exec backend sh -c "cd backend && alembic history"

# ML (host, needs the datasets and the venv)
python model/train_full.py --smoke-test
python model/train_full.py
python model/evaluate.py
python -m model.evaluate_cross_dataset
python -m model.audit_patient_leakage

# Frontend
cd frontend && npm install && npm run dev
cd frontend && npx tsc -b
cd frontend && npx oxlint

# Streamlit
streamlit run app.py
```

### B. Key numbers to memorise

| | |
|---|---|
| Classes | 4 — CNV, DME, DRUSEN, NORMAL |
| In-distribution | **95.17% acc / 0.9233 macro F1**, 13,146 images |
| Patient-disjoint subset | **97.50% / 0.9541**, 7,771 images |
| Cross-dataset | **88.1% / 0.895**, 2,712 images, 3 external sources |
| Before multi-dataset training | 82.0% / 0.78, DRUSEN recall 0.48 |
| Trainable parameters | 22,071,300 of 23,516,228 |
| Datasets | 4 |
| API endpoints | 12 |
| Database tables | 7 |
| Migrations | 7 |
| Frontend routes | 7 + catch-all |
| CLIP prompts | 10 (1 accept, 9 reject) |
| Token lifetime | 7 days |
| bcrypt cost | 12 |
| Upload limit | 12 MB |
| Rate limits | 10 logins / 5 min; 5 registrations / hour |
| Cold start | 66 s |
| Peak memory | 686 MB |

### C. Document cross-reference

| For | Read |
|---|---|
| Setup and usage | `README.md` |
| Complete feature inventory + gaps | `FEATURES.md` |
| Build log, checkpoint by checkpoint | `TODO.md` |
| Decisions, dead ends, superseded designs | `PROJECT_CONTEXT.md` |
| What was tested and found, with evidence | `REVIEW_CHECKPOINTS.md` |
| Viva answers with regeneration commands | `DEFENSE_NOTES.md` |
| Free hosting, step by step | `DEPLOYMENT.md` |
| Deep understanding (this file) | `PROJECT_MASTERY.md` |

### D. What this document does **not** cover

Stated so you know the boundaries of your own preparation:

- **The clinical medicine.** Class descriptions come from `explanations.py`.
  Nothing here validates them against an ophthalmology source.
- **Line-by-line coverage of every frontend component.** The architecturally
  important ones are covered; the rest follow the same patterns.
- **`model/oct_preprocessing.py` internals.** It is retired; only the negative
  result matters.
- **Streamlit specifics.** `app.py` is a thin, standalone reuse of the same
  inference code.
- **Original motives where the repository is silent.** Marked
  **[NOT DETERMINABLE]** throughout rather than guessed.

---

*End of document. If something here contradicts the code, the code is right —
verify, then correct this file.*
