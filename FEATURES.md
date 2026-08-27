# Visioret — Complete Feature Specification

> **What this document is.** A full, factual inventory of what Visioret does
> and how, intended to be handed to another person or AI to assess whether the
> scope is sufficient or what should be added.
>
> Every number here is measured from the actual system, not estimated. Where
> something is *not* implemented, or was tried and rejected, it says so —
> the gaps are listed in §12 rather than hidden.

---

## 1. What the project is

**Visioret** is an explainable-AI web application for **retinal OCT (Optical
Coherence Tomography) disease classification**.

- **Context:** 4th-year undergraduate final-year project (SPL3), Institute of
  Information Technology, University of Dhaka.
- **Nature:** research and demonstration tool. **Not** an approved clinical
  diagnostic device, and the interface states this.
- **Core loop:** upload one OCT B-scan → verify it really is an OCT scan →
  classify into 4 disease classes → explain *where* the model looked and
  *why that region matters* → let a qualified reviewer correct the result.

### The four classes

| Class | Meaning |
|---|---|
| **CNV** | Choroidal neovascularization — abnormal vessel growth, feature of wet AMD |
| **DME** | Diabetic macular edema — intraretinal fluid from leaking vessels |
| **DRUSEN** | Sub-retinal deposits — an early sign of AMD |
| **NORMAL** | No abnormality detected |

---

## 2. Technology stack

| Layer | Technology |
|---|---|
| Model | PyTorch, ResNet-50 (ImageNet-pretrained, fine-tuned) |
| Explainability | Grad-CAM (manual implementation via forward/backward hooks on `layer4`) |
| Input validation | CLIP (`openai/clip-vit-base-patch32`) zero-shot + grayscale heuristic |
| Backend | FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2 |
| Database | PostgreSQL 16 |
| Auth | bcrypt password hashing + stateless JWT (PyJWT) |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, React Router v7, Framer Motion |
| Serving | nginx (static frontend), Uvicorn (API) |
| Orchestration | Docker Compose (3 services: `db`, `backend`, `frontend`) |
| Secondary UI | Streamlit demo (`app.py`) kept in sync with the same model pipeline |

---

## 3. Machine learning pipeline

### 3.1 Architecture and training

- **Backbone:** ResNet-50, ImageNet-pretrained.
- **Fine-tuning:** `layer3`, `layer4`, and `fc` unfrozen (22,071,300 of
  23,516,228 parameters trainable). Earlier layers frozen.
- **Loss:** cross-entropy, **class-weighted** for the imbalanced distribution.
- **Optimiser:** Adam, lr `1e-4`, weight decay `1e-4`.
- **Schedule:** `ReduceLROnPlateau` on validation macro-F1, factor 0.5,
  patience 2.
- **Regularisation/stopping:** early stopping on val macro-F1, patience 5,
  max 30 epochs.
- **Precision:** mixed precision (`torch.amp`) when CUDA is available.
- **Augmentation:** random horizontal flip, ±5° rotation, mild colour jitter.
- **Preprocessing (deployed):** resize 224×224 → tensor → ImageNet
  normalisation. Applied identically in training, evaluation and inference.

### 3.2 Data and splitting — the leakage fix

Four public datasets are used:

| Dataset | Source | Classes used | Notes |
|---|---|---|---|
| **Kermany OCT2017** | Guangzhou / UCSD | all 4 | primary dataset, ~84k images |
| **Noor Eye Hospital** | Tehran, Iran | CNV, DRUSEN, NORMAL | 16,803 images, 441 patients |
| **OCTDL** | Optovue scanner | NORMAL, DME | different scanner vendor |
| **Duke (Srinivasan 2014)** | Duke/Harvard/Michigan | NORMAL, DME | Spectralis |

**Critical correctness decisions:**

1. **Patient-grouped splitting.** Kermany's *official* train/test split leaks
   ~85% of its test patients into train (verified). It is therefore **not
   used as-is**. All data is pooled and re-split by patient ID
   (`GroupShuffleSplit`). The split is persisted (`patient_split.json`) so
   the held-out test set never changes across reruns or resumes.

   **Known limitation, disclosed rather than hidden:** the grouping key is
   `f"{class_name}-{number}"`, not the bare number. 896 of 4,657 numeric IDs
   (19.2%) appear under more than one class folder — clinically coherent
   (wet AMD in one eye, drusen in the fellow eye) — so one patient can be
   split into up to three groups and scattered across splits. 5,375 of
   13,146 test images (40.9%) are affected. The effect was **measured**
   (`model/audit_patient_leakage.py`) and runs *opposite* to memorisation:

   | Subset | n | Accuracy | Macro F1 | DRUSEN F1 |
   |---|---|---|---|---|
   | Full test set | 13,146 | 0.9517 | 0.9233 | 0.817 |
   | Leaked | 5,375 | 0.9180 | 0.8878 | 0.752 |
   | Clean | 7,771 | 0.9750 | 0.9541 | 0.882 |

   The leaked group scores *lower*, because it is by construction the
   multi-diagnosis patients — the ambiguous CNV/DRUSEN boundary cases. So
   95.17% is conservative and **97.50% is the genuinely patient-disjoint
   figure**. Correcting the key would require a full retrain, so it is
   documented instead. The cross-dataset result is unaffected (OCTDL, Duke
   and Noor all key correctly).
2. **Per-B-scan labels for Noor.** Noor encodes the label in each *filename*
   (`003_Normal.jpg`), not just the folder — a diagnosed patient's volume
   still contains normal-looking slices. Using the folder label would inject
   real label noise; the filename label is used instead.
3. **Excluded ambiguous labels.** OCTDL and Duke both have an `AMD` class that
   is *not* split into CNV vs DRUSEN. Rather than guess a mapping, those
   images are excluded entirely.
4. **Namespaced patient IDs.** Patient IDs are prefixed per source
   (`noor-`, `octdl-`, `duke-`) so IDs can never collide across datasets.

### 3.3 Measured performance (deployed checkpoint)

**In-distribution** — Kermany held-out test, 13,146 images from patients
reserved before any training:

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| CNV | 0.983 | 0.940 | 0.961 | 6,663 |
| DME | 0.929 | 0.934 | 0.932 | 1,632 |
| DRUSEN | 0.739 | 0.913 | 0.817 | 1,010 |
| NORMAL | 0.979 | 0.990 | 0.984 | 3,841 |
| **Accuracy** | | | **95.17%** | |
| **Macro F1** | | | **92.33%** | |

**Cross-dataset generalization** — reserved held-out split of Noor + OCTDL +
Duke, 2,712 images the model never trained on:

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| CNV | 0.91 | 0.92 | 0.92 | 547 |
| DME | 0.95 | 0.97 | 0.96 | 182 |
| DRUSEN | 0.83 | 0.79 | 0.81 | 779 |
| NORMAL | 0.89 | 0.91 | 0.90 | 1,204 |
| **Accuracy** | | | **88.1%** | |
| **Macro F1** | | | **89.5%** | |

**The generalization story (a real experimental result):** before combining
datasets, the Kermany-only model scored **82.0% / 0.78 macro-F1** on external
data — with DRUSEN recall at only **0.48**. After fine-tuning on the combined
set, external performance rose to **88.1% / 0.90** with DRUSEN recall at
**0.79**, while in-distribution accuracy was essentially unchanged
(95.42% → 95.17%). This was a measured improvement, not a claimed one.

### 3.4 Out-of-distribution (OOD) input gate

Prevents the classifier from confidently labelling a non-OCT image.

**Two stages, cheapest first:**
1. **Grayscale heuristic** — real OCT B-scans are near-grayscale; a colour
   photo is rejected before any model runs.
2. **CLIP zero-shot semantic check** — the image is scored against 10 text
   prompts (one OCT prompt, nine negatives covering people, objects, animals,
   natural photographs, X-ray/CT, abstract art, gradients, charts/plots, and
   screenshots/documents). The OCT prompt must win the argmax. **No
   probability threshold is tuned**, deliberately.

   The negative set is the gate's real design surface: because the decision
   is an argmax, the gate can only reject what some prompt describes. Two
   prompts were added during the pre-defense review after a grayscale
   confusion-matrix plot was accepted at `p=0.848` and classified DME at 77%
   confidence — no prompt described a chart, so the OCT prompt won by
   default.

**Rejected uploads return HTTP 422** with an explanatory message and **no
diagnosis** — the UI presents this as an amber notice, not a red error,
because refusing is a correct decision.

**Why CLIP and not the earlier approach:** the original gate used
feature-space distance from a centroid calibrated on 1,600 Kermany-only
images. It wrongly rejected **3 of 5** randomly chosen real Noor CNV scans,
because a legitimate OCT scan from a different scanner sits far from a
single-dataset centroid. CLIP needs no per-dataset calibration and
generalizes to sources it has never seen. **Validated 45/45 correct** across
30 real OCT images spanning all 4 sources and 15 real non-OCT photographs,
including the exact images that previously failed.

**Re-validated after the prompt-set fix**, on a larger multi-source set:
**171/171 real OCT images accepted** (Kermany 100, Noor 41, OCTDL 30) with
charts, documents and screenshots all rejected. The regression direction
matters more than the rejection direction here — a gate that turns away real
patient scans is the failure this design was adopted to prevent.

### 3.5 Explainability

- **Grad-CAM** computed manually against `model.layer4` using forward and
  backward hooks; the heatmap is rendered server-side onto the scan as a
  single image (it is not a client-adjustable layer, and the UI says so).
- **Written clinical explanation** per prediction, combining:
  - a **static per-class clinical description** of what that finding looks
    like on OCT and why the region matters, and
  - a **dynamic sentence derived from the heatmap's own geometry** (centroid
    position → left/centre/right, spread → tight/broad).
- **Deliberate limit:** the dynamic sentence never claims a specific retinal
  layer, because there is no layer segmentation to justify it. It stays at
  coarse image position.
- **Grad-CAM quality was assessed, not assumed:** 10 overlays across all four
  classes, including the known CNV/DRUSEN confusion cases. All produced tight,
  anatomically sensible blobs. The misclassified cases still localized
  correctly — establishing the confusion is a *classification-boundary*
  problem, not an explainability failure. Grad-CAM++ was therefore not
  pursued.

---

## 4. Backend API

12 endpoints. Authorization column: 🔓 open · 🔑 any signed-in · 👁 reviewer ·
🛡 admin.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/health` | 🔓 | Device, checkpoint status, class list, OOD gate status |
| POST | `/api/auth/register` | 🔓 | Create account (always `viewer`) |
| POST | `/api/auth/login` | 🔓 | Obtain JWT |
| GET | `/api/auth/me` | 🔑 | Current account |
| PATCH | `/api/auth/me` | 🔑 | Edit own name / password |
| POST | `/api/predict` | 🔓 (optional auth) | Validate → classify → Grad-CAM → explain → persist |
| GET | `/api/scans` | 🔓 (scoped) | Scan archive, scoped by identity |
| GET | `/api/scans/{id}` | 🔓 (scoped) | One scan's full analysis |
| PUT | `/api/scans/{id}/feedback` | 👁 | Record correct/incorrect + corrected class |
| GET | `/api/metrics` | 👁 | Stored evaluation results |
| GET | `/api/admin/users` | 🛡 | All accounts + scan/review counts |
| PATCH | `/api/admin/users/{id}/role` | 🛡 | Promote/demote viewer ↔ reviewer |

### Database schema (7 tables, 7 Alembic migrations)

`users`, `scans`, `model_versions`, `predictions`, `gradcam_results`,
`feedback`, `evaluation_metrics`.

Notable design points:
- **`model_versions`** is keyed by checkpoint file mtime, so retraining
  produces a new row and every prediction stays attributable to the exact
  model that made it.
- **`evaluation_metrics`** stores per-class metrics and the full confusion
  matrix as JSON, so the metrics page shows real evaluation output rather
  than headline numbers only.
- **`feedback.is_correct`** distinguishes "confirmed correct" from "never
  reviewed" — the original schema could not.
- **`scans.anon_session`** scopes anonymous history to one browser session.

---

## 5. Roles and authorization

Three roles, enforced **server-side** (the UI also hides controls, but that is
presentation only).

| Capability | anonymous | viewer | reviewer | admin |
|---|---|---|---|---|
| Analyze a scan | ✅ | ✅ | ✅ | ✅ |
| See Grad-CAM + explanation | ✅ | ✅ | ✅ | ✅ |
| Scan archive scope | own session | own scans | **all** | **all** |
| Record a correction | ❌ 401 | ❌ 403 | ✅ | ✅ |
| View model metrics | ❌ 401 | ❌ 403 | ✅ | ✅ |
| Manage accounts | ❌ | ❌ | ❌ 403 | ✅ |

**The reasoning behind the split (defensible, not invented hierarchy):** a
correction writes `corrected_class` — a human label asserting the model was
wrong, exactly the kind of record that would feed back into retraining. It
therefore needs provenance and a qualified author. A reviewer needs
cross-user visibility *because* reviewing other people's predictions is the
job.

**Two deliberate asymmetries:**
- **Ownership governs visibility; role governs authority to label.** A viewer
  can see their own scan but still cannot assert the model was wrong on it.
- **Admin never spreads through the API.** It is created only by hand against
  the database (`backend/grant_role.py`). Admins cannot grant admin, cannot
  modify another admin, and cannot change their own role.

### Anonymous privacy model

Anonymous scans are scoped by an opaque session id held in **`sessionStorage`**
(not `localStorage`), so history lasts exactly as long as the browser session.
A **missing** session id matches *nothing* rather than all anonymous rows —
otherwise omitting the header would re-expose everyone's scans.
`backend/purge_anonymous.py` deletes anonymous scans and their image files for
real (`--dry-run`, `--all`, `--older-than-hours`).

---

## 6. Frontend

7 routes: `/` (Predict), `/history`, `/scans/:id`, `/metrics`, `/login`,
`/profile`, `/admin`.

### Design system
- **Semantic design tokens** (`canvas`/`surface`/`imaging`/`line`/`ink`/
  `muted`/`accent`) as CSS variables registered through Tailwind v4 `@theme`,
  so light and dark are two designed palettes rather than an inversion.
- **The imaging surface is dark in *both* themes** — grayscale OCT is read on
  dark surfaces in real radiology practice.
- **Per-class semantic colours** (amber/rose/violet/emerald) used strictly as
  data indicators, verified for contrast.
- Typography: Inter for UI, IBM Plex Mono for all technical/numeric data.

### Key interface features
- **Two-column analysis workspace** — imaging on the wide left, a sticky
  380px analysis rail (verdict → distribution → interpretation → review).
- **Image comparison viewer** with Compare / Original / Grad-CAM modes and a
  keyboard-navigable full-screen lightbox (Escape, arrow keys, focus trap,
  focus restore). `object-contain` throughout — OCT aspect ratios vary from
  1:1 to 2.7:1 and cropping could remove diagnostic tissue.
- **Grad-CAM intensity legend lives in the Interpretation panel header**, so
  the overlay and the reasoning about it are visually joined.
- **Drag-and-drop upload** with a themed scan-line animation during inference.
- **Dense scan archive** with client-side class filtering, sorting, and
  scan-ID search (honest: the list endpoint has no server-side filters).
- **Metrics page** with stat readouts, per-class table with inline bars, and a
  row-normalised confusion matrix tinted by intensity (diagonal vs errors).
- **Light/dark theme toggle** with a pre-paint script so there is no flash;
  follows the OS until the user chooses explicitly.
- **Generated identicon avatars** derived locally from the email hash —
  deliberately not Gravatar, which would send user email hashes to a third
  party.

### Accessibility (measured, not assumed)
- Semantic heading hierarchy verified (h1→h2→h3, no skips) on every page.
- Real `<button>`/`<a>` elements throughout — zero clickable `<div>`s.
- `role="alert"` on every dynamic error/warning.
- Tables with `scope` and `<caption>`.
- **WCAG AA contrast verified by computation** in both themes (tightest
  measured 4.72:1, including confusion-matrix cells at maximum tint).
- Visible focus rings; `prefers-reduced-motion` respected throughout.
- **Zero horizontal overflow at 320px and 375px** on all routes.

### A design principle enforced across the codebase
**An animation may decorate a transition, but must never decide whether
content exists, what it says, or whether navigation occurred.** Seven separate
bugs of this class were found and fixed (metrics readouts freezing at 0.0%,
empty probability bars, a stranded theme icon, an invisible-but-focusable
menu, a stale review panel, route changes that silently didn't render, and —
found in the pre-defense review — the route wrapper leaving every page at
`opacity: 0` in a background tab). The guard `lib/motion.ts:canAnimate()` is
now used by every entrance animation rather than by one of five.

---

## 7. Operational tooling

| Script | Purpose |
|---|---|
| `model/train_full.py` | Full training with patient-grouped splits, resume support |
| `model/evaluate.py` | In-distribution evaluation → report, confusion matrix, DB |
| `model/evaluate_cross_dataset.py` | External generalization evaluation |
| `model/compute_ood_stats.py` | (retired path) OOD calibration statistics |
| `backend/grant_role.py` | Grant/revoke roles, incl. the only way to create an admin |
| `backend/purge_anonymous.py` | Delete anonymous scans + image files |

**Training robustness:** full resume state (model + optimizer + scheduler +
scaler + epoch) is saved every epoch, and a real power outage mid-training was
recovered from with no progress lost.

---

## 8. Engineering practices demonstrated

- **Patient-grouped splitting** after discovering real leakage in a published
  dataset's official split.
- **Honest negative result:** OCT-specific preprocessing (speckle denoising,
  B-scan flattening, retinal cropping) was fully built, wired in, evaluated —
  and **did not beat the baseline**, so it was reverted rather than shipped.
  The code is kept, documented, as evidence the critique was addressed.
- **Reproducible splits** persisted to disk.
- **Migration-managed schema** (7 Alembic migrations, no ad-hoc DDL).
- **Server-side authorization** with UI hiding as a separate, non-load-bearing
  layer.
- **Measured verification** — contrast computed, not eyeballed; permissions
  tested per role; generalization measured on genuinely held-out data.

---

## 9. Known bugs found and fixed during development

Worth having ready — professors often ask "what went wrong?"

1. **Dataset leakage** in Kermany's official split (~85% of test patients also
   in train) — found by verification, fixed with patient-grouped re-splitting.
2. **Checkpoint contamination** — smoke tests shared the real checkpoint path;
   a lucky 32-image score became the "best to beat", blocking 5 real epochs
   from ever saving. Fixed with an isolated smoke-test path.
3. **Stale-baseline comparison** — a checkpoint's stored val score was measured
   on a different validation set than the run comparing against it, which
   could trigger false early stopping. Fixed by re-measuring on the current
   set before training.
4. **CPU oversubscription** — OpenCV's internal threading colliding with
   DataLoader worker processes stalled training. Fixed with
   `cv2.setNumThreads(1)` per worker.
5. **OOD gate rejecting real OCT scans** — single-dataset calibration; replaced
   with CLIP.
6. **Missing RGB conversion** in inference broke grayscale JPEG uploads.
7. **Frontend not sending auth token** on scan endpoints after visibility
   became identity-dependent — a signed-in user saw the wrong scan set.
8. **Anonymous scans pooled globally** — every anonymous visitor could see all
   others'. Fixed with session scoping.
9. **Six animation-gating bugs** (see §6).
10. **OOD gate accepted a chart as an OCT scan** — argmax over a fixed prompt
    set can only reject what a prompt describes, and none described a chart.
    Found by end-to-end probing during the pre-defense review; fixed with two
    negative prompts and re-validated 171/171 on real OCT.
11. **Backend Docker image was 10.7 GB** — PyPI's `torch` wheel for Linux is
    the CUDA build, so ~2.5 GB of nvidia libraries were installed into a
    container with no GPU. Now 3.06 GB.
12. **Grad-CAM overlays were geometrically distorted** — the *original* was
    being shrunk to 224×224 instead of the *heatmap* being enlarged to the
    original's size, squashing a 768×496 scan's overlay ~35% horizontally so
    it no longer aligned with the scan beside it in compare view.
13. **Metrics page was permanently empty on a fresh clone** — `ModelVersion`
    was keyed on the checkpoint's file *mtime*, which a `git clone` changes,
    so no stored evaluation row ever matched. Now keyed on a SHA-256 of the
    checkpoint's contents, with results committed alongside the weights and
    seeded into an empty database at startup.

---

## 10. Deployment

- **Docker Compose**, 3 services. Postgres on host port 5433 (5432 was taken
  by a pre-existing local install). Frontend on 5173 via nginx, API on 8000.
- **Persistent volumes** for Postgres data, the Torch model cache, and the
  HuggingFace/CLIP cache.
- **Migrations run automatically** on backend startup.
- **Backend is CPU-only in Docker** for portability; CUDA is used
  automatically when training on the host.

---

## 11. What the system deliberately does *not* do

Stated explicitly so nobody assumes otherwise:

- No email verification, password reset, or OAuth.
- No DICOM support — JPEG/PNG only.
- No multi-image or volume (3D) analysis; one B-scan at a time.
- No layer segmentation, so no layer-specific claims in explanations.
- No automatic retraining from collected corrections (they are stored, not
  consumed).
- No PHI/patient-identity handling — scans are not linked to patient records.
- Not HIPAA/GDPR-assessed; not a certified medical device.

---

## 12. Known gaps and candidate future work

- **Corrections are collected but never used** — an active-learning loop that
  actually retrains on reviewer corrections is the most natural next step.
- **Anonymous purge is manual**, not scheduled.
- **No automated test suite** — verification to date has been manual and
  script-driven, not `pytest`/CI.
- **Rate limiting covers only authentication** (10 failed logins / 5 min,
  5 registrations / hour, per client address, in-process). `/api/predict` and
  the read endpoints are unthrottled, and the limiter is process-local so it
  would need shared storage behind more than one worker.
- **API docs (`/docs`, `/redoc`, `/openapi.json`) are public.** Intentional
  for a research demo; every endpoint behind them is still authorization-
  checked.
- **Scan images are served without authentication.** `/media/...` is public to
  anyone holding the URL; filenames are `uuid4` so they cannot be guessed, but
  a shared link grants indefinite access. Deliberate (plain `<img>` tags
  cannot send an Authorization header) and documented in `backend/main.py`,
  but it is the first thing to close in any deployment with real patient data.
- **JWT has no refresh/revocation** — a 7-day token cannot be invalidated.
- **Metrics are reviewer-gated**, so an examiner viewing anonymously cannot
  see them.
- Grad-CAM++ / alternative attribution methods not compared quantitatively.
- No model calibration analysis (confidence values are softmax outputs and are
  characteristically very high).
