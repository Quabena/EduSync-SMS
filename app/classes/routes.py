from flask import render_template, flash, redirect, url_for, request
from flask_login import login_required
from app import db
from app.decorators import role_required
from app.models import Class, Teacher
from app.classes.forms import ClassForm
from app.classes import bp
from app.utils.storage import backup_database


@bp.route("/")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def index():
    classes = Class.query.all()
    return render_template("classes/list.html", classes=classes)


@bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required(["admin", "headteacher"])
def create():
    form = ClassForm()
    if form.validate_on_submit():
        class_ = Class(
            name=f"{form.level.data} {form.section.data}",
            level=form.level.data,
            section=form.section.data,
        )
        teacher = Teacher.query.get(form.teacher_id.data)
        if teacher:
            class_.teachers.append(teacher)

        db.session.add(class_)
        db.session.commit()
        flash("Class created successfully!", "success")
        return redirect(url_for("classes.index"))

    return render_template("classes/create.html", form=form, title="Create Class")


@bp.route("/<int:class_id>")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def detail(class_id):
    class_ = Class.query.get_or_404(class_id)

    # Assuming you have relationships in models.py:
    # class_.teachers (many-to-many)
    # class_.students (one-to-many)
    teachers = class_.teachers
    students = class_.students

    return render_template(
        "classes/detail.html",
        class_=class_,
        teachers=teachers,
        students=students,
    )


@bp.route("/<int:class_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(["admin", "headteacher"])
def edit(class_id):
    class_ = Class.query.get_or_404(class_id)
    form = ClassForm(obj=class_)

    if form.validate_on_submit():
        class_.name = f"{form.level.data} {form.section.data}"
        class_.level = form.level.data
        class_.section = form.section.data

        class_.teachers.clear()
        teacher = Teacher.query.get(form.teacher_id.data)
        if teacher:
            class_.teachers.append(teacher)

        db.session.commit()
        flash("Class successfully updated!", "success")
        backup_database()
        return redirect(url_for("classes.index"))

    return render_template(
        "classes/edit.html", form=form, title="Edit Class", class_=class_
    )


@bp.route("/<int:class_id>/delete", methods=["POST"])
@login_required
@role_required(["admin"])
def delete(class_id):
    class_ = Class.query.get_or_404(class_id)
    db.session.delete(class_)
    db.session.commit()
    flash("Class successfully deleted!", "success")
    backup_database()
    return redirect(url_for("classes.index"))
