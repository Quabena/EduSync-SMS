from flask import render_template, redirect, request, jsonify, url_for, flash
from flask_login import login_required, current_user
from app.decorators import role_required
from app import db
from app.models import Classroom, MoodEntry
from app.mood import bp
from app.utils.mood import record_classroom_mood, get_classroom_mood
from datetime import datetime


@bp.route("/track/<int:class_id>", methods=["GET", "POST"])
@login_required
@role_required(["admin", "teacher"])
def track(class_id):
    class_ = Classroom.query.get_or_404(class_id)

    if request.method == "POST":
        notes = request.form.get("notes", "")
        entry = record_classroom_mood(class_id, notes)
        flash("Mood recorded successfully!", "success")
        return redirect(url_for("mood.track", class_id=class_id))

    # Getting mood history
    mood_data = get_classroom_mood(class_id)

    return render_template("mood/track.html", class_=class_, mood_data=mood_data)


# Mood history
@bp.route("/history/<int:class_id>")
@login_required
@role_required(["admin", "teacher", "headteacher"])
def history(class_id):
    class_ = Classroom.query.get_or_404(class_id)
    mood_data = get_classroom_mood(class_id, days=90)
    return render_template("mood/history.html", class_=class_, mood_data=mood_data)
