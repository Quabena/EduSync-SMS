from flask import render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from app import db
from app.auth.forms import LoginForm, RegistrationForm
from app.models import User
from app.auth import bp


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if user and user.check_password(form.password.data):
            login_user(user, remember=True)
            flash("Login successful!", "success")
            return redirect(url_for("main.index"))
        else:
            flash("Invalid username or password", "danger")

    return render_template("auth/login.html", title="Sign In", form=form)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if not current_user.is_authenticated or current_user.role != "admin":
        flash("You do not have permission to access this page", "danger")
        return redirect(url_for("main.index"))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            role=form.role.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("User registered successfully!", "success")
        return redirect(url_for("main.index"))

    return render_template("auth/register.html", title="Register User", form=form)


@bp.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out", "info")
    return redirect(url_for("auth.login"))
