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

## R2 — Model & ML pipeline ⬜

Training script correctness, data splitting and leakage, checkpoint handling,
evaluation scripts, reproducibility (seeds, persisted splits), the OOD gate,
Grad-CAM generation, and whether the reported numbers can actually be
regenerated from the repo.

## R3 — Backend API ⬜

Every endpoint: request validation, error handling, status codes, response
shapes, DB session handling, migration chain integrity, and whether the ORM
models match the migrations and the live schema.

## R4 — Frontend ⬜

Build integrity, routes, component structure, state management, API
integration, loading/error/empty states, and dead code.

## R5 — Security & privacy ⬜

Full authorization matrix re-verified end to end, secret handling, CORS,
password storage, JWT handling, input validation, file-upload safety, and
data exposure (including the anonymous-session boundary).

## R6 — Accessibility & responsive ⬜

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
