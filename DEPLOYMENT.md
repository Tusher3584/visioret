# Visioret — Free Deployment Guide

Getting Visioret running on a public URL, for free, so it can be demonstrated
from any machine with a browser.

> **Status: not started.** Steps 1–3 and 7–16 are ready to follow. Steps 4–6
> are code changes that have **not been made yet** — the app currently runs as
> three containers (nginx + FastAPI + Postgres) via `docker-compose.yml`, which
> is not the shape that gets deployed. Do not start at Step 7 until Phase 1 is
> done.

---

## Why this setup

| Piece | Where | Why |
|---|---|---|
| Backend + model + frontend | **Hugging Face Space** (Docker, free CPU) | The free CPU tier is sized for ML demos. The backend peaks at ~686 MB RAM with a ~3 GB image — that does not fit Render/Fly/Vercel free tiers, and Vercel's serverless functions cap far below what PyTorch needs |
| Database | **Neon** (free Postgres) | Space storage is ephemeral. Without an external database, every account, scan and review is lost on restart |

**Everything is served from one Space, one URL, one origin.** That is
deliberate: same-origin removes the CORS configuration, the CSP
`connect-src` problem, and the build-time `VITE_API_BASE_URL` problem in one
move. For a live demo, fewer moving parts matters more than architectural
separation.

---

## Phase 0 — Accounts (~10 minutes, only you can do this)

- [ ] **Step 1 — Hugging Face account.** Sign up at
      <https://huggingface.co>. Choose the username carefully: it becomes part
      of your public URL, e.g. `rifat-visioret.hf.space`.

- [ ] **Step 2 — Neon account and database.** Sign up at
      <https://neon.tech>, create a project named `visioret`, and copy the
      connection string. It looks like:

      postgresql://user:password@ep-something.neon.tech/neondb

      Save it somewhere safe — you paste it in Step 9. If it does not already
      end with `?sslmode=require`, add that.

- [ ] **Step 3 — Install Git LFS.**

      git lfs install

      This is not optional. `model/checkpoints/resnet50_oct.pth` is 94 MB, and
      Hugging Face rejects any file over 10 MB that is not tracked by LFS.
      Skipping this makes Step 8 fail with a confusing push error.

---

## Phase 1 — Code changes (not yet done)

These convert the project from "three containers on your machine" to "one
container on a Space". They are implementation work, not something to follow
by hand.

- [ ] **Step 4 — FastAPI serves the frontend.** Mount the built React app as
      static files with an SPA fallback so client-side routes (`/history`,
      `/scans/5`) resolve. The frontend switches to relative `/api/...` calls.

- [ ] **Step 5 — One merged Dockerfile.** Multi-stage: Node builds the
      frontend, the Python image copies `dist/` in. Listens on **port 7860**
      (what Spaces expect). **CLIP weights are downloaded during the build**
      and baked into an image layer — this is what stops a cold start from
      taking a minute in front of the panel.

- [ ] **Step 6 — Verify locally.** Run that single container on this machine
      and re-test the whole flow: upload, Grad-CAM, non-OCT rejection, login,
      roles, metrics, review. Find problems here, not live.

---

## Phase 2 — Deploy to Hugging Face

- [ ] **Step 7 — Create the Space.** On Hugging Face: **New Space** →
      name `visioret` → SDK **Docker** → hardware **CPU basic (free)** →
      visibility **Public**.

- [ ] **Step 8 — Push the code.** The Space is a git repository. Add it as a
      remote and push. Exact commands will be provided once Phase 1 is done,
      because the LFS tracking has to be set up in the same step.

- [ ] **Step 9 — Add secrets.** In the Space: **Settings → Variables and
      secrets → New secret**. Add exactly two:

      | Name | Value |
      |---|---|
      | `DATABASE_URL` | the Neon connection string from Step 2 |
      | `JWT_SECRET_KEY` | a fresh 64-character random hex value |

      Generate the key with:

      python -c "import secrets; print(secrets.token_hex(32))"

      Never commit either value. The app refuses to start without
      `JWT_SECRET_KEY`, which is intentional.

- [ ] **Step 10 — Wait for the build.** It starts automatically. **Expect
      15–25 minutes the first time** — it is installing PyTorch. Watch the
      build log in the Space UI. Later pushes are much faster because Docker
      layers cache.

---

## Phase 3 — Bring it to life

- [ ] **Step 11 — Open your Space URL.** On first boot the backend runs all 7
      database migrations against Neon automatically and seeds the published
      evaluation metrics from the committed file. You should land on the
      Predict page.

- [ ] **Step 12 — Register your account** through the UI. Use a **real-looking
      email domain**. Addresses on `.test`, `.local` or `localhost` are
      correctly rejected as reserved domains and will return a validation
      error.

- [ ] **Step 13 — Make yourself admin.** Open Neon's web **SQL Editor** and
      run:

      UPDATE users SET role = 'admin' WHERE email = 'your@email.com';

      This is the *only* way to become an admin — no API endpoint can grant
      it, by design. That is worth mentioning if a panel asks how
      administrative privilege is bootstrapped.

- [ ] **Step 14 — Verify live.** Walk the demo you intend to give:
      - upload a real OCT scan → prediction, Grad-CAM overlay, interpretation
      - upload a non-OCT image → rejected, **no diagnosis shown**
      - open History → the scan is listed
      - open Metrics → both result tables and confusion matrices
      - open a scan and record a review → attribution and timestamp appear

---

## Phase 4 — Before the defense

- [ ] **Step 15 — Record a backup video.** A 2–3 minute screen capture of the
      full flow above, kept on your phone and on a USB stick. The demo depends
      on the venue's network; this is the fallback if it fails.

- [ ] **Step 16 — Wake the Space 5–10 minutes early.** Free Spaces sleep when
      idle. One visit wakes it, so the panel never watches it boot.

---

## Troubleshooting

**Push rejected, "file too large" or an LFS error.** Step 3 was skipped, or
the `.pth` was committed before LFS tracking was set up.

**Build fails on `pip install`.** Almost always a timeout pulling PyTorch.
Re-trigger the build; the cached layers make the retry much shorter.

**Space starts, but every page is blank or shows an API error.** Check the
Space logs. Most likely `DATABASE_URL` is missing, wrong, or lacks
`?sslmode=require`.

**"Application startup failed" mentioning JWT.** `JWT_SECRET_KEY` was not set
in Step 9.

**Metrics page is empty for a reviewer account.** The seed step did not run.
Confirm `model/checkpoints/evaluation_metrics.json` was pushed, and look for
`Seeded 2 evaluation metric row(s)` in the Space logs.

**Login says "Too many attempts."** The rate limiter (10 failed logins per 5
minutes) is working. Wait it out, or restart the Space — its state is
in-process.

**First request after idle takes ~30–60s.** Expected: the Space is waking.
This is what Step 16 avoids.

---

## Two things to decide knowingly

**Uploaded scan images are served without authentication.** Filenames are
random UUIDs so they cannot be guessed, but anyone holding a link can view
that image indefinitely. For a controlled demo this is fine; it is documented
in `backend/main.py` and listed in `FEATURES.md`. It is a deliberate
trade-off, not an oversight — but on a public URL it should be a decision you
have actually made.

**The rate limiter resets whenever the Space restarts**, because it keeps
state in the process. Login throttling is therefore weaker in practice than
the configured numbers suggest.

---

## Timing

Roughly an afternoon in total, most of it waiting on Step 10.

**Do this at least a week before the defense, then leave it alone.** Free-tier
terms change, and this document cannot verify today's Hugging Face and Neon
limits — check them as you sign up.
