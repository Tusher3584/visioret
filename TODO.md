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

## Checkpoint 3 — Grad-CAM accuracy

Likely benefits from Checkpoint 2's cleaner input. Revisit after that lands.

- [ ] Assess current Grad-CAM localization quality on the (re)trained model
- [ ] Consider a sharper variant (e.g. Grad-CAM++) if plain Grad-CAM still
      isn't precise enough
- [ ] Re-verify against the CNV/DRUSEN confusion pattern found in Phase A
      evaluation (243 CNV images misclassified as DRUSEN) — does a tighter
      CAM correlate with fewer of these errors?

## Checkpoint 4 — Grad-CAM "why" explanation section

- [ ] Write per-class clinical explanation content (what CNV/DME/DRUSEN/
      NORMAL findings typically look like on OCT, why that region matters)
- [ ] Decide static (templated per predicted class) vs. dynamic (also
      describing *where* in the image the heatmap concentrates)
- [ ] Add to both backend response and frontend display

## Checkpoint 5 — Additional data sources / generalization

- [ ] Identify appropriate additional public OCT datasets beyond Kermany
      OCT2017 (different scanners/populations)
- [ ] Decide: fine-tune on a combined set, or evaluate cross-dataset as a
      generalization test (or both)
- [ ] Document the generalization result honestly either way

## Checkpoint 6 — UI redesign

Current frontend is functionally correct but visually generic
(default-Tailwind look, no real design pass). Needs to look like a
considered product for a final-year defense, not a scaffold.

- [ ] Real design pass: typography, layout, color system, information
      hierarchy — not just "it uses Tailwind"
- [ ] Apply consistently across Predict / History / Detail views

## Checkpoint 7 — Evaluation metrics integrated into the app

- [ ] Backend: write `evaluate.py` results into the `EvaluationMetric` table
      (currently defined in the schema but never populated)
- [ ] API endpoint to serve model evaluation metrics
- [ ] Frontend: a view showing accuracy/precision/recall/F1/confusion matrix
      — currently these only exist as offline files nobody using the app can see

## Checkpoint 8 — Feedback / correction workflow

- [ ] API endpoint(s) for submitting a correction against a prediction
      (the `Feedback` table already exists, unused)
- [ ] Frontend: a way to flag/correct a prediction from the scan detail view

## Checkpoint 9 — User accounts

- [ ] Decide how much auth is actually needed (simple role-based accounts,
      not a full identity provider — per earlier scope note)
- [ ] Backend: registration/login, associate scans with the real `user_id`
      (currently always `NULL`)
- [ ] Frontend: login/account UI, role-appropriate views if relevant

## Checkpoint 10 — Accessibility pass

- [ ] Semantic HTML / ARIA review
- [ ] Keyboard navigation check
- [ ] Contrast check (light + dark mode)
- [ ] Focus states visible throughout

## Checkpoint 11 — Deployment ⚪ stretch, do last

- [ ] Only attempt once everything above is solid locally
