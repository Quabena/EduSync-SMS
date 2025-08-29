import os
from flask import (
    render_template,
    flash,
    redirect,
    url_for,
    request,
    current_app,
    abort,
    send_file,
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
import secrets
import mimetypes
from pathlib import Path
from PIL import Image
from app.decorators import role_required
from app.models import Teacher, Subject, Class
from app.teachers.forms import TeacherForm
from app.teachers import bp
from app.utils.storage import backup_database
from datetime import datetime


@bp.route("/")
@login_required
@role_required(["admin", "headteacher"])
def index():
    teachers = Teacher.query.all()
    return render_template("teachers/list.html", teachers=teachers)


@bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required(["admin", "headteacher"])
def create():
    form = TeacherForm()

    if form.validate_on_submit():
        photo_filename = None

        # Save uploaded photo if present
        if form.photo.data:
            try:
                photo_filename = save_teacher_photo(form.photo.data)
            except ValueError as e:
                flash(str(e), "danger")
                return render_template("teachers/create.html", form=form)

        # Save certificates (append-only storage model, store just filenames)
        certificate_paths = []
        if form.certificates.data:
            for cert in form.certificates.data:
                if cert and cert.filename:
                    try:
                        filename = save_teacher_certificate(cert)
                        certificate_paths.append(filename)
                    except ValueError as e:
                        flash(str(e), "danger")
                        return render_template("teachers/create.html", form=form)

        teacher = Teacher(
            first_name=form.first_name.data,
            middle_name=form.middle_name.data,
            surname=form.surname.data,
            gender=form.gender.data,
            date_of_birth=form.date_of_birth.data,
            hometown=form.hometown.data,
            college_attended=form.college_attended.data,
            area_of_specialization=form.area_of_specialization.data,
            academic_certificate=form.academic_certificate.data,
            academic_area_of_study=form.academic_area_of_study.data,
            academic_college=form.academic_college.data,
            professional_certificate=form.professional_certificate.data,
            professional_area_of_study=form.professional_area_of_study.data,
            professional_college=form.professional_college.data,
            staff_id=form.staff_id.data,
            registered_number=form.registered_number.data,
            ntc_number=form.ntc_number.data,
            ssnit_number=form.ssnit_number.data,
            phone_number=form.phone_number.data,
            email=form.email.data,
            emergency_contact_name=form.emergency_contact_name.data,
            emergency_contact_number=form.emergency_contact_number.data,
            photo_path=photo_filename,
            certificate_paths=(
                ",".join(certificate_paths) if certificate_paths else None
            ),
            specialization_id=form.specialization_id.data,
        )

        # Add assigned classes
        for class_id in form.assigned_classes.data:  # type: ignore
            class_ = Class.query.get(class_id)
            if class_:
                teacher.classes.append(class_)

        db.session.add(teacher)
        db.session.commit()

        flash("Teacher created successfully!", "success")
        backup_database()
        return redirect(url_for("teachers.detail", teacher_id=teacher.id))

    return render_template("teachers/create.html", form=form)


@bp.route("/<int:teacher_id>")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def detail(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    return render_template("teachers/detail.html", teacher=teacher)


@bp.route("/<int:teacher_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(["admin", "headteacher"])
def edit(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    form = TeacherForm(obj=teacher)

    # Populate dropdowns
    form.specialization_id.choices = [
        (s.id, s.name) for s in Subject.query.order_by(Subject.name).all()
    ]
    form.assigned_classes.choices = [
        (c.id, c.name) for c in Class.query.order_by(Class.name).all()
    ]

    # Pre-select assigned classes for GET requests
    if request.method == "GET":
        form.assigned_classes.data = [c.id for c in teacher.classes]

    if form.validate_on_submit():
        # === Photo replacement ===
        if form.photo.data:
            if teacher.photo_path:
                document_dir = Path(current_app.config["TEACHER_PHOTOS_DIR"]).resolve()
                old = (document_dir / teacher.photo_path).resolve()
                try:
                    old.relative_to(document_dir)  # safety check
                    if old.exists():
                        try:
                            old.unlink()
                        except Exception:
                            current_app.logger.warning(
                                f"Could not delete previous photo for teacher {teacher.id}"
                            )
                except Exception:
                    current_app.logger.warning(
                        f"Invalid or missing old photo path for teacher {teacher.id}"
                    )

            try:
                new_filename = save_teacher_photo(form.photo.data)
                teacher.photo_path = new_filename
            except ValueError as e:
                flash(str(e), "danger")
                return redirect(url_for("teachers.edit", teacher_id=teacher.id))

        # === Certificates: append new uploads ===
        if form.certificates.data and any(
            getattr(f, "filename", "") for f in form.certificates.data
        ):
            new_files = []
            for cert in form.certificates.data:
                if cert and cert.filename:
                    try:
                        filename = save_teacher_certificate(cert)
                        new_files.append(filename)
                    except ValueError as e:
                        flash(str(e), "danger")
                        return redirect(url_for("teachers.edit", teacher_id=teacher.id))

            if new_files:
                existing = (
                    teacher.certificate_paths.split(",")
                    if teacher.certificate_paths
                    else []
                )
                teacher.certificate_paths = ",".join(existing + new_files)

        # === Update other fields ===
        form.populate_obj(teacher)

        # === Update classes (replace) ===
        teacher.classes = Class.query.filter(
            Class.id.in_(form.assigned_classes.data)
        ).all()

        db.session.commit()
        flash("Teacher updated successfully!", "success")
        backup_database()
        return redirect(url_for("teachers.detail", teacher_id=teacher.id))

    return render_template("teachers/edit.html", form=form, teacher=teacher)


# Allowed MIME types for images
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

# Allowed certificate/document types
ALLOWED_CERT_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}
ALLOWED_CERT_EXTS = {".pdf", ".jpg", ".jpeg", ".png"}


def _is_safe_path(base_dir: Path, path: Path) -> bool:
    """Return True if path is inside base_dir."""
    try:
        path.resolve().relative_to(base_dir.resolve())
        return True
    except Exception:
        return False


@bp.route("/photos/<path:filename>")
@login_required
def teacher_photo(filename):
    """Serve teacher photos safely from TEACHER_PHOTOS_DIR."""
    document_dir = Path(current_app.config["TEACHER_PHOTOS_DIR"]).resolve()

    if os.path.isabs(filename) or ".." in filename.split(os.path.sep):
        abort(403)

    safe_name = secure_filename(filename)
    requested = (document_dir / safe_name).resolve()

    if not _is_safe_path(document_dir, requested):
        abort(403)

    if not requested.is_file():
        abort(404)

    mime_type, _ = mimetypes.guess_type(str(requested))
    if not mime_type:
        mime_type = "application/octet-stream"

    if mime_type not in ALLOWED_MIME_TYPES:
        abort(403)

    response = send_file(str(requested), mimetype=mime_type, conditional=True)
    response.headers["Cache-Control"] = "public, max-age=86400, immutable"
    return response


@bp.route("/certs/<path:filename>")
@login_required
def teacher_certificate(filename):
    """Serve teacher certificates safely from TEACHER_CERTS_DIR."""
    base_dir = Path(current_app.config["TEACHER_CERTS_DIR"]).resolve()

    if os.path.isabs(filename) or ".." in filename.split(os.path.sep):
        abort(403)

    safe_name = secure_filename(filename)
    requested = (base_dir / safe_name).resolve()

    if not _is_safe_path(base_dir, requested):
        abort(403)

    if not requested.is_file():
        abort(404)

    mime_type, _ = mimetypes.guess_type(str(requested))
    if not mime_type:
        mime_type = "application/octet-stream"

    if mime_type not in ALLOWED_CERT_MIME_TYPES:
        abort(403)

    response = send_file(str(requested), mimetype=mime_type, conditional=True)
    response.headers["Cache-Control"] = "public, max-age=86400, immutable"
    return response


def save_teacher_photo(file_storage, *, output_size=(600, 600)):
    """Save an uploaded teacher photo to TEACHER_PHOTOS_DIR and return filename."""
    filename = secure_filename(file_storage.filename or "")
    if not filename:
        raise ValueError("No filename provided")

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise ValueError("Unsupported file extension")

    random_name = secrets.token_hex(12) + ext
    document_dir = Path(current_app.config["TEACHER_PHOTOS_DIR"])
    document_dir.mkdir(parents=True, exist_ok=True)

    save_path = document_dir / random_name

    img = Image.open(file_storage.stream)
    img = img.convert("RGB")
    img.thumbnail(output_size)
    img.save(save_path, quality=85)

    return random_name


def save_teacher_certificate(file_storage):
    """
    Save an uploaded certificate/document into TEACHER_CERTS_DIR.
    Returns a randomized filename (store just the filename in DB).
    """
    filename = secure_filename(file_storage.filename or "")
    if not filename:
        raise ValueError("No filename provided")

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_CERT_EXTS:
        raise ValueError("Unsupported certificate type. Allowed: PDF/JPG/PNG")

    random_name = f"cert_{secrets.token_hex(12)}{ext}"
    base_dir = Path(current_app.config["TEACHER_CERTS_DIR"])
    base_dir.mkdir(parents=True, exist_ok=True)
    save_path = base_dir / random_name

    # Save directly (no image processing; certificates can be PDFs/images)
    file_storage.save(str(save_path))
    return random_name


@bp.route("/<int:teacher_id>/certs/<path:filename>/delete", methods=["POST"])
@login_required
@role_required(["admin", "headteacher"])
def delete_certificate(teacher_id, filename):
    """
    Manually delete one certificate and remove it from teacher.certificate_paths.
    """
    teacher = Teacher.query.get_or_404(teacher_id)
    safe_name = secure_filename(os.path.basename(filename))

    current_files = [p for p in (teacher.certificate_paths or "").split(",") if p]
    if safe_name not in current_files:
        flash("Certificate not found.", "warning")
        return redirect(url_for("teachers.detail", teacher_id=teacher_id))

    cert_path = Path(current_app.config["TEACHER_CERTS_DIR"]) / safe_name
    try:
        if cert_path.exists():
            cert_path.unlink()
    except Exception:
        current_app.logger.exception("Could not delete certificate file")
        flash("Could not delete certificate file (it may be in use).", "danger")
        return redirect(url_for("teachers.detail", teacher_id=teacher_id))

    # Update DB field
    current_files.remove(safe_name)
    teacher.certificate_paths = ",".join(current_files) if current_files else None
    db.session.commit()

    flash("Certificate deleted.", "success")
    return redirect(url_for("teachers.detail", teacher_id=teacher_id))


@bp.route("/<int:teacher_id>/delete", methods=["POST"])
@login_required
@role_required(["admin"])
def delete(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)

    # Delete associated files
    if teacher.photo_path:
        photo_path = Path(current_app.config["TEACHER_PHOTOS_DIR"]) / teacher.photo_path
        if photo_path.exists():
            try:
                photo_path.unlink()
            except Exception:
                current_app.logger.warning(
                    "Could not delete photo file during teacher delete."
                )

    if teacher.certificate_paths:
        for cert_path in (p for p in teacher.certificate_paths.split(",") if p):
            full_path = Path(current_app.config["TEACHER_CERTS_DIR"]) / cert_path
            if full_path.exists():
                try:
                    full_path.unlink()
                except Exception:
                    current_app.logger.warning(
                        "Could not delete certificate during teacher delete."
                    )

    db.session.delete(teacher)
    db.session.commit()
    flash("Teacher deleted successfully!", "success")
    backup_database()
    return redirect(url_for("teachers.edit"))
