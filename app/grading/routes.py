from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.decorators import role_required
from app import db
from app.models import Assignment, StudentAssignment, Subject
from app.grading import bp
from app.utils.grading import process_assignement
import os
from werkzeug.utils import secure_filename


@bp.route("/assignments")
@login_required
@role_required(["teacher"])
def list_assignments():
    assignments = Assignment.query.filter_by(teacher_id=current_user.id).all()
    return render_template("grading/list.html", assignments=assignments)


@bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required(["teacher"])
def create_assignment():
    if request.method == "POST":
        # Creating a simplified assignment creation
        title = request.form["title"]
        subject_id = request.form["subject_id"]
        questions = {}

        # Processing questions (in a real system, this would be more complex)
        for i in range(1, int(request.form["questions"]) + 1):
            questions[i] = {
                "text": request.form[f"q{i}_text"],
                "answer": request.form[f"q{i}_answer"],
            }

        assignment = Assignment(
            title=title,
            subject_id=subject_id,
            teacher_id=current_user.id,
            questions=questions,
        )
        db.session.add(assignment)
        db.session.commit()
        flash("Assignment created!", "success")
        return redirect(url_for("grading.list_assignments"))

    subjects = Subject.query.all()
    return render_template("grading/create.html", subjects=subjects)


@bp.route("/grade/<int:assignment_id>", methods=["GET", "POST"])
@login_required
@role_required(["teacher"])
def grade_assignment(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)

    if request.method == "POST":
        student_id = request.form["student_id"]
        image = request.files["submission"]

        if image:
            # Saving submission
            filename = secure_filename(f"submission_{student_id}_{assignment_id}.png")
            save_path = os.path.join(
                current_app.config["DOCUMENT_DIR"], "submissions", filename
            )
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            image.save(save_path)

            # Processing with OCR
            score, feedback = process_assignement(save_path, assignment_id)

            # Savign the results
            submission = StudentAssignment(
                student_id=student_id,
                assignment_id=assignment_id,
                submission_path=filename,
                score=score,
                feedback=feedback,
            )
            db.session.add(submission)
            db.session.commit()
            flash("Assignment graded successfully!", "success")
            return redirect(
                url_for("grading.view_submission", submission_id=submission.id)
            )

    return render_template("grading/grade.html", assignment=assignment)


@bp.route("/submission/<int:submission_id>")
@login_required
@role_required(["teacher"])
def view_submission(submission_id):
    submission = StudentAssignment.query.get_or_404(submission_id)
    return render_template("grading/submission.html", submission=submission)
