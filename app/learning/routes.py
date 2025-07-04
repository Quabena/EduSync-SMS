from flask import render_template, request, jsonify, flash, redirect
from flask_login import login_required, current_user
from app.decorators import role_required
from app.models import Student
from app.learning import bp
from app.utils.learning import generate_learning_path


@bp.route("/student/<int:student_id>")
@login_required
@role_required(["teacher", "headteacher"])
def student_path(student_id):
    student = Student.query.get_or_404(student_id)
    learning_path = generate_learning_path(student_id)
    return render_template(
        "learning/path.html", student=student, learning_path=learning_path
    )


@bp.route("/generate/<int:student_id>", methods=["POST"])
@login_required
@role_required(["teacher", "headteacher"])
def generate_pdf(student_id):
    # I will implement the PDF generation here later
    flash("PDF learning path generated!", "success")
    return redirect("learning.student_path")  # student_id=student_id)
