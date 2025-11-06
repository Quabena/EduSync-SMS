from flask import render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from app import db
from app.decorators import role_required
from app.models import Subject, Student
from app.subjects import bp
from app.utils.storage import backup_database


@bp.route("/")
@login_required
@role_required(["admin", "teacher"])
def index():
    subjects = Subject.query.all()
    active_students_count = Student.query.filter_by(status="active").count()

    return render_template(
        "subjects/list.html",
        subjects=subjects,
        active_students_count=active_students_count,
    )


@bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required(["admin", "teacher"])
def create():
    if request.method == "POST":
        name = request.form["name"]
        code = request.form["code"]

        subject = Subject(name=name, code=code)
        db.session.add(subject)
        db.session.commit()
        flash("Subject created successfully!", "success")
        backup_database()
        return redirect(url_for("subjects.index"))

    return render_template("subjects/create.html")


@bp.route("/<int:subject_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(["admin", "headteacher"])
def edit(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    active_students_count = Student.query.filter_by(status="active").count()

    if request.method == "POST":
        subject.name = request.form["name"]
        subject.code = request.form["code"]
        db.session.commit()
        flash("Subject successfully updated!", "success")
        backup_database()
        return redirect(url_for("subjects.index"))

    return render_template(
        "subjects/edit.html",
        subject=subject,
        active_students_count=active_students_count,
    )


@bp.route("/<int:subject_id>/delete", methods=["POST"])
@login_required
@role_required(["admin"])
def delete(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    db.session.delete(subject)
    db.session.commit()
    flash("Subject successfully deleted!", "success")
    backup_database()
    return redirect(url_for("subjects.index"))
