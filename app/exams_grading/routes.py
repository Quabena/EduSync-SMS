import json
from flask import (
    render_template,
    request,
    jsonify,
    flash,
    redirect,
    url_for,
    current_app,
    Response,
    make_response,
    abort,
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
    Attendance,
    User,
    SchoolInfo,
    StudentRemarks,
    TermDates,
    SchoolCalendar,
)
from app.exams_grading import bp
from app.exams_grading.forms import SchoolInfoForm, TermDatesForm, StudentRemarksForm
from datetime import datetime, timezone
from app.decorators import role_required
from sqlalchemy import and_, or_, distinct, func
from werkzeug.utils import secure_filename
from collections import defaultdict
import os
import re
import math
import pdfkit


@bp.route("/", methods=["GET"])
@login_required
@role_required(["admin", "headteacher", "teacher"])
def index():
    """
    Grading dashboard. Prefer using Class.master_class_canonical if present.
    """
    # Base class filter: non-alumni, JHS classes
    base_filter = (Class.is_alumni_class == False, Class.name.like("JHS%"))

    # If the DB model has master_class_canonical, get distinct non-null values directly from DB
    master_groups = []
    if hasattr(Class, "master_class_canonical"):
        # Query distinct canonical values (skip null/empty)
        rows = (
            Class.query.with_entities(distinct(Class.master_class_canonical))  # type: ignore
            .filter(*base_filter)
            .filter(Class.master_class_canonical.isnot(None))  # type: ignore
            .all()
        )
        # rows is list of 1-tuples like [('JHS 1',), ('JHS 2',), ...]
        master_groups = [r[0] for r in rows if r[0]]
        # Ensure canonical normalization just in case (defensive)
        master_groups = sorted(
            {normalize_class_group(m) for m in master_groups}, key=lambda x: x
        )
    else:
        # Fallback: load classes and build canonical set in Python
        classes = Class.query.filter(*base_filter).order_by(Class.name).all()

        master_set = set()
        for class_ in classes:
            # Prefer master_class if present, else try name
            raw = getattr(class_, "master_class", None) or getattr(class_, "name", None)
            if raw:
                master_set.add(normalize_class_group(raw))

        # always include "all"
        master_set.add("all")

        def sort_key(val):
            if val == "all":
                return (0, 0, "")
            m = re.match(r"^JHS\s*([1-9]+)$", val, flags=re.I)
            if m:
                return (1, int(m.group(1)), "")
            return (2, 999, val.lower())

        master_groups = sorted(master_set, key=sort_key)

    # Ensure "all" is first and unique
    if "all" not in master_groups:
        master_groups.insert(0, "all")
    else:
        # put "all" at index 0
        master_groups = ["all"] + [g for g in master_groups if g != "all"]

    # Query classes for other parts of the page
    classes = (
        Class.query.filter(Class.is_alumni_class == False, Class.name.like("JHS%"))
        .order_by(Class.name)
        .all()
    )

    subjects = Subject.query.order_by(Subject.name).all()  # type: ignore

    recent_assignments = (
        TeacherSubjectClass.query.join(Class, TeacherSubjectClass.class_id == Class.id)
        .order_by(Class.name.desc())
        .limit(8)
        .all()
    )

    current_app.logger.debug("master_groups: %s", master_groups)

    return render_template(
        "exams_grading/index.html",
        classes=classes,
        subjects=subjects,
        recent_assignments=recent_assignments,
        master_groups=master_groups,
        now=datetime.now,
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
    classes = (
        Class.query.filter(Class.is_alumni_class == False, Class.name.like("JHS%"))
        .order_by(Class.name)
        .all()
    )

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
        now=datetime.now(),
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


# normalize helper for class_group input
def normalize_class_group(raw):
    """
    Normalize incoming class_group values into canonical master_class names
    or the sentinel "all". Handles variants like:
      - "all", "All"
      - "1", "2", "3"
      - "JHS1", "JHS 1", "jhs 1a", "JHS1A" -> "JHS 1"
      - "JHS 2", "jhs2b", etc.
    Returns either "all" or canonical master_class (e.g. "JHS 1").
    """
    if raw is None:
        return "all"

    s = str(raw).strip()
    if not s:
        return "all"

    lower = s.lower()

    # Accept explicit 'all'
    if lower == "all":
        return "all"

    # If purely numeric like "1", "2", "3"
    if lower.isdigit():
        return f"JHS {int(lower)}"

    # If something like "jhs1", "jhs 1", "jhs1a", "jhs 1 b"
    m = re.match(r"^jhs[\s\-]*([1-3])", lower)
    if m:
        level = int(m.group(1))
        return f"JHS {level}"

    # If user passed "1a" or "2b" (without JHS) treat as JHS <n>
    m2 = re.match(r"^([1-3])[ab]?$", lower)
    if m2:
        return f"JHS {int(m2.group(1))}"

    # If input already looks like "jhs 1" or "jhs 2" etc. be safe and normalize spacing/casing
    m3 = re.match(r"^(jhs)\s*([1-3])", lower)
    if m3:
        return f"JHS {int(m3.group(2))}"

    # Fallback: try to return the original trimmed string capitalized like stored in DB.
    # Many DB values for master_class are like "JHS 1" so attempt to make that form:
    # If raw contains a number 1-3, try to build "JHS <n>"
    m4 = re.search(r"([1-3])", lower)
    if m4:
        return f"JHS {int(m4.group(1))}"

    # last resort: return original trimmed (title-cased) so query can try matching it
    return s.title()


@bp.route("/master/<class_group>/<term>/<year>", methods=["GET"])
@login_required
@role_required(["admin", "headteacher", "teacher"])
def master_sheet(class_group, term, year):
    """
    Render the master sheet. class_group can be 'all' or specific master_class name.
    Uses master_class_canonical if available, falls back safely.
    """

    # Normalize incoming group right away (defensive)
    group = normalize_class_group(class_group)

    # Select classes depending on "all" or specific group.
    # Prefer canonical column if present.
    base_filters = (Class.is_alumni_class == False,)
    classes = []

    if group == "all":
        classes = (
            Class.query.filter(Class.is_alumni_class == False)
            .filter(Class.name.ilike("JHS%"))
            .order_by(Class.name)
            .all()
        )
    else:
        if hasattr(Class, "master_class_canonical"):
            # exact match against canonical column (fast & reliable)
            classes = (
                Class.query.filter(Class.is_alumni_class == False)
                .filter(Class.master_class_canonical == group)  # type: ignore
                .order_by(Class.name)
                .all()
            )
        else:
            # fallback: match start-with (handles "JHS 1A", "JHS 1 B", etc.)
            m = re.match(r"^JHS\s*([1-9]+)$", group, flags=re.I)
            if m:
                level = m.group(1)
                classes = (
                    Class.query.filter(Class.is_alumni_class == False)
                    .filter(
                        or_(
                            Class.master_class.ilike(f"JHS {level}%"),
                            Class.master_class.ilike(f"%{level}%"),
                            Class.name.ilike(f"% {level}%"),
                        )
                    )
                    .order_by(Class.name)
                    .all()
                )
            else:
                classes = (
                    Class.query.filter(Class.is_alumni_class == False)
                    .filter(Class.master_class.ilike(f"{group}%"))
                    .order_by(Class.name)
                    .all()
                )

    class_ids = [c.id for c in classes]
    current_app.logger.debug(
        "master_sheet: requested group=%r normalized=%r -> classes_found=%d class_ids=%s",
        class_group,
        group,
        len(classes),
        class_ids,
    )

    # Students: only if we have classes
    if class_ids:
        students = (
            Student.query.filter(Student.class_id.in_(class_ids))
            .order_by(Student.surname, Student.first_name)
            .all()
        )
    else:
        students = []

    current_app.logger.debug("students found: %d", len(students))

    # Subjects: teacher assignments for these classes (active)
    if class_ids:
        subjects = (
            Subject.query.join(TeacherSubjectClass)
            .filter(TeacherSubjectClass.class_id.in_(class_ids))
            .filter(TeacherSubjectClass.is_active == True)
            .distinct()
            .all()
        )
    else:
        subjects = []

    current_app.logger.debug("subjects found: %d", len(subjects))

    # Build term_scores using a single bulk query to avoid N*M queries
    term_scores = {}  # mapping student_id -> subject_id -> TermScore or None
    if students and subjects:
        student_ids = [s.id for s in students]
        subject_ids = [sub.id for sub in subjects]

        # bulk fetch all TermScore rows for these students/subjects/term/year
        scores = TermScore.query.filter(
            TermScore.student_id.in_(student_ids),
            TermScore.subject_id.in_(subject_ids),
            TermScore.term == term,
            TermScore.year == year,
        ).all()

        # Map into dict for O(1) lookups
        score_map = {(sc.student_id, sc.subject_id): sc for sc in scores}

        # Initialize term_scores structure and populate
        for student in students:
            term_scores[student.id] = {}
            for subject in subjects:
                term_scores[student.id][subject.id] = score_map.get(
                    (student.id, subject.id)
                )
    else:
        # initialize empty mappings for template compatibility
        for student in students:
            term_scores[student.id] = {}
            for subject in subjects:
                term_scores[student.id][subject.id] = None

    # Totals & positions (same logic, but safe for empty sets)
    student_totals = {}
    for student in students:
        total = 0.0
        for subject in subjects:
            s = term_scores[student.id].get(subject.id)
            if s and getattr(s, "total_score", None):
                try:
                    total += float(s.total_score)
                except Exception:
                    # defensive: if total_score isn't numeric, ignore it
                    continue
        student_totals[student.id] = total

    # compute positions (handle ties)
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

    current_app.logger.debug(
        "master_sheet debug: classes=%d students=%d subjects=%d term_score_rows=%d",
        len(classes),
        len(students),
        len(subjects),
    )

    return render_template(
        "exams_grading/master_sheet.html",
        class_group=group,
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
        classes = (
            Class.query.filter(Class.is_alumni_class == False, Class.name.like("JHS%"))
            .order_by(Class.name)
            .all()
        )
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
        "exams_grading/view_assignments.html",
        assignments=assignments,
        year=datetime.now().year,
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
        "exams_grading/select_period.html",
        class_=class_,
        subject=subject,
        now=datetime.now,
        current_month=datetime.now().month,
    )


# Route for student's academic report
# @bp.route("/student-report/<int:student_id>/<term>/<year>")
# @login_required
# @role_required(["admin", "headteacher", "teacher"])
# def student_term_report(student_id, term, year):
#     """Generating a termly report for a specific student."""
#     # fetch student (404 if missing)
#     student = Student.query.get_or_404(student_id)

#     # Fetch this student's term scores for the term/year
#     term_scores = TermScore.query.filter_by(
#         student_id=student_id, term=term, year=year
#     ).all()

#     # Ensure totals are calculated for display (does not commit to DB)
#     for s in term_scores:
#         try:
#             s.calculate_totals()
#         except Exception:
#             current_app.logger.exception(
#                 "Failed to calculate totals for TermScore id=%s", getattr(s, "id", None)
#             )

#     # Class information (may be None)
#     class_ = Class.query.get(student.class_id) if student.class_id else None

#     # Calculating subject positions
#     subject_positions = {}
#     for score in term_scores:
#         subject_scores = (
#             TermScore.query.filter_by(
#                 subject_id=score.subject_id,
#                 class_id=score.class_id,
#                 term=term,
#                 year=year,
#             )
#             .order_by(TermScore.total_score.desc())  # type: ignore
#             .all()
#         )

#         for idx, subject_score in enumerate(subject_scores, start=1):
#             if subject_score.student_id == student_id:
#                 subject_positions[score.subject_id] = idx
#                 break

#     # --- compute totals & percentage for the report ---
#     # total_score is scaled to 100 per subject in calculate_totals()
#     total_marks_obtained = sum((s.total_score or 0.0) for s in term_scores)
#     subjects_count = len(term_scores)
#     total_possible = subjects_count * 100  # 100 per subject after scaling

#     percentage = (
#         (total_marks_obtained / total_possible * 100.0) if total_possible else 0.0
#     )
#     average_marks = (total_marks_obtained / subjects_count) if subjects_count else 0.0
#     average_percent_per_subject = (
#         (percentage / subjects_count) if subjects_count else 0.0
#     )

#     # --- ATTENDANCE: use Attendance.status field (present/absent) ---
#     attendance_present = 0
#     attendance_absent = 0
#     attendance_percentage = 0.0

#     try:
#         attendance_records = Attendance.query.filter_by(
#             student_id=student_id, term=term, year=year
#         ).all()

#         for rec in attendance_records:
#             status = getattr(rec, "status", None)
#             if isinstance(status, str) and status.strip():
#                 s = status.strip().lower()
#                 if s in ("present", "p", "1", "yes", "true"):
#                     attendance_present += 1
#                 elif s in ("absent", "a", "0", "no", "false"):
#                     attendance_absent += 1
#                 else:
#                     # Unknown status — treat as absent (safe default)
#                     attendance_absent += 1
#             else:
#                 # Non-string or missing status — treat as absent (safe default)
#                 attendance_absent += 1

#         total_attendance = attendance_present + attendance_absent
#         if total_attendance:
#             attendance_percentage = (attendance_present / total_attendance) * 100.0
#         else:
#             attendance_percentage = 0.0

#     except Exception:
#         # Log but don't break page render
#         current_app.logger.exception(
#             "Error computing attendance for student_id=%s term=%s year=%s",
#             student_id,
#             term,
#             year,
#         )
#         attendance_present = attendance_absent = 0
#         attendance_percentage = 0.0

#     # Debug log for computed values
#     current_app.logger.debug(
#         "student_term_report: student_id=%s term=%s year=%s total=%r possible=%r percentage=%.2f "
#         "attendance_present=%s attendance_absent=%s attendance_pct=%.2f",
#         student_id,
#         term,
#         year,
#         total_marks_obtained,
#         total_possible,
#         percentage,
#         attendance_present,
#         attendance_absent,
#         attendance_percentage,
#     )

#     # Render template with all required and helpful context
#     return render_template(
#         "exams_grading/student_term_report.html",
#         student=student,
#         class_=class_,
#         term_scores=term_scores,
#         subject_positions=subject_positions,
#         term=term,
#         year=year,
#         total_marks_obtained=total_marks_obtained,
#         percentage=percentage,
#         subjects_count=subjects_count,
#         average_marks=average_marks,
#         average_percent_per_subject=average_percent_per_subject,
#         attendance_present=attendance_present,
#         attendance_absent=attendance_absent,
#         attendance_percentage=attendance_percentage,
#         now=datetime.now(),
#     )


# --- New Term REport


# Route for student report cards
def grade_and_remark(percent: float):
    """
    Return (grade, remark) based on percentage.
    Adjust thresholds to match school policy.
    """
    if percent is None:
        return ("--", "No score")
    p = percent
    if p >= 80:
        return ("1", "Excellent")
    if p >= 70:
        return ("2", "Very Good")
    if p >= 60:
        return ("3", "Good")
    if p >= 50:
        return ("4", "Satisfactory")
    if p >= 40:
        return ("5", "Pass")
    return ("9", "Fail")


# student_term_report commented after changes ---
# @bp.route("/student-report/<int:student_id>/<term>/<year>", methods=["GET"])
# @login_required
# @role_required(["admin", "headteacher", "teacher"])
# def student_term_report(student_id, term, year):
#     # 1) Basic fetches
#     student = Student.query.get_or_404(student_id)
#     klass = student.classroom  # relationship defined on Student.classroom
#     context = build_report_card_context(student_id, term, year)

#     # School info (single row expected)
#     school_info = SchoolInfo.query.first()

#     # 2) Subjects & term scores — bulk fetch
#     # Get all TermScore rows for the student for the given term/year
#     scores = (
#         TermScore.query.filter_by(student_id=student.id, term=term, year=year)
#         .join(Subject)
#         .all()
#     )

#     # Also find which subjects are assigned to the class (teacher assignments)
#     class_subjects = (
#         Subject.query.join(TeacherSubjectClass)
#         .filter(
#             TeacherSubjectClass.class_id == klass.id,
#             TeacherSubjectClass.is_active == True,
#         )
#         .distinct()
#         .order_by(Subject.name)  # type: ignore
#         .all()
#     )

#     # Build subject list: union of class_subjects and subjects present in scores
#     subject_ids = set([s.id for s in class_subjects] + [sc.subject_id for sc in scores])
#     subjects = (
#         Subject.query.filter(Subject.id.in_(subject_ids)).order_by(Subject.name).all()  # type: ignore
#     )

#     # Map term score by subject for quick access
#     score_map = {(sc.subject_id): sc for sc in scores}

#     # 3) Compute per-subject totals, grade, remarks
#     subject_rows = []
#     total_marks = 0.0
#     counted_subjects = 0

#     for subject in subjects:
#         sc = score_map.get(subject.id)
#         if sc:
#             components = {
#                 "individual_test": sc.individual_test or 0,
#                 "group_work": sc.group_work or 0,
#                 "class_test": sc.class_test or 0,
#                 "project": sc.project or 0,
#                 "class_total": sc.class_total or 0,
#                 "exam_score": sc.exam_score or 0,
#                 "total_score": sc.total_score or 0,
#             }
#             pct = float(components["total_score"])
#         else:
#             components = {
#                 k: None
#                 for k in (
#                     "individual_test",
#                     "group_work",
#                     "class_test",
#                     "project",
#                     "class_total",
#                     "exam_score",
#                     "total_score",
#                 )
#             }
#             pct = None

#         grade, remark = grade_and_remark(pct if pct is not None else 0.0)

#         subject_rows.append(
#             {
#                 "subject": subject,
#                 "components": components,
#                 "total": components.get("total_score"),
#                 "grade": grade,
#                 "remark": remark,
#                 "teacher": None,
#             }
#         )

#         score_val = components.get("total_score")
#         if isinstance(score_val, (int, float)):
#             total_marks += float(score_val)
#             counted_subjects += 1

#     overall_percentage = (total_marks / counted_subjects) if counted_subjects else None
#     overall_grade, overall_remark = (
#         grade_and_remark(overall_percentage or 0.0)
#         if overall_percentage is not None
#         else ("--", "No score")
#     )

#     # 4) Attendance summary for the term/year
#     total_attendance = Attendance.query.filter_by(
#         student_id=student.id, term=term, year=year
#     ).count()
#     # Optionally compute total possible days using SchoolCalendar (if populated)
#     possible_days = SchoolCalendar.query.filter_by(
#         term=term, year=year, day_type="school_day"
#     ).count()
#     attendance_pct = (
#         (total_attendance / possible_days * 100.0) if possible_days else None
#     )

#     # 5) Teacher/headteacher remarks (StudentRemarks)
#     remarks_obj = StudentRemarks.query.filter_by(
#         student_id=student.id, term=term, year=year
#     ).first()

#     # 6) Class statistics and positions
#     # Compute total_score for all students in the same class for given term/year
#     # We'll compute sum(total_score) per student across subjects that belong to that class/term
#     # Use TermScore.class_id == klass.id to ensure we only pick scores recorded for this class.
#     class_totals_query = (
#         db.session.query(
#             TermScore.student_id, func.sum(TermScore.total_score).label("sum_total")
#         )
#         .filter(
#             TermScore.class_id == klass.id,
#             TermScore.term == term,
#             TermScore.year == year,
#         )
#         .group_by(TermScore.student_id)
#         .order_by(func.sum(TermScore.total_score).desc())
#     )

#     class_totals = class_totals_query.all()  # list of tuples (student_id, sum_total)

#     # Build positions mapping with ties handled
#     positions = {}
#     prev = None
#     rank = 0
#     for idx, (s_id, sum_total) in enumerate(class_totals, start=1):
#         if prev is None:
#             rank = 1
#             positions[s_id] = rank
#             prev = sum_total
#         else:
#             if sum_total == prev:
#                 positions[s_id] = rank
#             else:
#                 rank = idx
#                 positions[s_id] = rank
#                 prev = sum_total

#     student_position = positions.get(student.id)

#     # 7) Number on roll for the class (active only)
#     number_on_roll = Student.query.filter_by(class_id=klass.id, status="active").count()

#     # 8) Prepare teacher mapping for subjects (optional): who teaches subject for this class
#     tsc_rows = TeacherSubjectClass.query.filter(
#         TeacherSubjectClass.class_id == klass.id,
#         TeacherSubjectClass.subject_id.in_(subject_ids),
#     ).all()
#     teacher_map = {
#         (tsc.subject_id): (tsc.teacher.full_name if tsc.teacher else None)
#         for tsc in tsc_rows
#     }

#     # inject teacher names into rows
#     for row in subject_rows:
#         row["teacher"] = teacher_map.get(row["subject"].id)

#     # 9) Render template
#     return render_template(
#         "exams_grading/student_term_report.html",
#         school=school_info,
#         student=student,
#         class_room=klass,
#         subject_rows=subject_rows,
#         total_marks=total_marks,
#         overall_percentage=overall_percentage,
#         overall_grade=overall_grade,
#         overall_remark=overall_remark,
#         attendance_count=total_attendance,
#         possible_days=possible_days,
#         attendance_pct=attendance_pct,
#         remarks_obj=remarks_obj,
#         position=student_position,
#         number_on_roll=number_on_roll,
#         term=term,
#         year=datetime.now().year,
#         # **context,
#     )


# New student_term_report
@bp.route("/student-report/<int:student_id>/<term>/<year>", methods=["GET"])
@login_required
@role_required(["admin", "headteacher", "teacher"])
def student_term_report(student_id, term, year):
    # Build full context
    context = build_report_card_context(student_id, term, year)

    # Render template
    return render_template(
        "exams_grading/student_term_report.html",
        **context,
    )


# --- Context for building a report card ---
def build_report_card_context(student_id: int, term: str, year: str):
    """
    Build and return the context dict needed to render the report card page.
    Returns a dict suitable for passing as **context to render_template.
    Raises 404 if student/class not found.
    """

    student = Student.query.get_or_404(student_id)
    klass = student.classroom

    school_info = SchoolInfo.query.first()

    # Bulk fetch scores and class subjects
    scores = TermScore.query.filter_by(
        student_id=student.id, term=term, year=year
    ).all()
    class_subjects = (
        Subject.query.join(TeacherSubjectClass)
        .filter(
            TeacherSubjectClass.class_id == klass.id,
            TeacherSubjectClass.is_active == True,
        )
        .distinct()
        .order_by(Subject.name)  # type: ignore
        .all()
    )

    subject_ids = set([s.id for s in class_subjects] + [sc.subject_id for sc in scores])
    subjects = (
        Subject.query.filter(Subject.id.in_(subject_ids)).order_by(Subject.name).all()  # type: ignore
    )

    score_map = {sc.subject_id: sc for sc in scores}

    # grade helper
    def grade_and_remark(percent: float):
        if percent is None:
            return ("--", "No score")
        if percent >= 80:
            return ("1", "Excellent")
        if percent >= 70:
            return ("2", "Very Good")
        if percent >= 60:
            return ("3", "Good")
        if percent >= 50:
            return ("4", "Pass")
        if percent >= 40:
            return ("5", "Marginal")
        return ("9", "Fail")

    subject_rows = []
    total_marks = 0.0
    counted_subjects = 0

    for subject in subjects:
        sc = score_map.get(subject.id)
        if sc:
            # coerce numeric components defensively (None -> 0)
            comp = {
                "individual_test": sc.individual_test or 0,
                "group_work": sc.group_work or 0,
                "class_test": sc.class_test or 0,
                "project": sc.project or 0,
                "class_total": sc.class_total or 0,
                "exam_score": sc.exam_score or 0,
                "total_score": sc.total_score if sc.total_score is not None else 0,
            }
            pct = float(comp["total_score"])
        else:
            comp = {
                k: None
                for k in (
                    "individual_test",
                    "group_work",
                    "class_test",
                    "project",
                    "class_total",
                    "exam_score",
                    "total_score",
                )
            }
            pct = None

        grade, remark = grade_and_remark(pct if pct is not None else 0.0)
        subject_rows.append(
            {
                "subject": subject,
                "components": comp,
                "total": comp.get("total_score"),
                "grade": grade,
                "remark": remark,
                "teacher": None,
            }
        )

        score_val = comp.get("total_score")
        if isinstance(score_val, (int, float)):
            total_marks += float(score_val)
            counted_subjects += 1

    # --- Custom overall grade: core subjects + best two others ---
    core_subject_names = {
        "English Language",
        "Mathematics",
        "Integrated Science",
        "Social Studies",
    }
    subject_scores = {
        row["subject"].name: row["components"].get("total_score")
        for row in subject_rows
        if row["components"].get("total_score") is not None
    }

    # Include core subjects
    overall_scores = [
        score for name, score in subject_scores.items() if name in core_subject_names
    ]

    # Best two remaining subjects
    remaining_scores = [
        score
        for name, score in subject_scores.items()
        if name not in core_subject_names
    ]
    best_two = sorted(remaining_scores, reverse=True)[:2]
    overall_scores.extend(best_two)

    overall_percentage = (
        (sum(overall_scores) / len(overall_scores)) if overall_scores else None
    )
    overall_grade, overall_remark = grade_and_remark(
        overall_percentage if overall_percentage else 0
    )

    # Attendance
    total_attendance = Attendance.query.filter_by(
        student_id=student.id, term=term, year=year
    ).count()
    possible_days = SchoolCalendar.query.filter_by(
        term=term, year=year, day_type="school_day"
    ).count()
    attendance_pct = (
        (total_attendance / possible_days * 100.0) if possible_days else None
    )

    # Remarks
    remarks_obj = StudentRemarks.query.filter_by(
        student_id=student.id, term=term, year=year
    ).first()

    # Class totals & positions
    class_totals_query = (
        db.session.query(
            TermScore.student_id, func.sum(TermScore.total_score).label("sum_total")
        )
        .filter(
            TermScore.class_id == klass.id,
            TermScore.term == term,
            TermScore.year == year,
        )
        .group_by(TermScore.student_id)
        .order_by(func.sum(TermScore.total_score).desc())
    )
    class_totals = class_totals_query.all()

    positions = {}
    prev = None
    rank = 0
    for idx, (s_id, sum_total) in enumerate(class_totals, start=1):
        if prev is None:
            rank = 1
            positions[s_id] = rank
            prev = sum_total
        else:
            if sum_total == prev:
                positions[s_id] = rank
            else:
                rank = idx
                positions[s_id] = rank
                prev = sum_total

    student_position = positions.get(student.id)
    number_on_roll = Student.query.filter_by(class_id=klass.id, status="active").count()

    # Teacher mapping
    tsc_rows = TeacherSubjectClass.query.filter(
        TeacherSubjectClass.class_id == klass.id,
        TeacherSubjectClass.subject_id.in_(subject_ids),
    ).all()
    teacher_map = {
        tsc.subject_id: (tsc.teacher.full_name if tsc.teacher else None)
        for tsc in tsc_rows
    }
    for row in subject_rows:
        row["teacher"] = teacher_map.get(row["subject"].id)

    context = dict(
        school=school_info,
        student=student,
        class_room=klass,
        subject_rows=subject_rows,
        total_marks=total_marks,
        overall_percentage=overall_percentage,
        overall_grade=overall_grade,
        overall_remark=overall_remark,
        attendance_count=total_attendance,
        possible_days=possible_days,
        attendance_pct=attendance_pct,
        remarks_obj=remarks_obj,
        position=student_position,
        number_on_roll=number_on_roll,
        term=term,
        year=year,
    )

    return context


# HTML route (uses helper)
@bp.route("/report-card/<int:student_id>/<term>/<year>", methods=["GET"])
@login_required
@role_required(["admin", "headteacher", "teacher"])
def report_card(student_id, term, year):
    context = build_report_card_context(student_id, term, year)
    return render_template("exams_grading/report_card.html", **context)


# PDF route (uses helper)
@bp.route("/report-card/<int:student_id>/<term>/<year>/pdf", methods=["GET"])
@login_required
@role_required(["admin", "headteacher", "teacher"])
def report_card_pdf(student_id, term, year):
    context = build_report_card_context(student_id, term, year)

    # Render HTML string
    html = render_template("exams_grading/student_term_report.html", **context)

    # Optional: configure pdfkit if wkhtmltopdf is not on PATH
    # config = pdfkit.configuration(wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe")
    # pdf = pdfkit.from_string(html, False, configuration=config)

    pdf = pdfkit.from_string(html, False)

    # Defensively coerce to bytes (some pdfkit setups might return True on success writing to file)
    if isinstance(pdf, bool):
        current_app.logger.error(
            "pdfkit.from_string returned boolean True; expected bytes. Check pdfkit config."
        )
        abort(500, "PDF generation failed")
    if not isinstance(pdf, (bytes, bytearray)):
        try:
            pdf = bytes(pdf)
        except Exception:
            current_app.logger.exception("Unable to coerce pdf output to bytes")
            abort(500, "PDF generation returned unexpected type")

    response = make_response(pdf)
    response.headers.set("Content-Type", "application/pdf")
    response.headers.set(
        "Content-Disposition",
        f"attachment; filename=report_{student_id}_{term}_{year}.pdf",
    )
    return response


# Route for admin/headteacher's interface for managing school information and term dates
@bp.route("/school-info", methods=["GET", "POST"])
@login_required
@role_required(["admin", "headteacher"])
def school_info():
    """Manage school information"""
    school = SchoolInfo.query.first()
    form = SchoolInfoForm(obj=school)

    if form.validate_on_submit():
        if not school:
            school = SchoolInfo()

        form.populate_obj(school)

        # Handle logo upload
        if "logo" in request.files:
            logo = request.files["logo"]
            if logo and logo.filename != "":
                filename = secure_filename(logo.filename)  # type: ignore
                logo_path = os.path.join(current_app.config["DOCUMENT_DIR"], filename)
                logo.save(logo_path)
                school.logo_path = filename

        if not SchoolInfo.query.first():
            db.session.add(school)

        db.session.commit()
        flash("School information updated successfully!", "success")
        return redirect(url_for("exams_grading.school_info"))

    return render_template("exams_grading/school_info.html", form=form, school=school)


# ---Term Dates---
@bp.route("/term-dates", methods=["GET", "POST"])
@login_required
@role_required(["admin", "headteacher"])
def term_dates():
    """Manage term dates"""
    term_dates_list = TermDates.query.all()
    form = TermDatesForm()

    if form.validate_on_submit():
        # Check if this term already exists
        existing = TermDates.query.filter_by(
            academic_year=form.academic_year.data, term=form.term.data
        ).first()

        if existing:
            flash(
                "Term dates for this academic year and term already exist!", "warning"
            )
            return redirect(url_for("exams_grading.term_dates"))

        term_date = TermDates(
            academic_year=form.academic_year.data,
            term=form.term.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            vacation_date=form.vacation_date.data,
            reopening_date=form.reopening_date.data,
        )

        db.session.add(term_date)
        db.session.commit()
        flash("Term dates added successfully!", "success")
        return redirect(url_for("exams_grading.term_dates"))

    return render_template(
        "exams_grading/term_dates.html", form=form, term_dates=term_dates_list
    )


# ---Delete term date---
@bp.route("/term-dates/<int:id>/delete", methods=["POST"])
@login_required
@role_required(["admin", "headteacher"])
def delete_term_dates(id):
    """Delete term dates"""
    term_date = TermDates.query.get_or_404(id)
    db.session.delete(term_date)
    db.session.commit()
    flash("Term dates deleted successfully!", "success")

    return redirect(url_for("exams_grading.term_dates"))


# ---Helper Functions---
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {
        "png",
        "jpg",
        "jpeg",
        "gif",
    }


def save_file(file, upload_folder):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        return filename
    return None


# Route for Teacher remarks interface
@bp.route("/student-remarks/<int:student_id>/<term>/<year>", methods=["GET", "POST"])
@login_required
@role_required(["admin", "headteacher", "teacher"])
def student_remarks(student_id, term, year):
    """Add or edit student remarks"""
    student = Student.query.get_or_404(student_id)

    # Checking if the current user is the class teacher or has higher privileges
    if current_user.role in ["teacher"]:
        teacher = Teacher.query.filter_by(email=current_user.email).first()
        if not teacher or student.class_id not in [c.id for c in teacher.classes]:
            flash("You are not authorized to add remarks for this student!", "danger")
            return redirect(url_for("exams_grading.index"))

    remarks = StudentRemarks.query.filter_by(
        student_id=student_id, term=term, year=year
    ).first()

    form = StudentRemarksForm(obj=remarks)

    if form.validate_on_submit():
        if remarks:
            form.populate_obj(remarks)
            remarks.updated_at = datetime.now(timezone.utc)
        else:
            teacher = Teacher.query.filter_by(email=current_user.email).first()
            if not teacher:
                flash("Teacher profile not found!", "danger")
                return redirect(url_for("exams_grading.index"))

            remarks = StudentRemarks(
                student_id=student_id, teacher_id=teacher.id, term=term, year=year
            )
            form.populate_obj(remarks)
            db.session.add(remarks)

        db.session.commit()
        flash("Remarks saved successfully!", "success")
        return redirect(
            url_for(
                "exams_grading.student_term_report",
                student_id=student_id,
                term=term,
                year=year,
            )
        )

    return render_template(
        "exams_grading/student_remarks.html",
        form=form,
        student=student,
        remarks=remarks,
        term=term,
        year=year,
    )


@bp.route("/class-reports/<int:class_id>/<term>/<year>")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def class_term_report(class_id, term, year, student_id):
    """Generating term reports for all students in a class"""
    class_ = Class.query.get_or_404(class_id)
    students = Student.query.filter_by(class_id=class_id).all()
    term_scores = TermScore.query.filter_by(student_id=student_id).all()

    return render_template(
        "exams_grading/class_term_report.html",
        class_=class_,
        students=students,
        term=term,
        year=year,
        term_scores=term_scores,
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
        scores = [score["total_score"] for score in data["scores"].values()]
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
        "exams_grading/student_performance.html",
        student=student,
        performance_data=performance_data,
        year=datetime.now().year,
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


# Breaking curses
