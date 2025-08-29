import os
from io import StringIO
import qrcode
from flask import (
    render_template,
    flash,
    redirect,
    url_for,
    request,
    current_app,
    send_file,
    Response,
    abort,
    send_from_directory,
    make_response,
)
import csv
from pathlib import Path
from PIL import Image
import secrets
import mimetypes
from config import Config
from datetime import datetime
from flask_login import login_required, current_user
import qrcode.constants
from werkzeug.utils import secure_filename
from app import db
from app.decorators import role_required
from app.models import Student, Class
from app.students.forms import StudentForm
from app.students import bp
from app.utils.storage import backup_database
from datetime import date


# Generating student QR code
def generate_student_qr(student_id):
    student = Student.query.get(student_id)
    if not student:
        return None

    # Creating QR Code data
    qr_data = f"STUDENT:{student.id}:{student.full_name.replace(' ', '_')}"

    # Generating QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Saving to file
    qr_filename = f"student_{student.full_name}.png"
    qr_path = os.path.join(current_app.config["QR_DIR"], qr_filename)
    img.save(qr_path)  # type: ignore

    # Updating student with QR path
    student.qr_path = qr_filename
    db.session.commit()


# Root route for students (lists)
@bp.route("/")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def index():
    students = Student.query.all()
    return render_template("students/list.html", students=students)


# Route to add student
@bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required(["admin", "headteacher"])
def create():
    form = StudentForm()
    # if not form:
    #     return render_template("students/create.html", form=form)

    # Allowed types / extensions
    ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

    if form.validate_on_submit():
        photo_filename = None
        saved_path = None

        # 1) Handle uploaded photo
        if form.photo.data:
            file = form.photo.data

            # 1.a) basic content-type check from upload
            content_type = getattr(file, "content_type", None)
            if content_type not in ALLOWED_MIME_TYPES:
                flash("Unsupported image type. Use JPG/PNG/GIF/WEBP.", "danger")
                return render_template("students/create.html", form=form)

            # 1.b) secure filename and extension
            original_name = secure_filename(file.filename or "")
            if not original_name:
                flash("Invalid file name.", "danger")
                return render_template("students/create.html", form=form)

            ext = Path(original_name).suffix.lower()
            if ext not in ALLOWED_EXTS:
                flash("Unsupported file extension.", "danger")
                return render_template("students/create.html", form=form)

            # 1.c) generate randomized filename
            photo_filename = f"{secrets.token_hex(12)}{ext}"

            # 1.d) prepare save directory (DOCUMENT_DIR should be a Path or str)
            doc_dir = current_app.config.get("DOCUMENT_DIR")
            if not doc_dir:
                flash("Server misconfiguration: no DOCUMENT_DIR.", "danger")
                return render_template("students/create.html", form=form)

            # ensure Path
            doc_dir = Path(doc_dir)
            try:
                doc_dir.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                current_app.logger.exception("Failed to create document dir")
                flash("Server error when preparing storage.", "danger")
                return render_template("students/create.html", form=form)

            saved_path = doc_dir / photo_filename

            # 1.e) verify image with Pillow and save safely (resize/normalize)
            try:
                # Pillow can validate and process the image
                img = Image.open(file)
                img.verify()  # raises if broken
                file.stream.seek(0)  # reset stream after verify

                img = Image.open(file)  # reopen for processing
                img = img.convert("RGB")  # normalize to RGB (drop alpha)
                max_size = (1000, 1000)  # tweak as needed
                img.thumbnail(max_size)
                img.save(saved_path, quality=85)
            except Exception as exc:
                # delete partial file if created
                if saved_path.exists():
                    try:
                        saved_path.unlink()
                    except Exception:
                        current_app.logger.exception("Could not remove invalid image")
                current_app.logger.exception("Invalid image upload")
                flash("Uploaded file is not a valid image.", "danger")
                return render_template("students/create.html", form=form)

        # 2) build the Student model; store only filename (photo_filename) or None
        student = Student(
            first_name=form.first_name.data,
            middle_name=form.middle_name.data,
            surname=form.surname.data,
            gender=form.gender.data,
            date_of_birth=form.date_of_birth.data,
            hometown=form.hometown.data,
            father_name=form.father_name.data,
            mother_name=form.mother_name.data,
            guardian_name=form.guardian_name.data,
            guardian_contact=form.guardian_contact.data,
            medical_records=form.medical_records.data,
            photo_path=photo_filename,  # store just the filename
            class_id=form.class_id.data,
        )

        # 3) save to DB with safe commit and cleanup on failure
        try:
            db.session.add(student)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception("Failed to create student")
            # If we saved a file already, remove it because DB failed
            if saved_path and saved_path.exists():
                try:
                    saved_path.unlink()
                except Exception:
                    current_app.logger.exception(
                        "Failed to remove photo after DB error"
                    )
            flash("Failed to create student. Try again.", "danger")
            return render_template("students/create.html", form=form)

        # 4) post-commit tasks (QR generation, backups) — keep them non-blocking if possible
        try:
            generate_student_qr(student.id)
        except Exception:
            current_app.logger.exception("Failed to generate QR for student")

        try:
            backup_database()
        except Exception:
            current_app.logger.exception("Backup failed")

        flash("Student created successfully!", "success")
        return redirect(url_for("students.detail", student_id=student.id))

    else:
        current_app.logger.error("Form validation failed: %s", form.errors)

    # GET or invalid form
    return render_template("students/create.html", form=form)


# Student detail route
@bp.route("/<int:student_id>")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def detail(student_id):
    student = Student.query.get_or_404(student_id)
    return render_template(
        "students/detail.html", student=student, current_date=date.today()
    )


# Edit Route
@bp.route("/<int:student_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(["admin", "headteacher"])
def edit(student_id):
    student = Student.query.get_or_404(student_id)
    form = StudentForm(obj=student)
    form.class_id.choices = [
        (c.id, c.name) for c in Class.query.order_by(Class.name).all()
    ]

    if form.validate_on_submit():
        if form.photo.data:
            # delete previous photo if present (safe)
            if student.photo_path:
                document_dir = Path(current_app.config["DOCUMENT_DIR"]).resolve()
                old = (document_dir / student.photo_path).resolve()
                try:
                    # ensure old is inside document_dir
                    old.relative_to(document_dir)
                    if old.exists():
                        old.unlink()
                except Exception:
                    # log/warn but don't crash the edit flow
                    current_app.logger.warning(
                        "Tried to delete a photo outside DOCUMENT_DIR or missing"
                    )

            # Save new photo using helper
            try:
                new_filename = save_student_photo(form.photo.data)
                student.photo_path = new_filename
            except ValueError as e:
                flash(str(e), "danger")
                return redirect(url_for("students.edit", student_id=student.id))

        student.first_name = form.first_name.data
        student.middle_name = form.middle_name.data
        student.surname = form.surname.data
        student.gender = form.gender.data
        student.date_of_birth = form.date_of_birth.data
        student.hometown = form.hometown.data
        student.father_name = form.father_name.data
        student.mother_name = form.mother_name.data
        student.guardian_name = form.guardian_name.data
        student.guardian_contact = form.guardian_contact.data
        student.medical_records = form.medical_records.data
        student.class_id = form.class_id.data
        student.religion = form.religion.data
        student.admission_date = form.admission_date.data
        student.height = form.height.data
        student.weight = form.weight.data

        db.session.commit()
        flash("Student info successfully updated!", "success")
        backup_database()
        return redirect(url_for("students.detail", student_id=student.id))

    return render_template("students/edit.html", form=form, student=student)


# Allowed MIME types for images
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _is_safe_path(base_dir: Path, path: Path) -> bool:
    """Return True if path is inside base_dir."""
    try:
        path.resolve().relative_to(base_dir.resolve())
        return True
    except Exception:
        return False


@bp.route("/photos/<path:filename>")
@login_required
def student_photo(filename):
    """
    Serve student photos from DOCUMENT_DIR in a safe way.
    Example URL: url_for('students.student_photo', filename='abc123.jpg')
    """
    document_dir = Path(current_app.config["DOCUMENT_DIR"]).resolve()

    # Prevent absolute or traversal requests
    if os.path.isabs(filename) or ".." in filename.split(os.path.sep):
        abort(403)

    # secure_filename will strip unsafe characters; but we still must resolve and check
    safe_name = secure_filename(filename)
    requested = (document_dir / safe_name).resolve()

    # ensure requested is under document_dir (prevent traversal)
    if not _is_safe_path(document_dir, requested):
        abort(403)

    if not requested.is_file():
        abort(404)

    mime_type, _ = mimetypes.guess_type(str(requested))
    if not mime_type:
        mime_type = "application/octet-stream"

    if mime_type not in ALLOWED_MIME_TYPES:
        abort(403)

    # Use send_file on the resolved path so Flask/Werkzeug handles conditional requests
    response = send_file(str(requested), mimetype=mime_type, conditional=True)
    # Cache for 1 day; you can increase if images are immutable
    response.headers["Cache-Control"] = "public, max-age=86400, immutable"
    return response


def save_student_photo(file_storage, *, output_size=(600, 600)):
    """
    Save an uploaded image (werkzeug FileStorage) into DOCUMENT_DIR.
    Returns the saved filename (string) to store in the DB (do NOT store full path).
    - Generates random hex name
    - Validates extension
    - Resizes using PIL.thumbnail
    """
    filename = secure_filename(file_storage.filename or "")
    if not filename:
        raise ValueError("No filename provided")

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise ValueError("Unsupported file extension")

    random_name = secrets.token_hex(12) + ext
    document_dir = Path(current_app.config["DOCUMENT_DIR"])
    document_dir.mkdir(parents=True, exist_ok=True)

    save_path = document_dir / random_name

    # open via stream to avoid saving original raw first
    img = Image.open(file_storage.stream)
    img.convert("RGB")  # normalize
    img.thumbnail(output_size)
    img.save(save_path, quality=85)

    return random_name


# Delete Route
@bp.route("/<int:student_id>/delete", methods=["POST"])
@login_required
@role_required(["admin"])
def delete(student_id):
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    flash("Student deleted successfully!", "success")
    backup_database()
    return redirect(url_for("students.index"))


# Bulk CSV Export
@bp.route("/export")
@login_required
@role_required(["admin", "headteacher"])
def export_csv():
    # Creating a CSV in memory
    output = StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(
        [
            "id",
            "first_name",
            "middle_name",
            "surname",
            "gender",
            "date_of_birth",
            "hometown",
            "father_name",
            "mother_name",
            "guardian_name",
            "guardian_contact",
            "medical_records",
            "class_id",
        ]
    )

    # Data
    students = Student.query.all()
    for s in students:
        writer.writerow(
            [
                s.id,
                s.first_name,
                s.middle_name or "",
                s.surname,
                s.gender,
                s.date_of_birth.strftime("%Y-%m-%d"),
                s.hometown or "",
                s.father_name or "",
                s.mother_name or "",
                s.guardian_name or "",
                s.guardian_contact or "",
                s.medical_records or "",
                s.class_id or "",
            ]
        )

    # Creating Response
    output.seek(0)
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=students.csv"},
    )


# Bulk CSV Import
@bp.route("/import", methods=["GET", "POST"])
@login_required
@role_required(["admin", "headteacher"])
def import_csv():
    if request.method == "POST":
        if "csv_file" not in request.files:
            flash("No file part", "danger")
            return redirect(request.url)

        file = request.files["csv_file"]
        if file.filename == "":
            flash("No selected file", "danger")
            return redirect(request.url)

        if file and file.filename.endswith(".csv"):  # type: ignore
            stream = StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_reader = csv.DictReader(stream)

            for row in csv_reader:
                # Parsing data
                dob = datetime.strptime(row["date_of_birth"], "%Y-%m-%d").date()

                student = Student(
                    first_name=row["first_name"],
                    middle_name=row["middle_name"] or None,
                    surname=row["surname"],
                    gender=row["gender"],
                    date_of_birth=row["date_of_birth"],
                    hometown=row["hometown"] or None,
                    father_name=row["father_name"] or None,
                    mother_name=row["mother_name"] or None,
                    guardian_name=row["guardian_name"] or None,
                    guardian_contact=row["guardian_contact"] or None,
                    medical_records=row["medical_records"] or None,
                    class_id=row["class_id"] or None,
                )
                db.session.add(student)

            db.session.commit()
            flash("Students imported successfully!", "success")
            return redirect(url_for("students.index"))
    return render_template("students/import.html")
