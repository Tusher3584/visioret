# Visioret — Explainable AI for Retinal OCT Disease Classification

Visioret classifies retinal **OCT (Optical Coherence Tomography)** B-scans into
four categories — **CNV, DME, DRUSEN, NORMAL** — and explains every prediction
with a Grad-CAM heatmap plus a written interpretation of what the highlighted
region means clinically. Qualified reviewers can correct predictions, and those
corrections are recorded against the exact model version that produced them.

It is a full-stack system: a fine-tuned ResNet-50, a FastAPI service, a
PostgreSQL database with migration-managed schema, and a React front end, all
runnable with a single `docker compose up`.

> **Not a medical device.** This is a research and demonstration system built as
> a 4th-year undergraduate final project (SPL3) at the Institute of Information
> Technology, University of Dhaka. It is not approved for clinical use and must
> not be used to make real diagnostic decisions.

---

## Table of contents

- [What it does](#what-it-does)
- [Results](#results)
- [Quick start (Docker)](#quick-start-docker)
- [Configuration](#configuration)
- [Roles and accounts](#roles-and-accounts)
- [Architecture](#architecture)
- [API reference](#api-reference)
- [Running without Docker](#running-without-docker)
- [Training and evaluation](#training-and-evaluation)
- [Datasets and attribution](#datasets-and-attribution)
- [Project structure](#project-structure)
- [Limitations](#limitations)
- [Further documentation](#further-documentation)

---

## What it does

1. **Validates the input.** Before classifying anything, an out-of-distribution
   gate checks the upload is really an OCT scan — a grayscale heuristic, then a
   CLIP zero-shot semantic check. A non-OCT image is rejected with **HTTP 422**
   and *no diagnosis is produced*. A classifier with only four output classes
   will confidently label a photograph of a cat as `CNV`; this is what stops
   that.
2. **Classifies** the scan with a ResNet-50 fine-tuned on four public OCT
   datasets, returning a predicted class and a full probability distribution.
3. **Explains** the result with Grad-CAM computed on `layer4`, rendered as an
   overlay, plus a written interpretation combining a per-class clinical
   description with a sentence derived from the heatmap's own geometry.
4. **Persists** the scan, prediction, heatmap and model version, so every result
   stays attributable to the exact checkpoint that produced it.
5. **Accepts review.** A reviewer can mark a prediction correct or incorrect and
   supply the correct class — a human label with provenance.

## Results

Both figures below are measured on data the model never trained on, and both
reports are reproducible from this repo (see
[Training and evaluation](#training-and-evaluation)).

**In-distribution** — Kermany held-out test set, 13,146 images from patients
reserved before any training:

| Subset | n | Accuracy | Macro F1 |
|---|---|---|---|
| Full reserved test set | 13,146 | **95.17%** | **92.33%** |
| Patients never seen in training | 7,771 | **97.50%** | **95.41%** |

Two rows, because the grouping key has a known flaw and the honest thing is
to show both — see [Known limitation](#known-limitation-patient-grouping)
below. The short version: the headline 95.17% is *conservative*, not
inflated.

**Cross-dataset generalization** — 2,712 held-out images from Noor Eye Hospital,
OCTDL and Duke, i.e. different scanners, different hospitals, different
countries:

| | Accuracy | Macro F1 | DRUSEN recall |
|---|---|---|---|
| Trained on Kermany only | 82.0% | 0.78 | 0.48 |
| **After multi-dataset fine-tuning** | **88.1%** | **0.90** | **0.79** |

The second row is the point of the experiment: a model trained on one dataset
looked excellent in-distribution and fell apart on other scanners. Training
across four sources fixed that at essentially no in-distribution cost
(95.42% → 95.17%).

Full per-class breakdowns: `model/checkpoints/evaluation_report.txt` and
`model/checkpoints/cross_dataset_evaluation_report.txt`.

### One correctness decision worth knowing about

Kermany's *official* train/test split leaks roughly **85% of its test patients
into the training set** — the same patient's B-scans appear on both sides. Any
accuracy measured against that split is inflated.

Visioret therefore **ignores the official split**. All images are pooled and
re-split by patient ID using `GroupShuffleSplit`, and the split is persisted to
`model/checkpoints/patient_split.json` so the held-out test set never changes
between runs.

### Known limitation: patient grouping

The grouping key is `f"{class_name}-{number}"` rather than the bare patient
number. **896 of Kermany's 4,657 numeric IDs (19.2%) appear under more than one
class folder** — clinically coherent, since a patient can have wet AMD in one
eye, drusen in the fellow eye, and normal-looking slices from both. Prefixing
the class therefore splits one patient into up to three groups, which the
splitter can scatter across train, val and test. **5,375 of the 13,146 test
images (40.9%) belong to a patient seen during training.**

The direction of that effect was measured, not assumed —
`python -m model.audit_patient_leakage` regenerates this table:

| Subset | n | Accuracy | Macro F1 | DRUSEN F1 |
|---|---|---|---|---|
| Full test set | 13,146 | 0.9517 | 0.9233 | 0.817 |
| Leaked (patient seen in training) | 5,375 | 0.9180 | 0.8878 | 0.752 |
| Clean (patient never seen) | 7,771 | 0.9750 | 0.9541 | 0.882 |

The model scores **lower** on the leaked patients — the opposite of what
memorisation produces. Those patients are, by construction, the
multi-diagnosis ones: the clinically ambiguous cases sitting on the
CNV/DRUSEN boundary where the model is weakest. So the reported 95.17% is
conservative, and 97.50% is the genuinely patient-disjoint figure — read as
*"performance on single-diagnosis patients never seen in training"*, since
that subset is a different population, not a drop-in replacement.

Fixing the key would change which patients land in which split, invalidating
the persisted split the current checkpoint was trained against, and would
require a full retrain. It is documented rather than silently corrected.

**The cross-dataset result is unaffected:** OCTDL keys on the bare numeric ID,
Duke on the per-patient volume folder, and Noor's class prefix is *correct*
there because its patient folders are numbered independently inside each class
folder.

## Quick start (Docker)

Requires Docker Desktop (or Docker Engine + Compose v2).

```bash
git clone <this-repo> && cd visioret
```

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Then edit `.env` and set `JWT_SECRET_KEY` to a random value — generate one with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Start everything:

```bash
docker compose up -d --build
```

Open **http://localhost:5173**.

| Service | URL | Notes |
|---|---|---|
| Frontend | http://localhost:5173 | nginx serving the built React app |
| API | http://localhost:8000 | FastAPI (Uvicorn) |
| API docs | http://localhost:8000/docs | auto-generated OpenAPI UI |
| Database | `localhost:5433` | Postgres 16 (5433, not 5432 — see below) |

**First run is slow.** The backend downloads ImageNet ResNet-50 weights and the
CLIP model (`openai/clip-vit-base-patch32`) on first use. Both are cached in
named Docker volumes, so this happens once. Database migrations run
automatically on backend startup.

> **Why port 5433?** The development machine already had a native PostgreSQL
> service bound to 5432. If 5432 is free on your machine you can change the
> mapping in `docker-compose.yml`; nothing inside the containers depends on the
> host port.

Check it is healthy:

```bash
curl http://localhost:8000/api/health
```

You should see the device, the loaded checkpoint, the four class names, and
`ood_gate_active: true`.

Shut down (data is preserved in named volumes):

```bash
docker compose down
```

## Configuration

| Variable | Required | Used by | Purpose |
|---|---|---|---|
| `JWT_SECRET_KEY` | **yes** | backend | Signing key for auth tokens |
| `DATABASE_URL` | outside Docker | backend | SQLAlchemy connection string |
| `VITE_API_BASE_URL` | build-time | frontend | API origin baked into the bundle |

`JWT_SECRET_KEY` has **no default**. `backend/auth.py` raises a `RuntimeError`
at import if it is missing, and `docker-compose.yml` refuses to start without
it. That is deliberate: a fallback signing key is a fallback that ends up in
production, and anyone who knows it can forge a token for any account.

`.env` is gitignored. Never commit it.

## Roles and accounts

Three roles, all enforced **server-side** — the UI hides controls too, but that
is presentation only and is not what protects anything.

| Capability | anonymous | viewer | reviewer | admin |
|---|---|---|---|---|
| Analyze a scan | ✅ | ✅ | ✅ | ✅ |
| See Grad-CAM + explanation | ✅ | ✅ | ✅ | ✅ |
| Scan archive scope | own session | own scans | **all** | **all** |
| Record a correction | ❌ | ❌ | ✅ | ✅ |
| View model metrics | ❌ | ❌ | ✅ | ✅ |
| Manage accounts | ❌ | ❌ | ❌ | ✅ |

Registration always creates a **viewer**. The reasoning: recording a correction
writes a human-authored label asserting the model was wrong — exactly the kind
of record that would feed a retraining loop — so it needs a qualified author,
not whoever signed up last.

**Anonymous use is fully supported** and privacy-scoped: an opaque id in
`sessionStorage` (not `localStorage`) scopes anonymous history to a single
browser session. A missing id matches *nothing* rather than every anonymous
scan. `backend/purge_anonymous.py` deletes anonymous scans and their image files
for good.

### Creating an admin

Admin cannot be granted through the API, by anyone, ever. It is issued by hand
against the database:

```bash
docker compose exec backend python -m backend.grant_role --list
```

```bash
docker compose exec backend python -m backend.grant_role you@example.com admin
```

An admin can then promote accounts between `viewer` and `reviewer` from the
in-app admin page. Admins cannot grant admin, modify another admin, or change
their own role.

## Architecture

```
Browser (React SPA, nginx)
   │  fetch + Bearer JWT
   ▼
FastAPI  ──►  OOD gate (grayscale → CLIP zero-shot)
   │              └─ reject → 422, no diagnosis
   │
   ├──►  ResNet-50 classifier  ──►  Grad-CAM (hooks on layer4)  ──►  explanation
   │
   ├──►  image files on disk (backend/media/)
   └──►  PostgreSQL (SQLAlchemy + Alembic)
             users · scans · model_versions · predictions
             gradcam_results · feedback · evaluation_metrics
```

**Stack:** PyTorch · CLIP (`transformers`) · FastAPI · SQLAlchemy 2 · Alembic ·
PostgreSQL 16 · React 19 · TypeScript · Vite · Tailwind CSS v4 · React Router 7 ·
Framer Motion · Docker Compose.

`model_versions` is keyed by the checkpoint file's modification time, so
retraining creates a new row and no historical prediction is ever silently
re-attributed to a model that did not make it.

## API reference

Interactive docs at `http://localhost:8000/docs`.
Auth: 🔓 open · 🔑 signed in · 👁 reviewer · 🛡 admin.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/health` | 🔓 | Device, checkpoint, classes, OOD gate status |
| `POST` | `/api/auth/register` | 🔓 | Create account (always `viewer`) |
| `POST` | `/api/auth/login` | 🔓 | Obtain JWT |
| `GET` | `/api/auth/me` | 🔑 | Current account |
| `PATCH` | `/api/auth/me` | 🔑 | Edit own name / password |
| `POST` | `/api/predict` | 🔓 | Validate → classify → Grad-CAM → explain → persist |
| `GET` | `/api/scans` | 🔓 | Scan archive, scoped by identity |
| `GET` | `/api/scans/{id}` | 🔓 | One scan's full analysis |
| `PUT` | `/api/scans/{id}/feedback` | 👁 | Record correct/incorrect + corrected class |
| `GET` | `/api/metrics` | 👁 | Stored evaluation results |
| `GET` | `/api/admin/users` | 🛡 | All accounts with scan/review counts |
| `PATCH` | `/api/admin/users/{id}/role` | 🛡 | Promote/demote viewer ↔ reviewer |

## Running without Docker

Useful for fast backend iteration. Requires Python 3.10+ and Node 20+.

**Backend** — needs a reachable Postgres. The simplest option is to run only the
database in Docker (`docker compose up -d db`) and point at it on port 5433:

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

With `.env` present at the project root:

```bash
python -m alembic -c backend/alembic.ini upgrade head
```

```bash
python -m uvicorn backend.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend && npm install && npm run dev
```

> The API's CORS policy allows only `http://localhost:5173` and
> `http://127.0.0.1:5173`. If Vite reports that 5173 was busy and it started on
> 5174 instead, the browser will block every request — free 5173 rather than
> fighting the symptom, or add the new origin in `backend/main.py`.

**Streamlit demo** — `app.py` is a minimal single-file UI over the same model
pipeline (including the same OOD gate), kept for quick model-only demos:

```bash
streamlit run app.py
```

### GPU

`requirements.txt` installs a CPU build of PyTorch, and the Docker backend is
CPU-only on purpose so it runs anywhere. For training, install a CUDA build in
the venv:

```bash
pip uninstall -y torch torchvision && pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
```

```bash
python -c "import torch; print(torch.cuda.is_available())"
```

Every script auto-detects CUDA. A checkpoint trained on GPU loads fine on CPU —
`torch.load(..., map_location=device)` remaps the tensors.

## Training and evaluation

The committed checkpoint `model/checkpoints/resnet50_oct.pth` (94 MB) is
tracked in git deliberately, so the system runs out of the box with no training
step. Retraining is optional.

Training needs the full datasets, which are **not** in this repo (see below) and
must be downloaded and their paths set at the top of `model/dataset.py`.

```bash
python model/train_full.py
```

- ResNet-50, ImageNet-pretrained; `layer3`, `layer4`, `fc` unfrozen.
- Class-weighted cross-entropy, Adam `lr=1e-4`, `weight_decay=1e-4`.
- `ReduceLROnPlateau` on val macro-F1; early stopping, patience 5, max 30 epochs.
- Mixed precision when CUDA is available.
- Patient-grouped split, persisted to `patient_split.json`.
- Full resume state (model + optimizer + scheduler + scaler + epoch) is written
  every epoch, so an interrupted run — a power cut, in practice — resumes
  without losing progress.

Evaluate:

```bash
python model/evaluate.py
```

```bash
python model/evaluate_cross_dataset.py
```

Each writes a report and a confusion matrix into `model/checkpoints/`, and
records the metrics into the database so the in-app metrics page shows real
evaluation output rather than hardcoded numbers.

> Retraining produces a new checkpoint and therefore a new `model_versions` row.
> Re-run both evaluation scripts afterwards so the metrics page is not
> describing a model that no longer exists.

## Datasets and attribution

Four public datasets, pooled and re-split by patient:

| Dataset | Source | Classes used |
|---|---|---|
| **Kermany OCT2017** | Guangzhou / UCSD | CNV, DME, DRUSEN, NORMAL |
| **Noor Eye Hospital** | Tehran, Iran | CNV, DRUSEN, NORMAL |
| **OCTDL** | Optovue | NORMAL, DME |
| **Duke (Srinivasan 2014)** | Duke / Harvard / Michigan | NORMAL, DME |

Two labelling decisions made for correctness rather than convenience:

- **Noor is labelled per B-scan, from the filename** (`003_Normal.jpg`), not from
  the patient folder. A diagnosed patient's volume still contains normal-looking
  slices; the folder label would have injected real label noise.
- **OCTDL's and Duke's `AMD` class is excluded entirely**, because it is not
  split into CNV vs DRUSEN and guessing a mapping would have fabricated labels.

Patient IDs are namespaced per source (`noor-`, `octdl-`, `duke-`) so they can
never collide.

**Bundled images.** `samples/` (4 images) and `data/` (400 images, 100 per
class) are from Kermany OCT2017, included so the repo demonstrates results with
no download. OCT2017 is from D.S. Kermany et al., *"Identifying Medical
Diagnoses and Treatable Diseases by Image-Based Deep Learning"*, **Cell**, 2018,
distributed under CC BY 4.0
(<https://data.mendeley.com/datasets/rscbjbr9sj/2>). These are an unmodified
subset, redistributed with attribution per that license.

## Project structure

```
app.py                            # Streamlit demo over the same model pipeline
docker-compose.yml                # db (5433) + backend (8000) + frontend (5173)
requirements.txt                  # Python deps, pinned for the ML stack
.env.example                      # copy to .env and fill in

model/
  inference.py                    # load_model, preprocess, predict, manual Grad-CAM
  dataset.py                      # dataset collectors + patient-grouped splitting
  train_full.py                   # the real training script (resume + warm-start)
  evaluate.py                     # in-distribution evaluation
  evaluate_cross_dataset.py       # external-generalization evaluation
  ood_detector.py                 # OOD gate entry point (grayscale → CLIP)
  clip_ood.py                     # CLIP zero-shot OCT check
  explanations.py                 # clinical text + heatmap-geometry description
  oct_preprocessing.py            # RETIRED experiment, kept as evidence (see TODO.md)
  compute_ood_stats.py            # RETIRED calibration script for the old OOD stage
  train_quick.py                  # LEGACY 400-image demo trainer
  checkpoints/
    resnet50_oct.pth              # the trained model — tracked in git
    patient_split.json            # persisted patient-grouped split
    external_patient_split.json   # persisted split for the external datasets
    evaluation_report.txt         # + confusion_matrix.png
    cross_dataset_evaluation_report.txt

backend/
  main.py                         # FastAPI app, all 12 endpoints
  auth.py                         # bcrypt hashing, JWT, role dependencies
  schemas.py                      # Pydantic request/response models
  storage.py                      # scan image persistence
  grant_role.py                   # role management CLI (only way to make an admin)
  purge_anonymous.py              # delete anonymous scans + their files
  db/models.py                    # SQLAlchemy models (7 tables)
  alembic/versions/               # 7 migrations
  Dockerfile                      # CPU-only; model/ is volume-mounted, not baked in

frontend/
  src/api/                        # typed client; ApiError carries HTTP status
  src/components/                 # layout, analysis workspace, UI primitives
  src/context/                    # auth + theme
  src/pages/                      # predict, history, scan detail, metrics,
                                  #   login, profile, admin
  src/lib/                        # identicon, anon session, motion helpers
  index.css                       # Tailwind v4 @theme semantic design tokens
  nginx.conf                      # SPA fallback routing

data/                             # 400-image Kermany subset (ImageFolder layout)
samples/                          # 4 images, one per class
```

## Limitations

Stated plainly, because a system that hides these is harder to trust than one
that names them:

- **Not a medical device.** No clinical validation, no regulatory approval.
- **JPEG/PNG only** — no DICOM support.
- **One B-scan at a time** — no volume (3D) analysis.
- **No layer segmentation**, so explanations describe *where* in the image the
  model looked, never which retinal layer. Claiming a layer without segmenting
  one would be fabrication.
- **Reviewer corrections are stored but not consumed** — there is no automatic
  retraining loop yet.
- **Auth is deliberately minimal** — no email verification, password reset,
  OAuth, refresh tokens, or token revocation. A 7-day JWT cannot be invalidated
  before it expires.
- **No rate limiting**, and no automated test suite; verification to date has
  been manual and script-driven.
- **Confidence values are raw softmax outputs** and are characteristically very
  high. No calibration analysis has been done.
- **No PHI handling.** Scans are not linked to patient identities.

## Further documentation

| File | What it is |
|---|---|
| [`FEATURES.md`](FEATURES.md) | Complete feature inventory, every measured number, all known gaps |
| [`TODO.md`](TODO.md) | The living checkpoint log — what was built, in order, and why |
| [`REVIEW_CHECKPOINTS.md`](REVIEW_CHECKPOINTS.md) | Pre-defense review plan and findings |
| [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) | Deep context: decisions, dead ends, and their reasoning |
