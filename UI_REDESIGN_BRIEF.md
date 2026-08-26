# Visioret — UI Redesign Brief

> **Purpose of this document.** It describes an existing, fully-working web
> application whose UI needs a *structural* redesign (not a re-skin). Hand
> this to a design AI to get back a concrete design specification, which
> will then be implemented in the existing React codebase.
>
> **Hard requirement for whoever designs from this:** every screen you
> propose must be buildable from the data listed in section 5. Do not
> invent charts, panels, or metrics whose underlying data this system does
> not produce. If you want to show something not in section 5, say so
> explicitly and flag it as "requires new backend work" rather than
> silently assuming it exists.

---

## 1. What the product actually is

**Visioret** is an explainable-AI web application for **retinal OCT
(Optical Coherence Tomography) disease classification**.

A user uploads a single retinal OCT B-scan image. The system:

1. Checks the image really is an OCT scan (rejects photos, X-rays,
   screenshots, etc. — it refuses to guess rather than fabricate a
   diagnosis).
2. Classifies it into one of **4 classes**: `CNV`, `DME`, `DRUSEN`,
   `NORMAL`.
3. Returns a **confidence score** and the **full probability distribution**
   across all 4 classes.
4. Generates a **Grad-CAM heatmap overlay** — a colored heat overlay on the
   scan showing which region of the image drove the model's decision. This
   is the "explainable" part and is the centerpiece of the product.
5. Produces a short **written explanation** of why that region matters
   clinically.
6. Lets the user **review the prediction** (mark it correct, or flag it
   incorrect and supply the correct class + a comment).

Everything is stored, so there's a browsable **history** of past scans, and
a **model performance** page showing how well the model actually does.

### The four classes (for tone/semantics, not for you to restate as UI copy)

- **CNV** — choroidal neovascularization; abnormal vessel growth, a feature
  of wet age-related macular degeneration. Serious, needs follow-up.
- **DME** — diabetic macular edema; fluid buildup from leaking vessels, a
  complication of diabetic retinopathy. Serious, needs follow-up.
- **DRUSEN** — extracellular deposits under the retina; an *early* sign of
  AMD. Typically monitored rather than urgently treated.
- **NORMAL** — no abnormality found.

### Who uses it / context of use

- Primary user: a **researcher or clinician-in-training** reviewing OCT
  scans, plus **academic examiners** evaluating the project.
- This is a **4th-year undergraduate final-year project (thesis)** at IIT,
  University of Dhaka. It will be **presented and defended in front of an
  academic panel.**
- It is a **research/demo tool, not a certified clinical device.** It must
  look credible and serious, but must not pretend to be an approved
  diagnostic product.
- Usage is **desk-based and deliberate** — a user uploads one scan and
  studies the result carefully. It is *not* a high-volume queue tool, not
  a dashboard someone monitors all day, and not a consumer app.

---

## 2. The core problem with the current UI (why we're redoing it)

Direct feedback from the project owner, verbatim in substance:

> "The UI isn't something that catches the eye… it looks like someone
> designing a webpage for the first time… I asked multiple times for
> modification, you kept the same structure, just added animation… this is
> a 4th year project, not 1st year."

Concretely, what's wrong:

- **The structure itself is the problem, not the styling.** Previous
  attempts only changed colors/typography and later added animation on top
  of an unchanged layout. That did not fix it.
- The layout is a **single narrow centered column (max-width ~768px) of
  stacked, near-identical rounded white cards**, on every page. Every page
  looks like the same generic vertical card list.
- There is **no visual hierarchy between the important thing and the
  supporting things.** The Grad-CAM explanation — the entire point of the
  product — gets the same visual weight as a feedback form.
- It reads as a **generic Tailwind/bootstrap-y admin scaffold**, not as a
  purpose-built medical imaging tool.
- It **wastes the screen**: on a desktop monitor it's a thin ribbon of
  content down the middle with huge empty margins, even though the primary
  content is *images that deserve to be looked at closely*.

**What we want instead:** a considered, distinctive, professional interface
that feels like a real medical-imaging / diagnostic-review product. It
should be visually striking enough to hold an examiner's attention, while
staying serious and legible. A genuine information-architecture rethink is
expected and welcome — including changing what goes on which page, how the
screen is divided, and what the primary focal point of each screen is.

---

## 3. Current information architecture (5 routes)

All five routes render inside the same shell: a narrow centered column with
a header bar on top.

| Route | Purpose |
|---|---|
| `/` | Upload a scan and get a prediction (the main screen) |
| `/history` | List of all past scans, newest first |
| `/scans/:scanId` | Full detail view of one past scan |
| `/metrics` | Model performance / evaluation statistics |
| `/login` | Combined login + registration form |

### Persistent header (on every route)

A single horizontal bar, then a thin divider line, containing:

- **Left:** a small 32px square logo mark (rounded blue square with a
  concentric-circle "eye/target" glyph), then the wordmark **"Visioret"**,
  with a one-line tagline underneath: *"Explainable AI for retinal OCT
  disease classification"*.
- **Right, in one row:** three text nav links (**Predict / History /
  Metrics**), then a small status pill, then an auth control.
  - **Status pill** shows live backend health, one of: `"Model ready ·
    CPU"` (or `GPU`), `"No trained checkpoint"`, `"API unreachable"`, or
    `"checking API..."`. It also carries a tooltip listing the device and
    the 4 class names.
  - **Auth control** is either a "Log in" link, or the logged-in user's
    name plus a "Log out" button.
- On narrow screens the whole header stacks into two rows.

### Screen 1 — `/` Predict (the main screen)

Currently a vertical stack:

1. **Card, "Step 1 — Provide an image":** a numbered circular step badge,
   the heading *"Provide an image"*, subtext *"Upload an OCT B-scan (JPEG
   or PNG)."*, then a **native `<input type="file">`** (browser-default
   "Choose File / No file chosen" control, only lightly styled) sitting
   next to a **"Predict" button**. The Predict button is disabled until a
   file is chosen. While running it reads "Analyzing...".
2. **Preview:** once a file is chosen, a small thumbnail (max ~320px wide)
   of the selected image appears *inside* that same card. During inference
   a blue scan-line sweep animates over the preview.
3. **Then, below, conditionally:**
   - An **amber notice** if the image was rejected as not-an-OCT-scan
     (deliberately amber, not red — it's a valid decision, not an error).
   - A **red error box** if something actually failed.
   - Or the **results**, introduced by a "Step 2 — Results" heading, which
     renders the shared result block described below.

**Known weak points here:** the raw unstyled file input looks amateurish;
the preview thumbnail is tiny; and results appear *below the fold* stacked
under the upload card, so the moment of payoff is visually buried.

### Screen 2 — the shared "scan result" block

Used by both `/` (after predicting) and `/scans/:scanId`. Currently four
stacked full-width cards:

1. **Two images side by side** (single column on mobile): the **original
   scan** and the **Grad-CAM overlay**, each with a small caption beneath
   ("Original image" / "Grad-CAM overlay"). They're roughly 350px wide
   each on desktop. There is currently **no zoom, no toggle, no
   side-by-side slider, and no way to view either image larger.**
2. **Prediction card:** a small uppercase label "PREDICTED CLASS", a
   confidence pill on the right (e.g. `100.0% confidence`, animated
   count-up, colored by class), the **class name in large bold colored
   text** (e.g. "CNV"), and beneath it the **probability bars** — one row
   per class showing `CLASS NAME | ▓▓▓▓░░░░ | 12.3%`, sorted descending,
   with the winning class's bar in its class color and the rest grey.
3. **Explanation card:** small uppercase label "WHY THIS REGION?", then a
   paragraph of clinical text (~3–5 sentences) explaining what that disease
   looks like on OCT and where the model's attention was concentrated
   (e.g. *"…the model's attention was tightly concentrated in the central
   region of the scan."*).
4. **Feedback card:** small uppercase label "WAS THIS PREDICTION CORRECT?",
   then either two buttons (green **Correct** / red **Incorrect**), or —
   if already reviewed — a sentence stating the recorded verdict plus a
   "Change my review" link. Choosing "Incorrect" swaps in a dropdown of the
   4 classes plus an optional comment textarea, with Submit/Cancel buttons.

**Known weak points here:** the two most valuable things on the screen (the
Grad-CAM image and the explanation of it) are visually disconnected from
each other, sitting in separate boxes far apart, and the images are too
small to actually study.

### Screen 3 — `/history`

A page heading "Scan History", then a vertical list of rows. Each row is a
bordered white card containing: a **64×64 square thumbnail** of the scan, a
**class-colored dot + the predicted class name**, the **confidence
percentage** in monospace beneath it, and the **date/time** right-aligned.
Whole row is clickable through to the detail view. Rows slide in with a
stagger and shift slightly right on hover.

**Known weak points:** no filtering, no search, no sorting controls, no
grouping by class or date, no indication of which scans have been reviewed
vs. not — even though that information exists. It's a flat, undifferentiated
list.

### Screen 4 — `/scans/:scanId`

A "← Back to history" link, then a heading `Scan #18 · 8/23/2026, 10:46:52
AM` with a small right-aligned monospace `Model: resnet50_oct_1787404414`,
then the exact same four-card result block described in Screen 2.

### Screen 5 — `/metrics`

A page heading "Model Performance", then **one large card per evaluated
dataset** (currently 2 cards). Each card contains, stacked:

1. The dataset name as a heading, e.g. *"In-distribution (Kermany OCT2017
   held-out test)"* or *"Cross-dataset generalization (Noor Eye Hospital +
   OCTDL + Duke, held-out)"*, with the model version and evaluation
   timestamp in small monospace beneath.
2. **Four stat tiles in a row** (2×2 on mobile): Accuracy, Macro Precision,
   Macro Recall, Macro F1 — each a small grey box with an uppercase label
   and a large monospace percentage that counts up on load.
3. **A per-class table:** rows = the 4 classes (each with its color dot),
   columns = Precision / Recall / F1 / Support.
4. **A confusion matrix table:** 4×4 grid of counts, rows = true label,
   columns = predicted label, with cells tinted by intensity — blue on the
   diagonal (correct), red off-diagonal (errors), proportional to the row
   total.

**Known weak points:** this is the most data-rich page in the app and it's
presented as plain HTML tables in a card. It's the page most likely to be
scrutinized in a thesis defense and it currently looks like unstyled output.

### Screen 6 — `/login`

A single narrow centered card (~384px) with a heading, a line of subtext
explaining login is optional, then Name (register only) / Email / Password
fields, a submit button, and a link toggling between login and register
modes.

---

## 4. Current visual language (all of which is open to being replaced)

- **Typography:** Inter for UI text; IBM Plex Mono for all numbers,
  IDs, model version strings, and confidence values.
- **Layout:** one centered column, `max-width: 768px`, ~32–40px vertical
  page padding, 24px gaps between cards.
- **Cards:** white (`#fff`) / dark `slate-900`, 1px `slate-200` border,
  12–16px corner radius, very subtle shadow.
- **Page background:** `slate-50` light / `slate-950` dark, with three
  large soft blurred colored blobs (blue, violet, emerald) slowly drifting
  behind everything.
- **Brand color:** blue (`blue-600`) for nav active state, primary buttons,
  links, and the logo.
- **Per-class semantic colors** — *this system is worth preserving in
  concept even if the palette changes*, because it lets a user recognize a
  class by color anywhere in the app:
  - `CNV` → **amber**
  - `DME` → **rose**
  - `DRUSEN` → **violet**
  - `NORMAL` → **emerald**
  - These are used for: the big class name text, the confidence pill, the
    winning probability bar, and the history-list dots.
- **Dark mode:** fully implemented throughout, follows the OS setting
  (`prefers-color-scheme`). **Any new design must work in both light and
  dark.**
- **Existing animations** (keep, adapt, or replace as the design calls
  for): page-to-page fade/slide transitions; a sliding "pill" that animates
  between nav items; staggered card entrances; count-up numbers; animated
  probability-bar fills; button hover/tap feedback; a scan-line sweep over
  the image while inference runs.

---

## 5. The real data available — DESIGN ONLY WITH THIS

This is the complete set of data the backend actually returns. **Anything
not on this list does not exist** and cannot be shown without new backend
work.

**On predicting / viewing a scan:**
- `scan_id` — integer
- `predicted_class` — one of `CNV` / `DME` / `DRUSEN` / `NORMAL`
- `confidence` — float 0–1 (in practice usually very high, often >0.95)
- `probabilities` — all 4 classes with their float 0–1 scores
- `original_image_url` — the uploaded OCT scan image
- `gradcam_overlay_url` — the same scan with the heat overlay burned in
  (note: it is a *pre-rendered image*, not an adjustable layer — opacity
  cannot be changed client-side)
- `explanation` — a paragraph of text (~3–5 sentences)
- `uploaded_at` — timestamp
- `model_version_label` — a string like `resnet50_oct_1787404414`
- `feedback` — either nothing, or `{ is_correct, corrected_class, comment,
  reviewed_at }`

**History list, per row:** `scan_id`, `uploaded_at`, `predicted_class`,
`confidence`, `original_image_url`. *(Note: the list endpoint does not
currently return whether a scan was reviewed — showing that would need a
small backend change, which is doable if the design calls for it.)*

**Model metrics, per dataset split:** `dataset_split_label` (human-readable
name), `accuracy`, `precision_macro`, `recall_macro`, `f1_macro`,
`per_class_metrics` (per class: precision / recall / f1 / support count),
`confusion_matrix` (4 labels + a 4×4 integer grid), `evaluated_at`,
`model_version_label`. There are currently **2** such splits.

**System health:** `device` (`cpu`/`gpu`), `checkpoint_loaded` (bool),
`classes` (the 4 names), `ood_gate_active` (bool).

**User:** `id`, `name`, `email`, `role` (currently always `"researcher"`).

**Real example values, so proportions are realistic:**
- Accuracy 95.2%, Macro F1 92.3% (in-distribution)
- Accuracy 88.1%, Macro F1 89.5% (cross-dataset)
- A typical prediction: CNV at 100.0%, others at 0.0%
- Per-class F1 ranges roughly 0.74–0.98
- Confusion matrix counts range from single digits to ~6264
- Scan images are grayscale, landscape, roughly 512×496 to 1100×410 px

---

## 6. Technical constraints the design must respect

- **Stack:** React 19 + TypeScript, Vite, **Tailwind CSS v4**,
  React Router v7, **framer-motion** for animation. Served as a static
  build behind nginx; talks to a separate FastAPI backend.
- Design should be expressible in **Tailwind utility classes**. Custom CSS
  is possible but should be the exception. Avoid designs that would
  require a whole additional UI component library.
- **Must be fully responsive**, working properly from 375px mobile up to
  wide desktop. Currently verified to have zero horizontal overflow at
  375px — that must stay true.
- **Must remain accessible**, and this is non-negotiable because it was
  explicitly built and verified: semantic headings in correct order, real
  `<button>`/`<a>` elements (never clickable divs), visible keyboard focus
  states, `role="alert"` on error/warning messages, proper table headers
  with `scope`, and **WCAG AA contrast (≥4.5:1) in both light and dark
  mode** — the current class colors were measured and pass at 6.4–8.4:1.
- **Respect `prefers-reduced-motion`** — animations must be disable-able.
- Keep all existing functionality: upload, predict, the not-an-OCT-scan
  rejection state, error states, loading states, probability display,
  Grad-CAM display, explanation text, review/correction flow, history
  browsing, metrics, and optional login.
- Images come from the backend at their native size; the design should
  specify how they're framed/cropped/scaled.

---

## 7. What we're asking for

A **structural redesign**, not a color swap. Specifically, please propose:

1. **An overall layout system** — is it still a centered column? A sidebar
   + main content? A two-pane workspace? Something else? Justify it for
   this specific use case (studying one medical image at a time).
2. **Screen-by-screen layouts** for all five routes, saying what is
   primary, secondary, and tertiary on each.
3. **A specific treatment for the Grad-CAM comparison** — this is the
   product's centerpiece and currently the weakest part. How should the
   original and heatmap be presented and compared?
4. **A real design system**: palette (light + dark), type scale, spacing
   scale, elevation/border treatment, and component styles for buttons,
   inputs, cards, tables, badges, and empty/loading/error states.
5. **A distinctive visual identity** appropriate to a serious medical
   imaging tool — something with a point of view, not a default admin
   template.
6. **Motion guidance** — what should animate, and what shouldn't.

Where a proposal needs data that section 5 doesn't cover, call it out
explicitly as requiring backend work instead of assuming it exists.
