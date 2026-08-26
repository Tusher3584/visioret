# Visioret — Post-Phase-E Checkpoint List

Working list of everything identified as missing or needing improvement after
the first full build (model → backend → database → frontend → Docker
integration). Tackled one checkpoint at a time, in order, not as one big
attempt. Check items off as they land; add a one-line note on what changed
when you do.

Priority order below is a recommendation, not fixed — confirm/reorder before
each checkpoint starts.

---

## Checkpoint 1 — Input validation / out-of-distribution detection 🔴 safety-critical ✅ DONE

The model currently has no way to say "I don't know" — any image, including a
non-OCT photo, gets forced into one of the 4 disease classes with high
confidence. Fix before anything else.

- [x] Collect/prepare a set of non-OCT negative images (natural photos, other
      medical imaging types) to train/validate the detector against — pivoted
      to a feature-space anomaly-detection approach instead (see note below),
      which needs no negative training images at all
- [x] Build a lightweight OOD ("is this actually an OCT scan?") detector —
      3-stage gate: color heuristic → brightness heuristic (both calibrated
      from real OCT training data) → feature-space distance in the trained
      disease model's own embedding space (reuses the already-loaded model,
      no extra network). `model/ood_detector.py` + `model/compute_ood_stats.py`
- [x] Integrate as a gate in the backend `/api/predict` pipeline: reject
      non-OCT uploads before running the 4-class model (HTTP 422). Also added
      to the Streamlit demo (`app.py`) for consistency.
- [x] Frontend: clear rejection message instead of a fake diagnosis — shown
      as a distinct amber notice (not a red error), since it's a valid
      decision, not a system failure
- [x] Test against real non-OCT images (e.g. the full-body photo case) and
      confirm correct rejection, plus confirm real OCT scans still pass
      through — verified via the actual running Docker stack: real OCT
      samples → normal predictions (200), a real downloaded photo → correctly
      rejected (422) with no diagnosis produced

**Note on approach change:** originally planned to train a binary classifier
against a downloaded negative-image set (CIFAR-10), but that mirror was
extremely slow (~15 min for <5% of the download). Pivoted to distance-based
OOD detection in the trained model's feature space instead — needs zero
negative training data, no extra model/training run, and is a legitimate,
well-established OOD technique in its own right (not just a workaround).

**Update 2026-08-23 — the distance-based stage above had a real bug, found
by the user testing real Noor Eye Hospital CNV images: 3 of 5 random ones
were wrongly rejected as "not OCT."** Root cause confirmed with hard
evidence: the feature-distance threshold was calibrated on 1,600
Kermany-only images (`compute_ood_stats.py`), so any genuinely valid OCT
scan from a different source/scanner could sit far enough from that
narrow centroid to get rejected — exactly the generalization gap
Checkpoint 5 was supposed to have addressed, except the OOD gate was never
recalibrated alongside the classifier. **Fixed by replacing the
feature-distance stage with a CLIP zero-shot semantic check**
(`model/clip_ood.py`) — "does this look like an OCT scan" per CLIP's
general visual understanding, which needs no per-dataset calibration at
all and generalizes to sources it's never seen. Validated: 45/45 correct
across 30 real OCT images spanning all 4 sources + 15 real non-OCT photos,
including the exact 2 Noor images that were failing before, both fixed.
Re-verified end-to-end through the live API: 10/10 additional random Noor
CNV images now accepted, a real non-OCT photo still correctly rejected
(422). The old feature-distance code is left in `model/ood_detector.py`
for reference (documented as retired, not deleted) since it's a legitimate
technique that just didn't hold up in practice against multi-source data.
Grayscale heuristic kept as a cheap pre-filter before CLIP runs.

## Checkpoint 2 — OCT-specific preprocessing pipeline 🔴 scientific rigor ✅ DONE (negative result, documented)

Addresses the "this pipeline isn't exclusive to OCT" critique. Generic
resize+normalize works for any image; these steps are OCT-domain-specific.

- [x] Speckle-noise reduction (`cv2.fastNlMeansDenoising`) — OCT's
      characteristic interferometry noise
- [x] Retinal region cropping (isolate retina from black background)
- [x] B-scan flattening (curve detection + column-wise shift to correct
      eye-curvature tilt) — standard step in real OCT analysis pipelines.
      All three implemented in `model/oct_preprocessing.py`, validated
      visually and against 80 real sample images with zero errors.
- [x] Wired into both training and inference, then evaluated end-to-end
- [x] Retrain and re-evaluate on the held-out test set; compare against the
      95.5%/92.8% macro-F1 baseline

**Result: did not help — reverted, not used in the deployed pipeline.**
A clean (uncontaminated) 5-epoch fine-tune warm-started from the baseline
checkpoint peaked at val_macro_f1=0.9184 (epoch 1) and degraded from there;
none of the 5 epochs beat the baseline's 0.9389. Most likely cause: the
baseline's layer3/4/fc weights were tuned on raw-pixel statistics, and
denoise/flatten/crop shift the input distribution enough that the
warm-started weights need more than 5 epochs to re-adapt — not evidence
the preprocessing itself is harmful, just unproven within this budget.
Decision (deliberate, not a default): keep `model/oct_preprocessing.py` as
tested, documented, working code (answers the "not OCT-specific" critique
honestly — "we built and evaluated this, here's the evidence"), but do NOT
wire it into the deployed model, since doing so without proof it helps
would just be complexity for its own sake. `train_full.py`/`evaluate.py`/
`model/inference.py` all reverted to plain resize+normalize, consistently.
Revisit if Checkpoint 5's fuller retrain (fresh init, more patience) has
room to test this properly instead of a patience-limited warm-start.

**Two real bugs found and fixed along the way** (see git history around
2026-08-20/21): (1) CPU oversubscription from `cv2`'s internal
multithreading colliding with DataLoader worker processes, stalling
training — fixed with `cv2.setNumThreads(1)` per worker
(`limit_worker_cv2_threads`, kept — a real fix independent of whether
`preprocess_oct` is used). (2) A checkpoint-contamination bug where
`--smoke-test` runs shared `CHECKPOINT_PATH` with real runs: a lucky
32-image smoke-test score (0.9389, coincidentally equal to the real
baseline) got treated as the real run's baseline, so 5 real epochs of
genuine progress could never register as "improvement," falsely triggering
early stopping and blocking the checkpoint save. Fixed by giving
`--smoke-test` a fully isolated `SMOKE_TEST_CHECKPOINT_PATH` that never
touches the real one.

## Checkpoint 3 — Grad-CAM accuracy ✅ DONE (assessed, no change needed)

- [x] Assess current Grad-CAM localization quality on the deployed model —
      inspected 10 overlays across all 4 classes (correct predictions +
      the CNV/DRUSEN confusion cases). Every one produced a tight, single,
      anatomically sensible blob: on the visible lesion for CNV/DME/DRUSEN,
      on the fovea for NORMAL. No diffuse or off-target heatmaps found.
- [x] Consider a sharper variant (e.g. Grad-CAM++) — not pursued. Grad-CAM++
      mainly helps when a class has multiple scattered instances causing
      diffuse attention; that's not the failure mode observed here (see
      script below).
- [x] Re-verify against the CNV/DRUSEN confusion pattern (220 CNV images
      misclassified as DRUSEN in the current baseline's confusion matrix) —
      **result: not a localization problem.** The misclassified cases still
      show a tight heatmap centered exactly on the lesion; the model is
      looking at the right place and still calling it wrong. These are
      genuinely small, ambiguous bumps between "small CNV" and "drusen
      deposit" — a real classification-boundary issue, not an explainability
      defect. A sharper CAM method wouldn't fix a decision the model already
      attended to correctly.

Sample generation script (for reference / rerunning against a future
retrained model): see conversation history around 2026-08-21; not committed
to the repo since it's an ad hoc diagnostic, not part of the shipped app.

## Checkpoint 4 — Grad-CAM "why" explanation section ✅ DONE

- [x] Per-class clinical explanation content (`model/explanations.py`,
      `CLINICAL_EXPLANATIONS`) — what CNV/DME/DRUSEN/NORMAL findings
      typically look like on OCT and why the model attends to that region.
- [x] Static clinical template + a simple dynamic sentence computed from the
      Grad-CAM heatmap's own geometry (centroid position -> left/center/
      right, spread -> tight/broad). Deliberately does NOT claim specific
      retinal layers -- no segmentation to back that up, so it stays at the
      level of coarse image position, which is honest given what we
      actually compute (`describe_heatmap_location`).
- [x] Added to backend: `PredictionResponse.explanation` /
      `ScanDetail.explanation`, persisted via a new `gradcam_results.
      explanation` column (Alembic migration `f4d872cf777a`).
- [x] Added to frontend: new "Why this region?" panel in `ScanResult.tsx`,
      wired through both the fresh-predict flow and the history detail view.
- [x] Also added to the Streamlit demo (`app.py`) for consistency.
- [x] Verified end-to-end against the running Docker stack for all 4
      classes (direct API calls + rendered history detail page).

**Bug found and fixed along the way:** reverting Checkpoint 2's
`preprocess_oct` wiring (see Checkpoint 2 note) also silently removed the
only place that guaranteed RGB input -- `preprocess_oct` used to convert
internally, so `model/inference.py`'s `preprocess_image` never had its own
`.convert("RGB")` call. Grayscale-mode OCT JPEGs (common; confirmed via the
bundled samples) then produced a 1-channel tensor and crashed at
`Normalize`. Training was never affected (`model/dataset.py`'s
`OCTDataset` already converts to RGB on load, independent of the
transform pipeline) -- this was inference-only, and was masked the whole
time `preprocess_oct` was in place. Fixed by adding the same
`.convert("RGB")` call directly in `preprocess_image`.

## Checkpoint 5 — Additional data sources / generalization ✅ DONE

- [x] Identify appropriate additional public OCT datasets beyond Kermany
      OCT2017 (different scanners/populations) — downloaded and extracted to
      `G:\Download\archive\`: **Noor Eye Hospital** (Tehran, Iran;
      `NoorEyeHospital\extracted\NEH_UT_2021RetinalOCTDataset\{CNV,DRUSEN,
      NORMAL}\<patient>\...` — ground truth is the **per-B-scan filename
      suffix**, e.g. `003_Normal.jpg`, NOT the folder name, since a
      diagnosed patient's volume can still contain normal-looking slices),
      **OCTDL** (`OCTDL\extracted\OCTDL\{NO,DME}\...`, different scanner
      vendor -- Optovue vs Kermany's Heidelberg Spectralis; its `AMD` class
      is excluded, not split into CNV/DRUSEN), **Duke Srinivasan 2014**
      (`DukeSrinivasan2014\extracted\Publication_Dataset\{DME,NORMAL}<n>\
      TIFFs\8bitTIFFs\...`, per-volume folders; `AMD<n>` excluded, same
      reason).
- [x] Cross-dataset generalization eval done with ZERO retraining
      (`model/evaluate_cross_dataset.py`, results in
      `model/checkpoints/cross_dataset_evaluation_report.txt` +
      `cross_dataset_confusion_matrix.png`): **82.0% accuracy / 0.78
      macro-F1** across 19,790 external images, vs. 95.4%/0.926 in-
      distribution. Confirms a real generalization gap, and it lines up
      with Checkpoint 3's finding: of 4,992 true external DRUSEN images,
      only 48% were called DRUSEN (841 -> CNV, 1,739 -> NORMAL) -- same
      CNV/DRUSEN boundary ambiguity, worse externally. DME also leaks into
      NORMAL (346/1,248).
- [ ] **NEXT STEP (not started): fine-tune on the combined dataset.** User
      approved retraining given this result ("yes go ahead and retrain if
      needed", then "we will do it later" -- deferred, not cancelled).
      Plan agreed: (1) reserve a held-out, patient/volume-grouped test
      split from each external dataset, kept out of training, so we can
      measure genuine post-finetune generalization improvement rather than
      memorization; (2) extend `model/dataset.py`'s sample collection to
      ingest all 4 sources into unified (filepath, class, patient_id)
      tuples -- patient ids must be dataset-prefixed so they can never
      collide across sources; (3) fine-tune warm-started from the current
      baseline checkpoint via the existing `train_full.py` infra; (4)
      re-evaluate on both the original Kermany test set and the new
      held-out external test split. Expected wall-clock: ~5-8 hours (more
      training data than Checkpoint 2's retrain, which took ~5 hours for
      5 epochs before patience stopped it).
- [x] Fine-tuning run completed 2026-08-22/23 (survived one power outage via
      `--resume`, resumed exactly at epoch 3 with no progress lost). Found
      and fixed a real measurement bug first: the checkpoint's stored
      val_macro_f1 (0.9389) was measured on the old Kermany-only val set,
      but this run validates on a combined (Kermany + external) val set --
      comparing epoch scores against that stale, easier-val-set number
      would be apples-to-oranges and could trigger false early stopping.
      Fixed in `train_full.py` by measuring the warm-started weights fresh
      on the new val set before training starts, and using THAT as the
      "best to beat" baseline (came out to 0.8964 -- confirmed the fix
      mattered, since epoch 1's real result of 0.9215 beats 0.8964 but not
      the stale 0.9389). Final result: best val_macro_f1 = 0.9215 (epoch 1),
      early-stopped after epoch 6 (patience=5), checkpoint saved correctly.
- [x] Evaluated both ways -- **a genuine, substantial win, not a tradeoff**:
      - In-distribution (Kermany held-out test, 13,146 images): 95.17%
        accuracy / 0.923 macro-F1 -- essentially unchanged from the
        pre-finetune baseline (95.42%/0.926), so no regression.
      - Cross-dataset (reserved external test split, 2,712 images never
        seen during training): **88.0% accuracy / 0.90 macro-F1**, up from
        82.0%/0.78 before fine-tuning. DRUSEN recall nearly doubled (0.48
        -> 0.79) -- directly closes the CNV/DRUSEN generalization failure
        found in the pre-finetune cross-dataset check and traced back to
        Checkpoint 3's CNV/DRUSEN boundary-ambiguity finding. DME F1 0.77
        -> 0.96. Full breakdown in `cross_dataset_evaluation_report.txt`.
      - Conclusion: Checkpoint 5 achieved its goal. Combining Noor Eye
        Hospital + OCTDL (partial) + Duke (partial) with Kermany OCT2017
        and fine-tuning measurably improved real generalization to unseen
        institutions/scanners, without costing in-distribution accuracy.

## Checkpoint 6 — UI redesign ✅ DONE

Current frontend is functionally correct but visually generic
(default-Tailwind look, no real design pass). Needs to look like a
considered product for a final-year defense, not a scaffold.

- [x] Real design pass: Inter (UI text) + IBM Plex Mono (confidence
      numbers, scan IDs, model version -- reinforces a precision-instrument
      feel) via Google Fonts; brand color moved from generic teal to a
      considered blue; a semantic per-class color system (amber=CNV,
      rose=DME, violet=DRUSEN, emerald=NORMAL) shared via
      `frontend/src/lib/classColors.ts` and applied consistently to the
      prediction badge, probability bars, and history-list color dots, so
      the same class always reads as the same color everywhere. Cards
      moved from flat borders to subtle elevation (rounded-xl + shadow-sm).
- [x] Applied consistently across Predict (`UploadPredict.tsx`), History
      (`ScanHistory.tsx`), and Detail (`ScanDetail.tsx` / `ScanResult.tsx`)
      views, plus `Nav.tsx` (new logo mark, refined status badge) and
      `App.tsx` (shell background).
- [x] Verified against the live Docker stack with real predictions across
      all 4 classes: computed styles confirmed each class renders its
      correct distinct color (amber/emerald/violet/rose) in both the badge
      text and probability bars, dark-mode variants correct, all images
      (original + Grad-CAM overlay) loading correctly.

**Bug found and fixed along the way:** verifying against live predictions,
the OOD gate rejected a real CNV sample as "not OCT" (422). Root cause:
`ood_stats.pth` was still calibrated against the pre-Checkpoint-5
checkpoint's feature space; fine-tuning shifted the model's embeddings
enough that the old distance thresholds no longer fit. Recalibrated via
`model/compute_ood_stats.py` and confirmed fixed. This should be done
after every retrain going forward -- the OOD detector is tied to the
specific checkpoint's feature space, not just an independent module.

**Round 2 (2026-08-23) — user feedback: still looked too plain/static for
a 4th-year defense.** Added a real animation layer (`framer-motion`):
route-change fade transitions (`App.tsx`), a sliding pill nav indicator
using `layoutId` (`Nav.tsx`), staggered entrance reveals on
`ScanResult.tsx`/`ScanHistory.tsx`, animated probability-bar fill-in and
count-up numbers (new `AnimatedNumber.tsx`, used for confidence % and the
metrics stat tiles), hover/tap micro-interactions on buttons and cards,
and a themed scan-line sweep animation over the preview image during
inference (reinforces the OCT-scanning concept rather than a generic
spinner). Also added an ambient drifting-gradient background to the shell
for visual depth. Tried the newer unified `motion` package first; when its
declarative `initial`/`animate` props appeared frozen during testing,
traced it to `document.hidden` being `true` in this session's Browser pane
(confirmed via `document.visibilityState`) -- Framer Motion's engine
intentionally pauses its rAF-driven animations on hidden/backgrounded
tabs, which is exactly this pane's persistent state all session (matches
every earlier "Browser pane is not displayed" screenshot failure). Not a
code bug; switched to the `framer-motion` package anyway (same maintainer,
more battle-tested history) since the two behaved identically and there
was no reason not to. **Could not get final visual (screenshot)
confirmation in this session for that same reason -- user should verify
the live animations directly at localhost:5173.**

**Round 3 (2026-08-25/26) — full structural redesign.** Round 2 was
correctly rejected: it kept the same information architecture and only
added motion. This round replaced the architecture itself, driven by a
written brief (`UI_REDESIGN_BRIEF.md`).

Core move: the 768px centred card-stack became a **two-column analysis
workspace** at `max-w-[1600px]` -- imaging holds the wide left column, a
380px sticky rail on the right carries verdict -> distribution ->
interpretation -> review. Below `xl` the rail drops underneath in the same
order. Scan images went from ~350px to 390x260 side by side, with
Compare / Original / Grad-CAM view modes and a full-screen lightbox.

Design system: semantic tokens (`canvas`/`surface`/`imaging`/`line`/`ink`/
`muted`/`accent`) as CSS variables registered through Tailwind v4 `@theme`,
so light and dark are two designed palettes rather than an inversion. The
`imaging` surface stays dark in **both** modes -- grayscale OCT is read on
dark surfaces in real radiology practice. Panels use thin borders and 3px
radius with no drop shadows; accent moved off generic blue to a technical
cyan; class colours are now used strictly as data indicators.

Structure: 5 pages + 18 components + 2 lib modules, replacing 10 flat
components. `ScanAnalysis` is shared verbatim by Predict and Scan Detail,
so there is exactly one implementation of "what a result looks like".
Notable pieces: real drag-and-drop `UploadWorkspace` (no raw file input),
the Grad-CAM intensity legend moved *into* the Interpretation panel header
so overlay and reasoning are tied together, a dense `ScanArchive` table
with client-side class filter / sort / scan-ID search, and a
row-normalised confusion matrix tinted so correct-vs-error structure reads
before any number does.

**Four real bugs found and fixed during verification:**
1. `HealthResponse` in `api/types.ts` was missing `ood_gate_active` -- the
   type had drifted from what the backend actually returns.
2. The new header was a single flex row and overflowed horizontally below
   ~360px (the old one stacked on mobile; mine didn't). Rewritten to wrap
   the nav onto a full-width tab strip. Verified clean at 320px and 375px.
3. The image lightbox restored focus to `<body>` instead of the trigger,
   and had no Tab trap. Both fixed -- trigger now focuses itself on click,
   and Tab cycles within the dialog.
4. **Most serious:** `AnimatedNumber` and the probability bars animate
   *from* zero via requestAnimationFrame, which browsers throttle in a
   hidden/background tab -- so the metrics page could display **0.0%** when
   the true value was 95.2%, and bars could sit empty. That is
   misinformation, not a missing animation. Added `lib/motion.ts`
   (`canAnimate`) so both render the true value immediately whenever the
   animation cannot be trusted to run, plus a `visibilitychange` guard that
   snaps an in-flight count-up to the real figure. Verified: correct values
   now render even with `document.hidden === true`.

**Verified against the deployed nginx build** (not the dev server):
two-column workspace at 821px+380px, images loading, zero horizontal
overflow on all five routes at 375px and 320px, clean h1->h2->h3 outline
everywhere, WCAG AA contrast in both modes (tightest 4.72, including
confusion-matrix cells at maximum tint), visible focus rings, lightbox
keyboard flow (Escape / arrows / Tab trap / focus restore), reduced-motion
CSS and `useReducedMotion` wired in every animated component, archive
filtering, and light mode. Wide tables scroll inside their own containers
rather than breaking the page.

**Theme switch (2026-08-26).** Added a manual light/dark toggle -- the app
previously followed `prefers-color-scheme` with no way to override it.

Theming moved off the media query onto a `data-theme` attribute on `<html>`,
with Tailwind's `dark:` variant repointed at the same attribute
(`@custom-variant dark`) so utility classes and the token palette can never
disagree about which theme is active. An inline script in `index.html`
resolves and applies the theme before first paint, so there is no flash of
the wrong palette on load. A first-time visitor still gets their OS
preference and keeps following it live; the first click stores an explicit
choice which then wins (`ThemeContext.tsx`).

The control is a 32px circular button showing the theme you would get by
clicking -- sun in dark mode, moon in light -- counter-rotating through each
other so the swap reads as one turn of a dial.

**Bug found and fixed while building it, the third of its kind:** the first
version used `AnimatePresence mode="wait"`, which *gates* the incoming icon
on the outgoing one's exit animation completing. Since requestAnimationFrame
is throttled in background tabs, that exit can never finish and the button
gets stranded showing the wrong symbol -- verified happening. Rewritten so
both icons stay mounted and their resting state is plain CSS classes with a
CSS transition: which icon shows is *information*, so it has to be correct
even when no animation ever runs. Framer is left to the tap/hover flourish,
where being skipped costs nothing. This is the same principle already
applied to `AnimatedNumber` and the probability bars -- an animation must
never decide whether content exists or what it says.

Verified live: initial state follows the OS, clicking flips theme + palette +
`color-scheme` + aria-label + icon, the choice persists across reload via the
pre-paint script, and both directions round-trip correctly.

## Checkpoint 7 — Evaluation metrics integrated into the app ✅ DONE

- [x] Extended `EvaluationMetric` (migration `263d6fc8f6f4`) with
      `per_class_metrics` and `confusion_matrix` JSON columns +
      `evaluated_at`, beyond the original macro-only columns -- needed for
      a genuinely useful view, not just a headline number.
- [x] `model/evaluate.py` and `model/evaluate_cross_dataset.py` now write
      their results into the DB (via the new best-effort
      `backend/db/write_evaluation.py` -- never raises, so the scripts
      still work standalone / print / save `.txt`+`.png` even if Postgres
      isn't reachable) under `dataset_split="kermany_test"` and
      `"external_test"` respectively. Extracted `get_or_create_model_version`
      out of `backend/main.py` into `backend/db/model_version.py` so both
      the API and the eval scripts share it without `model/` importing the
      FastAPI app.
- [x] New `GET /api/metrics` endpoint, returns one entry per evaluated
      dataset split for the currently deployed model version.
- [x] New frontend `/metrics` page (`ModelMetrics.tsx` + nav link):
      headline accuracy/precision/recall/F1 stat tiles, a per-class table
      with the same class-color dots as the rest of the app, and a
      confusion matrix rendered as a real table with intensity-tinted
      cells (blue = correct/diagonal, rose = errors, both scaled by count).
      Verified against the live Docker stack with real data from both
      dataset splits.

## Checkpoint 8 — Feedback / correction workflow ✅ DONE

- [x] Extended `Feedback` (migration `53b8feed0825`) with an `is_correct`
      boolean -- the original schema only had `corrected_class` (nullable),
      which couldn't distinguish "confirmed correct" from "never reviewed."
      `PUT /api/scans/{scan_id}/feedback` upserts against the scan's latest
      prediction (one review per prediction, resubmitting replaces it);
      validates `corrected_class` is provided and is one of the deployed
      model's classes when `is_correct=false`.
- [x] Frontend: `FeedbackForm.tsx`, wired into `ScanResult.tsx` so it shows
      on both the fresh-predict flow and the scan history detail view.
      Correct/Incorrect buttons, a class dropdown + optional comment for
      corrections, and an existing-review state with a "change my review"
      edit path. Verified end-to-end against the live Docker stack: submit
      correct, submit incorrect with a correction + comment, validation
      error on a missing correction, resubmit-overwrites behavior, and the
      edit/cancel UI flow.

## Checkpoint 9 — User accounts ✅ DONE

Scope decision: real minimal auth -- bcrypt-hashed passwords + JWT, no
email verification/password reset/OAuth. Login is optional throughout;
predicting and giving feedback both still work anonymously (`user_id`/
`reviewed_by` stay NULL), matching this being a demo/research tool rather
than a gated clinical system.

- [x] Backend: `backend/auth.py` (bcrypt hashing, JWT create/decode,
      `get_current_user` / `get_current_user_optional` FastAPI
      dependencies). New `users.password_hash` column (migration
      `e96f48ad79fb`). `POST /api/auth/register`, `POST /api/auth/login`,
      `GET /api/auth/me`. `JWT_SECRET_KEY` from environment (`.env` for
      host, `docker-compose.yml` for the container) -- deliberately no
      hardcoded fallback in code, so a missing key fails loudly rather than
      silently signing tokens with a guessable default.
- [x] `/api/predict` and `PUT /api/scans/{id}/feedback` now accept an
      optional bearer token and attach `scan.user_id` / `feedback.
      reviewed_by` when present.
- [x] Frontend: `AuthContext.tsx` (token in localStorage, fetches `/me` on
      load), `AuthPage.tsx` (combined login/register form at `/login`),
      `Nav.tsx` shows "Log in" or "{name} · Log out".
- [x] Verified end-to-end against the live Docker stack: register, duplicate-
      email rejection, wrong-password rejection, login, `/me` with/without
      token, authenticated predict correctly sets `scan.user_id`,
      authenticated feedback correctly sets `feedback.reviewed_by`, logout
      clears the token and reverts the nav.

**Round 2 (2026-08-26) -- signing in was doing nothing.** User asked what
privileges login actually granted, and the honest answer was: none. Audit
confirmed `get_current_user` (the 401-ing dependency) guarded exactly one
endpoint -- `/api/auth/me`, which only reports whether you are logged in.
Everything else was open or optional-auth. `/api/scans` returned every
user's scans with no filtering, `/api/scans/{id}` had no ownership check,
and `role` was stored, defaulted, returned in responses, and **never
compared against anything anywhere**. Login wrote two foreign keys that
nothing read back. That is authentication with no authorization.

Replaced the placeholder `researcher` role with two roles that are
enforced (migration `b2abbe5bc236`; existing accounts migrated to
`reviewer` so nobody lost access they already had):

| | `viewer` (default) | `reviewer` | anonymous |
|---|---|---|---|
| Analyze a scan | yes | yes | yes |
| Sees in archive | own scans | **all** scans | anonymous scans |
| Open scan by URL | own only (404 otherwise) | any | anonymous only |
| Record a correction | **no** (403) | yes | no (401) |
| View model metrics | **no** (403) | yes | no (401) |

The split is grounded in what the data means, not an invented org chart:
a correction writes `feedback.corrected_class`, a human label asserting the
model was wrong, which is exactly what would feed back into retraining --
so it needs provenance and a qualified author. A reviewer needs
cross-user visibility precisely *because* reviewing other people's
predictions is the job. Note the deliberate asymmetry: ownership governs
**visibility**, role governs **authority to label**, so a viewer can see
their own scan but still cannot assert the model was wrong on it.

Roles are **not self-assignable** -- registration always creates a viewer.
Promotion is an out-of-band admin action via the new
`backend/grant_role.py` (`--list`, or `EMAIL ROLE`), the way real systems
bootstrap privileged accounts. Enforcement is server-side
(`require_reviewer` in `backend/auth.py`); the frontend also hides these
affordances but that is presentation only.

Attribution is now actually visible: `owner_name` on scan summaries and
detail, `reviewer_name` on feedback, the role shown beside the user's name
in the header, a "Submitted by" column that appears only for reviewers,
and the archive description stating whose scans you are looking at.

**Bug found and fixed during verification:** `listScans`, `getScan` and
`fetchMetrics` in `api/client.ts` never sent the auth token -- they had not
needed it while everything was public. After scoping visibility by
identity, the frontend was still calling them anonymously, so a signed-in
viewer saw the 34 anonymous scans instead of their own 1. Caught because
the API returned 1 while the DOM rendered 34. Fixed by adding
`authHeaders()` to all three.

Verified live for all three states (anonymous / viewer / reviewer):
metrics 401/403/200, corrections 401/403/200, archive counts 34/1/37,
direct-URL access to a non-owned scan 404s for a viewer and 200s for a
reviewer, a viewer gets 403 correcting even their own scan, the Metrics
nav link is hidden for non-reviewers, the review panel explains why it is
locked rather than silently hiding, and the "Submitted by" column appears
only for reviewers.

## Checkpoint 10 — Accessibility pass ✅ DONE (incl. mobile)

- [x] Semantic HTML / ARIA review across every component. Fixes made:
      section labels that were plain `<span>`s (Predicted class, Why this
      region?, Was this prediction correct?) promoted to real `<h3>`
      elements, nested correctly under each page's `<h2>` -- verified the
      full site now has a clean h1>h2>h3 outline, no skipped levels.
      Added a page-level `<h2>` to History and Metrics, which had none.
      `ModelMetrics.tsx`'s tables got `scope="col"`/`scope="row"` on all
      header cells and a real `<caption>` for the confusion matrix (was a
      sibling `<span>` -- captions are auto-announced when a screen reader
      lands on the table, a sibling span isn't). The decorative probability
      bar fill (`ProbabilityBars.tsx`) marked `aria-hidden` since its value
      is already in adjacent visible text -- avoids double-announcing.
      The file input (`UploadPredict.tsx`) had no accessible name (the
      nearby `<p>` doesn't count as a label) -- added `aria-label`. Every
      dynamic error/warning message across all 6 components that show one
      now has `role="alert"` so it's announced when it appears, not just
      when a screen reader happens to scan past it.
- [x] Keyboard navigation: verified every click handler in the codebase is
      attached to a real `<button>` (grepped for `onClick` -- zero
      `<div onClick>`/`<span onClick>` patterns), so Tab focus and
      Enter/Space activation work by default with zero custom JS needed.
      Confirmed no `outline-none`/`focus:outline-none` anywhere in the
      codebase (grepped), and directly verified via a real Tab keypress
      that focus-visible correctly triggers the browser's native outline
      on a nav link.
- [x] Contrast check, computed precisely rather than eyeballed: wrote an
      OKLCH/OKLab -> linear-sRGB -> WCAG relative-luminance converter (the
      live site's computed styles come back in oklch()/oklab(), not rgb(),
      since Tailwind v4's palette is natively OKLCH) and measured every
      text/background pairing the class-color system produces, including
      the translucent dark-mode badges (blended against the actual card
      background, not treated as opaque). All 8 badge combinations (4
      classes x light/dark) plus the confidence badge and predicted-class
      heading text passed WCAG AA (>=4.5:1) with real margin -- the
      tightest was 6.41:1, most were 6.5-8.4:1.
- [x] Focus states: confirmed visible (see keyboard nav above) -- browser
      default outline is untouched, nothing suppresses it.
- [x] Mobile (explicitly requested, beyond the original checklist):
      verified zero horizontal overflow at 375px width on every page
      (Predict, History, Scan Detail, Metrics) including the wide
      per-class and confusion-matrix tables, which correctly scroll inside
      their own `overflow-x-auto` container instead of breaking the page.
      Confirmed the nav header's `flex-col sm:flex-row` correctly stacks
      below the sm breakpoint with no element overlap, checked both
      logged-out and logged-in (longer username text) states.

## Checkpoint 11 — Deployment ⚪ stretch, do last

- [ ] Only attempt once everything above is solid locally
