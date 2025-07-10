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
    send_from_directory,
)
import csv
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
    if form.validate_on_submit():

        # Handling file upload
        photo_path = None
        if form.photo.data:
            photo = form.photo.data
            filename = secure_filename(photo.filename)

            # DOCUMENT_DIR is a Path object
            save_path = current_app.config["DOCUMENT_DIR"] / filename
            save_path.parent.mkdir(parents=True, exist_ok=True)  # Just in case

            print("Save path:", save_path)
            print("Exists:", save_path.parent.exists())

            photo.save(str(save_path))  # Save expects string path

            # Store relative path from BASE_DIR
            rel_path = save_path.relative_to(current_app.config["BASE_DIR"])
            photo_path = str(rel_path)

        student = Student(
            first_name=form.first_name.data,
            middle_name=form.middle_name.data,
            surname=form.surname.data,
            gender=form.gender.data,
            date_of_birth=form.date_of_birth.data,
            hometown=form.hometown.data,
            father_name=form.father_name.data,
            mother_name=form.mother_name.data,
            guardian=form.guardian_name.data,
            guardian_contact=form.guardian_contact.data,
            medical_records=form.medical_records.data,
            photo_path=photo_path,
            class_id=form.class_id.data,
        )

        db.session.add(student)
        db.session.commit()

        # Generating QR Code
        generate_student_qr(student.id)

        flash("Student created successfully!", "success")
        backup_database()  # Backing up after important changes
        return redirect(url_for("students.detail", student_id=student.id))
    return render_template("students/create.html", form=form)


# Student detail route
@bp.route("/<int:student_id>")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def detail(student_id):
    student = Student.query.get_or_404(student_id)
    return render_template("students/detail.html", student=student)


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
            if student.photo_path:
                old_path = os.path.join(
                    current_app.config["BASE_DIR"], student.photo_path
                )
                if os.path.exists(old_path):
                    os.remove(old_path)

            # Save new photo
            photo = form.photo.data
            filename = secure_filename(photo.filename)
            save_path = os.path.join(current_app.config["DOCUMENT_DIR"], filename)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            photo.save(save_path)

            # Store relative path from BASE_DIR (e.g. student_photos/filename.jpg)
            student.photo_path = os.path.relpath(
                save_path, start=current_app.config["BASE_DIR"]
            )

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

        db.session.commit()
        flash("Student info successfully updated!", "success")
        backup_database()
        return redirect(url_for("students.detail", student_id=student.id))

    return render_template("students/edit.html", form=form, student=student)


@bp.route("/photo/<path:filename>")
@login_required
def student_photo(filename):
    full_path = os.path.join(current_app.config["BASE_DIR"])
    directory = os.path.dirname(full_path)
    file = os.path.basename(full_path)
    return send_from_directory(directory, file)


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
