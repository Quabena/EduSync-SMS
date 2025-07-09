import os
from flask import render_template, flash, redirect, url_for, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
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
        # Handle file uploads
        photo_path = None
        if form.photo.data:
            photo = form.photo.data
            filename = secure_filename(
                f"teacher_photo_{datetime.now().timestamp()}_{photo.filename}"
            )
            photo_path = os.path.join("teacher_photos", filename)
            save_path = os.path.join(current_app.config["DOCUMENT_DIR"], photo_path)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            photo.save(save_path)

        certificate_paths = []
        for cert in form.certificates.data:
            if cert:
                filename = secure_filename(
                    f"cert_{datetime.now().timestamp()}_{cert.filename}"
                )
                cert_path = os.path.join("teacher_certs", filename)
                save_path = os.path.join(current_app.config["DOCUMENT_DIR"], cert_path)
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                cert.save(save_path)
                certificate_paths.append(cert_path)

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
            photo_path=photo_path,
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
    form.specialization_id.choices = [
        (s.id, s.name) for s in Subject.query.order_by(Subject.name).all()  # type: ignore
    ]
    form.assigned_classes.choices = [
        (c.id, c.name) for c in Class.query.order_by(Class.name).all()
    ]

    # Pre-select assigned classes
    form.assigned_classes.data = [c.id for c in teacher.classes]

    if form.validate_on_submit():
        # Handle file uploads
        if form.photo.data:
            # Delete old photo if exists
            if teacher.photo_path:
                old_path = os.path.join(
                    current_app.config["DOCUMENT_DIR"], teacher.photo_path
                )
                if os.path.exists(old_path):
                    os.remove(old_path)

            photo = form.photo.data
            filename = secure_filename(
                f"teacher_photo_{datetime.now().timestamp()}_{photo.filename}"
            )
            photo_path = os.path.join("teacher_photos", filename)
            save_path = os.path.join(current_app.config["DOCUMENT_DIR"], photo_path)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            photo.save(save_path)
            teacher.photo_path = photo_path

        certificate_paths = []
        if form.certificates.data and any(form.certificates.data):
            # Delete old certificates
            if teacher.certificate_paths:
                for cert_path in teacher.certificate_paths.split(","):
                    old_path = os.path.join(
                        current_app.config["DOCUMENT_DIR"], cert_path
                    )
                    if os.path.exists(old_path):
                        os.remove(old_path)

            for cert in form.certificates.data:
                if cert:
                    filename = secure_filename(
                        f"cert_{datetime.now().timestamp()}_{cert.filename}"
                    )
                    cert_path = os.path.join("teacher_certs", filename)
                    save_path = os.path.join(
                        current_app.config["DOCUMENT_DIR"], cert_path
                    )
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    cert.save(save_path)
                    certificate_paths.append(cert_path)
            teacher.certificate_paths = ",".join(certificate_paths)

        # Update fields
        form.populate_obj(teacher)

        # Update classes
        teacher.classes = []
        for class_id in form.assigned_classes.data:
            class_ = Class.query.get(class_id)
            if class_:
                teacher.classes.append(class_)

        db.session.commit()
        flash("Teacher updated successfully!", "success")
        backup_database()
        return redirect(url_for("teachers.detail", teacher_id=teacher.id))

    return render_template("teachers/edit.html", form=form, teacher=teacher)


@bp.route("/<int:teacher_id>/delete", methods=["POST"])
@login_required
@role_required(["admin"])
def delete(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)

    # Delete associated files
    if teacher.photo_path:
        photo_path = os.path.join(
            current_app.config["DOCUMENT_DIR"], teacher.photo_path
        )
        if os.path.exists(photo_path):
            os.remove(photo_path)

    if teacher.certificate_paths:
        for cert_path in teacher.certificate_paths.split(","):
            full_path = os.path.join(current_app.config["DOCUMENT_DIR"], cert_path)
            if os.path.exists(full_path):
                os.remove(full_path)

    db.session.delete(teacher)
    db.session.commit()
    flash("Teacher deleted successfully!", "success")
    backup_database()
    return redirect(url_for("teachers.index"))
