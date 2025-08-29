import json
from flask import (
    render_template,
    request,
    jsonify,
    flash,
    redirect,
    url_for,
    current_app,
)
from flask_login import login_required, current_user
from app import db
from app.models import (
    TeacherSubjectClass,
    Class,
    Subject,
    Teacher,
    Student,
    TermScore,
)
from app.exams_grading import bp
from app.decorators import role_required
from sqlalchemy import and_, or_


@bp.route("/", methods=["GET"])
@login_required
@role_required(["admin", "headteacher", "teacher"])
def index():
    """
    Grading dashboard. Shows shortcuts and summary data.
    Admin/headteacher sees full dashboard; teachers see only their assignments.
    """
    # Supply classes/subjects for quick jump form
    classes = Class.query.order_by(Class.name).all()
    subjects = Subject.query.order_by(Subject.name).all()  # type: ignore

    # Fix the query to work with the new schema
    recent_assignments = (
        TeacherSubjectClass.query.join(Class, TeacherSubjectClass.class_id == Class.id)
        .order_by(Class.name.desc())
        .limit(8)
        .all()
    )

    return render_template(
        "exams_grading/index.html",
        classes=classes,
        subjects=subjects,
        recent_assignments=recent_assignments,
    )


@bp.route("/assign", methods=["GET", "POST"])
@login_required
@role_required(["admin", "headteacher"])
def assign_teacher_subject():
    """
    GET: render assignment form.
    POST: create new TeacherSubjectClass assignment (returns JSON for AJAX).
    """
    assignments = TeacherSubjectClass.query.filter_by(is_active=True).all()

    if request.method == "POST":
        try:
            teacher_id = int(request.form.get("teacher_id", 0))
            subject_id = int(request.form.get("subject_id", 0))
            class_id = int(request.form.get("class_id", 0))
        except ValueError:
            return jsonify({"status": "error", "message": "Invalid IDs"}), 400

        if not (teacher_id and subject_id and class_id):
            return jsonify({"status": "error", "message": "Missing fields"}), 400

        existing = TeacherSubjectClass.query.filter_by(
            subject_id=subject_id, class_id=class_id, is_active=True
        ).first()

        if existing:
            teacher_name = existing.teacher.full_name if existing.teacher else "Unknown"
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"Class already assigned to {teacher_name}",
                        "assignment_data": {
                            "teacher_id": existing.teacher_id,
                            "subject_id": existing.subject_id,
                            "class_id": existing.class_id,
                        },
                    }
                ),
                409,
            )

        new_assignment = TeacherSubjectClass(
            teacher_id=teacher_id,
            subject_id=subject_id,
            class_id=class_id,
            is_active=True,
        )
        db.session.add(new_assignment)
        db.session.commit()

        return jsonify(
            {"status": "success", "message": "Assignment made successfully!"}
        )

    teachers = Teacher.query.order_by(Teacher.surname, Teacher.first_name).all()
    subjects = Subject.query.order_by(Subject.name).all()  # type: ignore
    classes = Class.query.order_by(Class.name).all()

    return render_template(
        "exams_grading/assign_teacher_subject.html",
        teachers=teachers,
        subjects=subjects,
        classes=classes,
    )


@bp.route("/reassign", methods=["POST"])
@login_required
@role_required(["admin", "headteacher"])
def reassign_teacher_subject():
    """
    Reassign an existing active assignment to a new teacher.
    (POST only, returns JSON)
    """
    from flask_wtf.csrf import validate_csrf

    try:
        validate_csrf(request.form.get("csrf_token"))
    except:
        return jsonify({"status": "error", "message": "Invalid CSRF token"}), 400

    assignment_id = request.form.get("assignment_id")
    new_teacher_id = request.form.get("teacher_id")

    if not (assignment_id and new_teacher_id):
        return jsonify({"status": "error", "message": "Missing parameters"}), 400

    assignment = TeacherSubjectClass.query.get(assignment_id)
    if not assignment:
        return jsonify({"status": "error", "message": "Assignment not found"}), 404

    # deactivate old assignment
    assignment.is_active = False

    # create new active assignment
    new_assignment = TeacherSubjectClass(
        teacher_id=int(new_teacher_id),
        subject_id=assignment.subject_id,
        class_id=assignment.class_id,
        is_active=True,
    )
    db.session.add(new_assignment)
    db.session.commit()

    return jsonify({"status": "success", "message": "Reassignment successful!"})


@bp.route("/grade/<int:class_id>/<int:subject_id>/<term>/<year>", methods=["GET"])
@login_required
@role_required(["admin", "headteacher", "teacher"])
def grading_page(class_id, subject_id, term, year):
    """
    Render the grading page for the given class/subject/term/year.
    """
    # Permissions check
    if not has_grading_access(current_user, class_id, subject_id):
        flash("You do not have permission to grade this class/subject!", "danger")
        return redirect(url_for("exams_grading.index"))

    class_ = Class.query.get_or_404(class_id)
    subject = Subject.query.get_or_404(subject_id)

    # get teacher assignment (active)
    assignment = TeacherSubjectClass.query.filter_by(
        class_id=class_id, subject_id=subject_id, is_active=True
    ).first()

    if not assignment or not assignment.teacher:
        flash("No teacher assigned to this class/subject combination!", "warning")
        return redirect(url_for("exams_grading.index"))

    # students in this class
    students = (
        Student.query.filter_by(class_id=class_id)
        .order_by(Student.surname, Student.first_name)
        .all()
    )

    # existing term scores map
    term_scores = {}
    if students:
        student_ids = [s.id for s in students]
        scores = TermScore.query.filter(
            TermScore.student_id.in_(student_ids),
            TermScore.subject_id == subject_id,
            TermScore.class_id == class_id,
            TermScore.term == term,
            TermScore.year == year,
        ).all()
        for s in scores:
            term_scores[s.student_id] = s

    return render_template(
        "exams_grading/grading.html",
        class_=class_,
        subject=subject,
        teacher=assignment.teacher,
        students=students,
        term_scores=term_scores,
        term=term,
        year=year,
    )


@bp.route("/save", methods=["POST"])
@login_required
def save_grades():
    """
    Accept JSON payload:
    {
      "class_id": 1,
      "subject_id": 2,
      "term": "Term 1",
      "year": "2025",
      "scores": {
        "student_id": { "individual_test": 10, ... }
      }
    }
    Saves or updates TermScore records.
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400

    class_id = data.get("class_id")
    subject_id = data.get("subject_id")
    term = data.get("term")
    year = data.get("year")
    scores = data.get("scores", {})

    if not (class_id and subject_id and term and year):
        return jsonify({"status": "error", "message": "Missing required info"}), 400

    # permission check
    if not has_grading_access(current_user, class_id, subject_id):
        return jsonify({"status": "error", "message": "Permission denied!"}), 403

    # resolving teacher_id
    teacher_id = None
    if getattr(current_user, "role", None) == "teacher":
        teacher = Teacher.query.filter_by(email=current_user.email).first()
        teacher_id = teacher.id if teacher else None
    else:
        assignment = TeacherSubjectClass.query.filter_by(
            class_id=class_id, subject_id=subject_id, is_active=True
        ).first()
        teacher_id = assignment.teacher_id if assignment else None

    if not teacher_id:
        return jsonify({"status": "error", "message": "No valid teacher found"}), 400

    for student_id_str, score_data in scores.items():
        try:
            sid = int(student_id_str)
        except Exception:
            continue

        individual_test = min(float(score_data.get("individual_test", 0) or 0), 15)
        group_work = min(float(score_data.get("group_work", 0) or 0), 15)
        class_test = min(float(score_data.get("class_test", 0) or 0), 15)
        project = min(float(score_data.get("project", 0) or 0), 15)
        exam_score = min(float(score_data.get("exam_score", 0) or 0), 100)

        # find existing
        term_score = TermScore.query.filter_by(
            student_id=sid,
            subject_id=subject_id,
            class_id=class_id,
            term=term,
            year=year,
        ).first()

        if term_score:
            term_score.individual_test = individual_test
            term_score.group_work = group_work
            term_score.class_test = class_test
            term_score.project = project
            term_score.exam_score = exam_score
            term_score.calculate_totals()
        else:
            term_score = TermScore(
                student_id=sid,
                subject_id=subject_id,
                class_id=class_id,
                teacher_id=teacher_id,
                term=term,
                year=year,
                individual_test=individual_test,
                group_work=group_work,
                class_test=class_test,
                project=project,
                exam_score=exam_score,
            )
            term_score.calculate_totals()
            db.session.add(term_score)

    db.session.commit()
    return jsonify({"status": "success", "message": "Scores saved successfully"})


@bp.route("/master/<class_group>/<term>/<year>", methods=["GET"])
@login_required
@role_required(["admin", "headteacher", "teacher"])
def master_sheet(class_group, term, year):
    """
    Render the master sheet. class_group can be 'all' or specific master_class name.
    """
    if class_group == "all":
        classes = Class.query.order_by(Class.name).all()
    else:
        classes = Class.query.filter_by(master_class=class_group).all()

    class_ids = [c.id for c in classes]
    students = (
        Student.query.filter(Student.class_id.in_(class_ids))
        .order_by(Student.surname, Student.first_name)
        .all()
    )

    subjects = (
        Subject.query.join(TeacherSubjectClass)
        .filter(TeacherSubjectClass.class_id.in_(class_ids))
        .filter(TeacherSubjectClass.is_active == True)
        .distinct()
        .all()
    )

    # build term_scores and totals
    term_scores = {}
    for student in students:
        term_scores[student.id] = {}
        for subject in subjects:
            score = TermScore.query.filter_by(
                student_id=student.id, subject_id=subject.id, term=term, year=year
            ).first()
            term_scores[student.id][subject.id] = score

    student_totals = {}
    for student in students:
        total = 0.0
        for subject in subjects:
            s = term_scores[student.id].get(subject.id)
            if s and s.total_score:
                total += s.total_score
        student_totals[student.id] = total

    # compute positions
    sorted_totals = sorted(student_totals.items(), key=lambda x: x[1], reverse=True)
    positions = {}
    rank = 0
    prev_score = None
    for idx, (student_id, score) in enumerate(sorted_totals, start=1):
        if prev_score is None:
            rank = 1
            positions[student_id] = rank
            prev_score = score
        else:
            if score == prev_score:
                positions[student_id] = rank
            else:
                rank = idx
                positions[student_id] = rank
                prev_score = score

    return render_template(
        "exams_grading/master_sheet.html",
        class_group=class_group,
        classes=classes,
        students=students,
        subjects=subjects,
        term_scores=term_scores,
        student_totals=student_totals,
        positions=positions,
        term=term,
        year=year,
    )


@bp.route("/master/<class_group>/<term>/<year>/print", methods=["GET"])
@login_required
@role_required(["admin", "headteacher", "teacher"])
def master_sheet_print(class_group, term, year):
    """
    Print-friendly master sheet. Use browser print (no external PDF lib required).
    """
    # reuse logic from master_sheet
    if class_group == "all":
        classes = Class.query.order_by(Class.name).all()
    else:
        classes = Class.query.filter_by(master_class=class_group).all()

    class_ids = [c.id for c in classes]
    students = (
        Student.query.filter(Student.class_id.in_(class_ids))
        .order_by(Student.surname, Student.first_name)
        .all()
    )

    subjects = (
        Subject.query.join(TeacherSubjectClass)
        .filter(TeacherSubjectClass.class_id.in_(class_ids))
        .filter(TeacherSubjectClass.is_active == True)
        .distinct()
        .all()
    )

    term_scores = {}
    for student in students:
        term_scores[student.id] = {}
        for subject in subjects:
            score = TermScore.query.filter_by(
                student_id=student.id, subject_id=subject.id, term=term, year=year
            ).first()
            term_scores[student.id][subject.id] = score

    student_totals = {}
    for student in students:
        total = 0.0
        for subject in subjects:
            s = term_scores[student.id].get(subject.id)
            if s and s.total_score:
                total += s.total_score
        student_totals[student.id] = total

    sorted_totals = sorted(student_totals.items(), key=lambda x: x[1], reverse=True)
    positions = {}
    rank = 0
    prev_score = None
    for idx, (student_id, score) in enumerate(sorted_totals, start=1):
        if prev_score is None:
            rank = 1
            positions[student_id] = rank
            prev_score = score
        else:
            if score == prev_score:
                positions[student_id] = rank
            else:
                rank = idx
                positions[student_id] = rank
                prev_score = score

    return render_template(
        "exams_grading/master_sheet_print.html",
        class_group=class_group,
        classes=classes,
        students=students,
        subjects=subjects,
        term_scores=term_scores,
        student_totals=student_totals,
        positions=positions,
        term=term,
        year=year,
    )


@bp.route("/assignments", methods=["GET"])
@login_required
@role_required(["admin", "headteacher", "teacher"])
def view_assignments():
    """
    View all current teacher-subject-class assignments.
    Returns HTML for browser requests, JSON for AJAX requests.
    """
    if current_user.role in ["admin", "headteacher"]:
        assignments = TeacherSubjectClass.query.filter_by(is_active=True).all()
    else:
        # For teachers, only show their own assignments
        teacher = Teacher.query.filter_by(email=current_user.email).first()
        if teacher:
            assignments = TeacherSubjectClass.query.filter_by(
                teacher_id=teacher.id, is_active=True
            ).all()
        else:
            assignments = []

    # Return JSON for AJAX requests only when explicitly requested
    # Use a more specific check to avoid confusing browser requests with AJAX
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        assignments_data = []
        for assignment in assignments:
            assignments_data.append(
                {
                    "id": assignment.id,
                    "teacher_id": assignment.teacher_id,
                    "teacher_name": (
                        assignment.teacher.full_name
                        if assignment.teacher
                        else "Unknown"
                    ),
                    "subject_id": assignment.subject_id,
                    "subject_name": (
                        assignment.subject.name if assignment.subject else "Unknown"
                    ),
                    "class_id": assignment.class_id,
                    "class_name": (
                        assignment.class_.name if assignment.class_ else "Unknown"
                    ),
                    "is_active": assignment.is_active,
                }
            )
        return jsonify({"assignments": assignments_data})

    # Return HTML for regular browser requests
    return render_template(
        "exams_grading/view_assignments.html", assignments=assignments
    )


@bp.route("/unassign", methods=["POST"])
@login_required
@role_required(["admin", "headteacher"])
def unassign_teacher_subject():
    """
    Unassign/delete a teacher-subject-class assignment.
    (POST only, returns JSON)
    """
    from flask_wtf.csrf import validate_csrf

    try:
        validate_csrf(request.form.get("csrf_token"))
    except:
        return jsonify({"status": "error", "message": "Invalid CSRF token"}), 400

    assignment_id = request.form.get("assignment_id")

    if not assignment_id:
        return jsonify({"status": "error", "message": "Missing assignment ID"}), 400

    assignment = TeacherSubjectClass.query.get(assignment_id)

    if not assignment:
        return jsonify({"status": "error", "message": "Assignment not found"}), 404

    # For safety, we'll deactivate instead of delete
    assignment.is_active = False
    db.session.commit()

    return jsonify({"status": "success", "message": "Assignment removed successfully!"})


@bp.route("/select-period/<int:class_id>/<int:subject_id>", methods=["GET"])
@login_required
@role_required(["admin", "headteacher", "teacher"])
def select_grading_period(class_id, subject_id):
    """
    Allow user to select term and year before going to grading page.
    """
    if not has_grading_access(current_user, class_id, subject_id):
        flash("You do not have permission to grade this class/subject!", "danger")
        return redirect(url_for("exams_grading.index"))

    class_ = Class.query.get_or_404(class_id)
    subject = Subject.query.get_or_404(subject_id)

    return render_template(
        "exams_grading/select_period.html", class_=class_, subject=subject
    )


# Route for student's academic report
@bp.route("/student-report/<int:student_id>/term/<year>")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def student_term_report(student_id, term, year):
    """Generating a termly report a specific student"""
    student = Student.query.get_or_404(student_id)

    # Getting all term scores for this student for the specified term and year
    term_scores = TermScore.query.filter_by(
        student_id=student_id, term=term, year=year
    ).all()

    # Getting class information
    class_ = Class.query.get(student.class_id) if student.class_id else None

    # Calculating subject positions
    subject_positions = {}
    for score in term_scores:
        # Getting all scores for this subject in the same class
        subject_scores = (
            TermScore.query.filter_by(
                subject_id=score.subject_id,
                class_id=score.class_id,
                term=term,
                year=year,
            )
            .order_by(TermScore.total_score.desc())  # type: ignore
            .all()
        )

        # Finding student's position
        for idx, subject_score in enumerate(subject_scores, 1):
            if subject_score.student_id == student_id:
                subject_positions[score.subject_id] = idx
                break

    return render_template(
        "exams_grading/student_term_report.html",
        student=student,
        class_=class_,
        term_scores=term_scores,
        subject_positions=subject_positions,
        term=term,
        year=year,
    )


@bp.route("/class-reports/<int:class_id>/<term>/<year>")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def class_term_report(class_id, term, year):
    """Generating term reports for all students in a class"""
    class_ = Class.query.get_or_404(class_id)
    students = Student.query.filter_by(class_id=class_id).all()

    return render_template(
        "exams_grading/class_term_report.html",
        class_=class_,
        students=students,
        term=term,
        year=year,
    )


# Route for student performance tracking
@bp.route("/student-performance/<int:student_id>")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def student_performance(student_id):
    """Viewing student's academic performance across all subjects"""
    student = Student.query.get_or_404(student_id)

    # Getting all term scores for student
    term_scores = TermScore.query.filter_by(student_id=student_id).all()

    # Organizimg scores by subject and term
    performance_data = {}
    for score in term_scores:
        if score.subject_id not in performance_data:
            subject = Subject.query.get(score.subject_id)
            performance_data[score.subject_id] = {"subject": subject, "scores": {}}

        term_key = f"{score.term} {score.year}"
        performance_data[score.subject_id]["scores"][term_key] = {
            "total_score": score.total_score,
            "class_total": score.class_total,
            "exam_score": score.exam_score,
            "individual_test": score.individual_test,
            "class_test": score.class_test,
            "project": score.project,
        }

    # Calculating averages and trends for student
    for subject_id, data in performance_data.items():
        scores = [score["total_score"] for score in data["score"].values()]
        if scores:
            data["average"] = sum(scores) / len(scores)
            data["trend"] = (
                "improving"
                if len(scores) > 1 and scores[-1] > scores[0]
                else (
                    "declining"
                    if len(scores) > 1 and scores[-1] < scores[0]
                    else "stable"
                )
            )
        else:
            data["average"] = 0
            data["trend"] = "no data"

    return render_template(
        "exams_grading/student_performance.html", performance_data=performance_data
    )


# Route for subject performance
@bp.route("/subject-performance/<int:subject_id>/<int:class_id>")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def subject_performance(subject_id, class_id):
    """View performance metrics for a specifics subject in a class"""
    subject = Subject.query.get_or_404(subject_id)
    class_ = Class.query.get_or_404(class_id)

    # Getting all term scores for this subject and class
    term_scores = TermScore.query.filter_by(
        subject_id=subject_id, class_id=class_id
    ).all()

    # Organizing by student and term
    performance_data = {}
    for score in term_scores:
        if score.student_id not in performance_data:
            student = Student.query.get(score.student_id)
            performance_data[score.student_id] = {"student": student, "scores": {}}

        term_key = f"{score.term} {score.year}"
        performance_data[score.student_id]["scores"][term_key] = score.total_score

    # Calculating class averages per term
    term_averages = {}
    for student_id, data in performance_data.items():
        for term, score in data["scores"].items():
            if term not in term_averages:
                term_averages[term] = []
            term_averages[term].append(score)

    for term, scores in term_averages.items():
        term_averages[term] = sum(scores) / len(scores) if scores else 0

    return render_template(
        "exams_grading/subject_performance.html",
        subject=subject,
        class_=class_,
        performance_data=performance_data,
        term_averages=term_averages,
    )


def has_grading_access(user, class_id, subject_id):
    """
    Determine whether `user` can grade class_id/subject_id.
    Admin/headteacher -> always True.
    Teacher -> only if teacher is assigned (TeacherSubjectClass active).
    Note: this function attempts to match current_user to a Teacher row by:
      * if current_user.role == 'teacher' and there's a Teacher record with user.email,
        use that Teacher.id; otherwise fallback to current_user.id (if your users and teachers share ids).
    Adjust to match your app's user<->teacher mapping if different.
    """
    if getattr(user, "role", None) in ["admin", "headteacher"]:
        return True

    if getattr(user, "role", None) == "teacher":
        teacher = Teacher.query.filter_by(email=getattr(user, "email", None)).first()
        teacher_id = teacher.id if teacher else None
        if not teacher_id:
            return False

        assignment = TeacherSubjectClass.query.filter_by(
            teacher_id=teacher_id,
            class_id=class_id,
            subject_id=subject_id,
            is_active=True,
        ).first()
        return assignment is not None

    return False
