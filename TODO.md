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
