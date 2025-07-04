from flask import render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.decorators import role_required
from app.models import Class, Teacher
from app.classes.forms import ClassForm
from app.classes import bp


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
            name=f"{form.level.data}{form.section.data}",
            level=form.level.data,
            section=form.section.data,
        )
        # Add teacher via association
        teacher = Teacher.query.get(form.teacher_id.data)
        if teacher:
            class_.teachers.append(teacher)

        db.session.add(class_)
        db.session.commit()
        flash("Class created successfully!", "success")
        return redirect(url_for("classes.index"))

    return render_template("classes/create.html", form=form)


@bp.route("/<int:class_id>")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def detail(class_id):
    class_ = Class.query.get_or_404(class_id)
    return render_template("classes/detail.html", class_=class_)
