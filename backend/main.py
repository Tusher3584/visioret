"""Visioret backend -- FastAPI service wrapping model/inference.py.

Run with (from the project root):
    uvicorn backend.main:app --reload --port 8000
"""

import io
import os
import sys
from contextlib import asynccontextmanager

import torch
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from sqlalchemy import false as sa_false, func
from sqlalchemy.orm import Session, joinedload, selectinload

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.inference import (  # noqa: E402
    generate_gradcam,
    load_model,
    overlay_gradcam,
    predict,
    preprocess_image,
)
from model.clip_ood import load_clip  # noqa: E402
from model.explanations import build_explanation  # noqa: E402
from model.ood_detector import check_is_oct  # noqa: E402

from backend.auth import (  # noqa: E402
    ASSIGNABLE_ROLES,
    ROLE_ADMIN,
    create_access_token,
    get_current_user,
    get_current_user_optional,
    hash_password,
    is_reviewer,
    require_admin,
    require_reviewer,
    spend_password_verification_time,
    verify_password,
)
from backend.rate_limit import (  # noqa: E402
    LOGIN_MAX_ATTEMPTS,
    LOGIN_WINDOW_SECONDS,
    REGISTER_MAX_ATTEMPTS,
    REGISTER_WINDOW_SECONDS,
    clear_attempts,
    enforce,
)
from backend.db.model_version import get_or_create_model_version  # noqa: E402
from backend.db.seed_metrics import seed_evaluation_metrics  # noqa: E402
from backend.db.models import EvaluationMetric, Feedback, GradcamResult, Prediction, Scan, User  # noqa: E402
from backend.db.session import get_db  # noqa: E402
from backend.schemas import (  # noqa: E402
    AdminUserRow,
    EvaluationMetricResponse,
    FeedbackCreate,
    FeedbackResponse,
    HealthResponse,
    LoginRequest,
    PredictionResponse,
    ProfileUpdate,
    RegisterRequest,
    RoleUpdate,
    ScanDetail,
    ScanSummary,
    TokenResponse,
    UserResponse,
)
from backend.storage import MEDIA_DIR, discard_scan_images, new_scan_id, save_scan_images  # noqa: E402

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKPOINT_PATH = os.path.join(ROOT_DIR, "model", "checkpoints", "resnet50_oct.pth")

# An OCT B-scan is a few hundred KB. 12 MB is generous for a lossless PNG of
# a large volume slice and still small enough that a burst of uploads cannot
# exhaust container memory.
MAX_UPLOAD_BYTES = 12 * 1024 * 1024

# Pillow's own bomb guard. The default (~89 MP) only WARNS at 1x and raises at
# 2x; setting it explicitly to something that comfortably exceeds any real OCT
# scan means DecompressionBombError fires early, before the pixels are
# allocated. The largest genuine scan seen in the four datasets is ~0.8 MP.
Image.MAX_IMAGE_PIXELS = 64_000_000

# Upper bound for GET /api/scans?limit=. Large enough that no real history
# view needs paging, small enough that one request cannot ask the database
# for everything.
MAX_SCAN_LIMIT = 200

model_state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, checkpoint_loaded, classes, val_macro_f1 = load_model(CHECKPOINT_PATH, device)
    model_state["model"] = model
    model_state["device"] = device
    model_state["checkpoint_loaded"] = checkpoint_loaded
    model_state["classes"] = classes
    clip_model, clip_processor = load_clip(device)
    model_state["clip_model"] = clip_model
    model_state["clip_processor"] = clip_processor

    from backend.db.session import SessionLocal

    db = SessionLocal()
    try:
        version = get_or_create_model_version(db, CHECKPOINT_PATH, val_macro_f1)
        model_state["model_version_id"] = version.id
        model_state["model_version_label"] = version.version_label
        # Populate the metrics page on a machine that has never run
        # model/evaluate.py (which needs the full dataset, not in the repo).
        # Only inserts splits that are missing, so a real local evaluation
        # always takes precedence over the committed export.
        seed_evaluation_metrics(db, CHECKPOINT_PATH, version.id)
    finally:
        db.close()

    yield
    model_state.clear()


app = FastAPI(title="Visioret API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(MEDIA_DIR, exist_ok=True)
# Scan images and Grad-CAM overlays are served as static files, WITHOUT an
# authorization check. This is a deliberate trade-off, not an oversight, and
# it is the one place where the ownership rules enforced by
# _visible_scans_query do not reach:
#
#   - Filenames are uuid4().hex, so a URL cannot be guessed or enumerated
#     (2^128 keyspace) -- possession of the link is the capability.
#   - Anyone who holds the link keeps access indefinitely, including after
#     an anonymous session ends. A link pasted into a chat or captured in a
#     proxy log stays live.
#
# It stays this way because the frontend renders these through plain <img>
# tags, which cannot attach an Authorization header; making them private
# needs either short-lived signed URLs or an authenticated proxy endpoint,
# and neither is warranted for a single-instance research demo carrying no
# patient identifiers. Any deployment holding real patient data should close
# this before anything else.
#
# Path traversal is not a concern here: StaticFiles resolves and confines
# paths itself (verified -- /media/../main.py and the percent-encoded form
# both 404).
app.mount("/media", StaticFiles(directory=os.path.dirname(MEDIA_DIR)), name="media")


@app.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        device=model_state["device"].type,
        checkpoint_loaded=model_state["checkpoint_loaded"],
        classes=model_state["classes"],
        ood_gate_active=model_state.get("clip_model") is not None,
    )


# Opaque id identifying one anonymous browser session. Sent by the frontend
# from sessionStorage, so it dies when the browser closes. Length-capped
# because it lands in an indexed String(64) column.
def anon_session_id(x_anon_session: str | None = Header(default=None)) -> str | None:
    if not x_anon_session:
        return None
    value = x_anon_session.strip()
    return value[:64] or None


def _user_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, name=user.name, email=user.email, role=user.role)


@app.post("/api/auth/register", response_model=TokenResponse)
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    enforce(request, "register", REGISTER_MAX_ATTEMPTS, REGISTER_WINDOW_SECONDS)
    # Length/format bounds (name, email, password 8..72) are enforced by
    # RegisterRequest -- see backend/schemas.py for why they belong there.
    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    user = User(name=body.name.strip(), email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenResponse(access_token=create_access_token(user.id), user=_user_response(user))


@app.post("/api/auth/login", response_model=TokenResponse)
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    # Counted before the attempt; cleared on success, so only failures
    # accumulate and a legitimate user signing in is never penalised.
    enforce(request, "login", LOGIN_MAX_ATTEMPTS, LOGIN_WINDOW_SECONDS)

    user = db.query(User).filter_by(email=body.email).first()
    if user is None:
        # Spend the same bcrypt time we would have on a real account before
        # answering. The message already refuses to distinguish "no such
        # email" from "wrong password"; without this, the response time does
        # the distinguishing instead.
        spend_password_verification_time()
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    clear_attempts(request, "login")
    return TokenResponse(access_token=create_access_token(user.id), user=_user_response(user))


@app.get("/api/auth/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return _user_response(user)


@app.patch("/api/auth/me", response_model=UserResponse)
def update_me(
    body: ProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update the signed-in account's own profile.

    Deliberately cannot change `role` or `email`: role is an administrative
    grant (see backend/grant_role.py) and must never be self-assignable, and
    email is the identity the account is keyed on.
    """
    changed = False

    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name cannot be empty.")
        user.name = name
        changed = True

    if body.new_password is not None:
        # Length bounds (8..72) come from ProfileUpdate; see backend/schemas.py.
        # Require the current password so a stolen/borrowed session cannot
        # silently lock the real owner out of their account.
        if not body.current_password or not verify_password(
            body.current_password, user.password_hash
        ):
            raise HTTPException(status_code=400, detail="Current password is incorrect.")
        user.password_hash = hash_password(body.new_password)
        changed = True

    if not changed:
        raise HTTPException(status_code=400, detail="Nothing to update.")

    db.commit()
    db.refresh(user)
    return _user_response(user)


def _admin_user_row(user: User, current: User, scans: dict, reviews: dict) -> AdminUserRow:
    return AdminUserRow(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
        scans_submitted=scans.get(user.id, 0),
        reviews_recorded=reviews.get(user.id, 0),
        is_self=user.id == current.id,
        # Admin accounts are managed only against the database, so they are
        # never editable here -- that is what stops the role spreading (or an
        # admin being locked out) through the API.
        is_editable=user.role != ROLE_ADMIN,
    )


@app.get("/api/admin/users", response_model=list[AdminUserRow])
def admin_list_users(db: Session = Depends(get_db), current: User = Depends(require_admin)):
    """Every account, for the admin user-management view."""
    users = db.query(User).order_by(User.created_at.asc()).all()

    scans = dict(
        db.query(Scan.user_id, func.count(Scan.id))
        .filter(Scan.user_id.isnot(None))
        .group_by(Scan.user_id)
        .all()
    )
    reviews = dict(
        db.query(Feedback.reviewed_by, func.count(Feedback.id))
        .filter(Feedback.reviewed_by.isnot(None))
        .group_by(Feedback.reviewed_by)
        .all()
    )

    return [_admin_user_row(u, current, scans, reviews) for u in users]


@app.patch("/api/admin/users/{user_id}/role", response_model=AdminUserRow)
def admin_set_role(
    user_id: int,
    body: RoleUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
):
    """Promote or demote an account between viewer and reviewer.

    Three things this deliberately refuses, so that administrative privilege
    can only ever originate from direct database access:
      - granting admin (not in ASSIGNABLE_ROLES),
      - modifying an existing admin (including demoting a rival admin),
      - changing your own role (an admin cannot lock themselves out, and
        cannot quietly hand themselves something else either).
    """
    if body.role not in ASSIGNABLE_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Role must be one of {list(ASSIGNABLE_ROLES)}. The admin role is granted "
            "directly against the database, not through this API.",
        )

    target = db.query(User).filter_by(id=user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="No such account.")

    if target.id == current.id:
        raise HTTPException(status_code=400, detail="You cannot change your own role.")

    if target.role == ROLE_ADMIN:
        raise HTTPException(
            status_code=400,
            detail="Admin accounts are managed directly against the database.",
        )

    target.role = body.role
    db.commit()
    db.refresh(target)

    scans = dict(
        db.query(Scan.user_id, func.count(Scan.id))
        .filter(Scan.user_id.isnot(None))
        .group_by(Scan.user_id)
        .all()
    )
    reviews = dict(
        db.query(Feedback.reviewed_by, func.count(Feedback.id))
        .filter(Feedback.reviewed_by.isnot(None))
        .group_by(Feedback.reviewed_by)
        .all()
    )
    return _admin_user_row(target, current, scans, reviews)


DATASET_SPLIT_LABELS = {
    "kermany_test": "In-distribution (Kermany OCT2017 held-out test)",
    "external_test": "Cross-dataset generalization (Noor Eye Hospital + OCTDL + Duke, held-out)",
}


@app.get("/api/metrics", response_model=list[EvaluationMetricResponse])
def get_metrics(
    db: Session = Depends(get_db),
    _reviewer: User = Depends(require_reviewer),
):
    """Latest evaluation results for the currently deployed model, one row
    per dataset split that's been evaluated (see model/evaluate.py and
    model/evaluate_cross_dataset.py -- neither runs automatically, so this
    reflects whenever those were last run against the current checkpoint)."""
    version_id = model_state.get("model_version_id")
    if version_id is None:
        return []
    metrics = (
        db.query(EvaluationMetric)
        .filter_by(model_version_id=version_id)
        .order_by(EvaluationMetric.dataset_split)
        .all()
    )
    return [
        EvaluationMetricResponse(
            dataset_split=m.dataset_split,
            dataset_split_label=DATASET_SPLIT_LABELS.get(m.dataset_split, m.dataset_split),
            accuracy=m.accuracy,
            precision_macro=m.precision_macro,
            recall_macro=m.recall_macro,
            f1_macro=m.f1_macro,
            per_class_metrics=m.per_class_metrics,
            confusion_matrix=m.confusion_matrix,
            evaluated_at=m.evaluated_at,
            model_version_label=model_state["model_version_label"],
        )
        for m in metrics
    ]


@app.post("/api/predict", response_model=PredictionResponse)
async def predict_endpoint(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
    session_id: str | None = Depends(anon_session_id),
):
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=400, detail="File must be a JPEG or PNG image.")

    # Reject on the declared size before reading anything. An OCT B-scan is
    # a few hundred KB; there is no legitimate 80 MB upload here, and
    # `await file.read()` would otherwise buffer the whole body in memory
    # before we ever got a chance to say no.
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. The limit is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        # Belt and braces: file.size comes from the client's multipart headers
        # and a hand-rolled request can omit or understate it.
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. The limit is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    try:
        image = Image.open(io.BytesIO(contents))
        image.load()
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="Could not read file as an image.")
    except Image.DecompressionBombError:
        # A small file can declare enormous dimensions -- a 459 KB PNG
        # expanding to 484 megapixels was accepted before this, allocating
        # gigabytes on a half-megabyte upload.
        raise HTTPException(
            status_code=400,
            detail="Image dimensions are implausibly large for an OCT scan.",
        )
    except Exception:
        # Truncated files, unsupported PNG variants and broken EXIF all raise
        # their own types here. Every one of them is a bad upload, i.e. a 400,
        # and letting any escape turns a client error into a 500.
        raise HTTPException(status_code=400, detail="Could not read file as an image.")

    model = model_state["model"]
    device = model_state["device"]
    classes = model_state["classes"]

    image_tensor = preprocess_image(image)

    is_oct, reason, detail = check_is_oct(image, model_state["clip_model"], model_state["clip_processor"], device)
    if not is_oct:
        raise HTTPException(
            status_code=422,
            detail=(
                "This doesn't look like a retinal OCT scan, so no diagnosis was made. "
                "Please upload an OCT B-scan image (JPEG/PNG)."
            ),
        )

    class_name, confidence, probabilities = predict(model, image_tensor, device, class_names=classes)
    class_index = classes.index(class_name)
    heatmap = generate_gradcam(model, image_tensor, class_index, device)
    overlay = overlay_gradcam(image, heatmap)
    explanation = build_explanation(class_name, heatmap)

    file_id = new_scan_id()
    original_url, overlay_url = save_scan_images(file_id, image, overlay)

    try:
        scan = Scan(
            file_path=original_url,
            user_id=current_user.id if current_user else None,
            # Only meaningful for anonymous submissions; a signed-in scan is owned
            # by user_id and must not also be reachable via a session id.
            anon_session=None if current_user else session_id,
        )
        db.add(scan)
        db.flush()  # assigns scan.id without committing yet

        prediction = Prediction(
            scan_id=scan.id,
            model_version_id=model_state["model_version_id"],
            predicted_class=class_name,
            confidence=confidence,
            class_probabilities=probabilities,
        )
        db.add(prediction)
        db.flush()

        db.add(GradcamResult(prediction_id=prediction.id, heatmap_path=overlay_url, explanation=explanation))
        db.commit()
    except Exception:
        # The two JPEGs are already on disk at this point. A failed commit
        # would otherwise leave them there permanently with nothing in the
        # database referencing them -- files nobody can reach and nobody
        # knows to delete.
        db.rollback()
        discard_scan_images(original_url, overlay_url)
        raise

    return PredictionResponse(
        scan_id=scan.id,
        predicted_class=class_name,
        confidence=confidence,
        probabilities=probabilities,
        original_image_url=original_url,
        gradcam_overlay_url=overlay_url,
        explanation=explanation,
    )


def _visible_scans_query(db: Session, current_user: User | None, session_id: str | None):
    """Scans the caller is allowed to see.

    Reviewers (and admins) see everything -- reviewing other people's
    predictions is the point of the role. A signed-in viewer sees only scans
    they own. An anonymous caller sees only scans carrying their own session
    id, never another anonymous visitor's.

    A missing session id matches nothing rather than matching all anonymous
    rows: `anon_session IS NULL` would otherwise re-expose the whole pooled
    history to any caller who simply omitted the header.
    """
    query = db.query(Scan)
    if is_reviewer(current_user):
        return query
    if current_user is not None:
        return query.filter(Scan.user_id == current_user.id)
    if not session_id:
        return query.filter(sa_false())
    return query.filter(Scan.user_id.is_(None), Scan.anon_session == session_id)


@app.get("/api/scans", response_model=list[ScanSummary])
def list_scans(
    db: Session = Depends(get_db),
    # Bounded: `?limit=-1` became SQL `LIMIT -1` and 500'd, and `?limit=999999`
    # was accepted outright -- which, combined with the eager loading below,
    # is one request asking the database for the entire table.
    limit: int = Query(default=50, ge=1, le=MAX_SCAN_LIMIT),
    current_user: User | None = Depends(get_current_user_optional),
    session_id: str | None = Depends(anon_session_id),
):
    scans = (
        _visible_scans_query(db, current_user, session_id)
        # Without these the loop below lazy-loads predictions and user per
        # row: ~101 queries to render 50 scans. selectinload issues one extra
        # query for all predictions; joinedload folds the owner into the main
        # one.
        .options(selectinload(Scan.predictions), joinedload(Scan.user))
        # A scan with no prediction row can never be rendered, so exclude it
        # in SQL rather than dropping it afterwards -- filtering post-limit
        # meant `?limit=50` could return fewer than 50 while more existed.
        .filter(Scan.predictions.any())
        .order_by(Scan.uploaded_at.desc())
        .limit(limit)
        .all()
    )
    results = []
    for scan in scans:
        if not scan.predictions:
            continue
        latest = max(scan.predictions, key=lambda p: p.predicted_at)
        results.append(
            ScanSummary(
                scan_id=scan.id,
                uploaded_at=scan.uploaded_at,
                predicted_class=latest.predicted_class,
                confidence=latest.confidence,
                original_image_url=scan.file_path,
                owner_name=scan.user.name if scan.user else None,
            )
        )
    return results


@app.get("/api/scans/{scan_id}", response_model=ScanDetail)
def get_scan(
    scan_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
    session_id: str | None = Depends(anon_session_id),
):
    # Filtered through the same visibility rule as the list, so a scan you
    # cannot see in history cannot be opened by guessing its URL either.
    scan = (
        _visible_scans_query(db, current_user, session_id).filter(Scan.id == scan_id).first()
    )
    if not scan or not scan.predictions:
        raise HTTPException(status_code=404, detail="Scan not found.")

    latest = max(scan.predictions, key=lambda p: p.predicted_at)
    if not latest.gradcam_result:
        raise HTTPException(status_code=500, detail="Scan has no Grad-CAM result on record.")

    return ScanDetail(
        scan_id=scan.id,
        uploaded_at=scan.uploaded_at,
        predicted_class=latest.predicted_class,
        confidence=latest.confidence,
        probabilities=latest.class_probabilities,
        original_image_url=scan.file_path,
        gradcam_overlay_url=latest.gradcam_result.heatmap_path,
        explanation=latest.gradcam_result.explanation,
        model_version_label=latest.model_version.version_label,
        feedback=_feedback_response(latest.feedback),
        owner_name=scan.user.name if scan.user else None,
        can_review=is_reviewer(current_user),
    )


def _feedback_response(feedback: Feedback | None) -> FeedbackResponse | None:
    if feedback is None:
        return None
    return FeedbackResponse(
        is_correct=feedback.is_correct,
        corrected_class=feedback.corrected_class,
        comment=feedback.comment,
        reviewed_at=feedback.reviewed_at,
        reviewer_name=feedback.reviewer.name if feedback.reviewer else None,
    )


@app.put("/api/scans/{scan_id}/feedback", response_model=FeedbackResponse)
def submit_feedback(
    scan_id: int,
    body: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_reviewer),
):
    """Flags the scan's latest prediction as correct/incorrect, optionally
    with the corrected class. Upserts -- resubmitting replaces the previous
    feedback for that prediction, since `feedback.prediction_id` is unique
    (one review per prediction).

    Reviewer-only: a correction is a human label asserting the model was
    wrong, and is the kind of record that would feed back into retraining,
    so it needs an identified and qualified author."""
    scan = db.query(Scan).filter_by(id=scan_id).first()
    if not scan or not scan.predictions:
        raise HTTPException(status_code=404, detail="Scan not found.")

    if not body.is_correct:
        if not body.corrected_class:
            raise HTTPException(status_code=400, detail="corrected_class is required when is_correct is false.")
        if body.corrected_class not in model_state["classes"]:
            raise HTTPException(
                status_code=400,
                detail=f"corrected_class must be one of {model_state['classes']}.",
            )

    latest = max(scan.predictions, key=lambda p: p.predicted_at)

    existing = db.query(Feedback).filter_by(prediction_id=latest.id).first()
    if existing:
        db.delete(existing)
        db.flush()

    feedback = Feedback(
        prediction_id=latest.id,
        reviewed_by=current_user.id,
        is_correct=body.is_correct,
        corrected_class=body.corrected_class if not body.is_correct else None,
        comment=body.comment,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return _feedback_response(feedback)
