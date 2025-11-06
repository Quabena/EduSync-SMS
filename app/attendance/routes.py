# attendance/routes.py
from app.utils.voice import announce
from flask import render_template, request, jsonify, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from flask_wtf.csrf import generate_csrf
from app.decorators import role_required
from app import db
from app.models import (
    User,
    Student,
    Class,
    Attendance,
    HallPass,
    Teacher,
    TeacherSubjectClass,
    AttendanceAudit,
)
from app.attendance import bp
from datetime import datetime, timedelta, date, timezone
import json
import csv
import io
from sqlalchemy import func, extract, case
from sqlalchemy.orm import joinedload


# Routes for attendance dashboard
@bp.route("/")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def attendance_dashboard():
    """Enhanced attendance dashboard with overview and analytics"""
    # Get classes the user has access to
    if current_user.role in ["admin", "headteacher"]:
        classes = Class.query.filter(
            Class.is_alumni_class == False, Class.name.like("JHS%")
        ).all()

    else:
        teacher = Teacher.query.filter_by(email=current_user.email).first()
        classes = teacher.classes if teacher else []

    # Get current date and term info
    today = date.today()
    current_month = today.month
    current_year = today.year

    # Determine current term based on month
    if 9 <= current_month <= 12:
        current_term = "Term 1"
    elif 1 <= current_month <= 4:
        current_term = "Term 2"
    else:
        current_term = "Term 3"

    # Get today's attendance summary for each class
    today_attendance = {}
    for class_ in classes:
        attendance_count = Attendance.query.filter_by(
            class_id=class_.id, date=today
        ).count()

        present_count = Attendance.query.filter_by(
            class_id=class_.id, date=today, status="present"
        ).count()

        absent_count = Attendance.query.filter_by(
            class_id=class_.id, date=today, status="absent"
        ).count()

        late_count = Attendance.query.filter_by(
            class_id=class_.id, date=today, status="late"
        ).count()

        excused_count = Attendance.query.filter_by(
            class_id=class_.id, date=today, status="excused"
        ).count()

        # class_.students may be dynamic or a list; use .count() if dynamic
        try:
            total_students_in_class = class_.students.count()
        except Exception:
            total_students_in_class = len(list(class_.students))

        today_attendance[class_.id] = {
            "total": attendance_count,
            "present": present_count,
            "absent": absent_count,
            "late": late_count,
            "excused": excused_count,
            "attendance_rate": (
                (present_count / total_students_in_class * 100)
                if total_students_in_class > 0
                else 0
            ),
        }

    # Get monthly attendance trends
    monthly_trends = {}
    for class_ in classes:
        # Get attendance data for the last 30 days
        start_date = today - timedelta(days=30)

        daily_data = (
            db.session.query(
                Attendance.date,
                func.count(case((Attendance.status == "present", 1))).label("present"),
                func.count(Attendance.id).label("total"),
            )
            .filter(Attendance.class_id == class_.id, Attendance.date >= start_date)
            .group_by(Attendance.date)
            .order_by(Attendance.date)
            .all()
        )

        monthly_trends[class_.id] = [
            {
                "date": data.date.strftime("%Y-%m-%d"),
                "rate": (data.present / data.total * 100) if data.total > 0 else 0,
            }
            for data in daily_data
        ]

    # Get chronic absenteeism alerts
    chronic_absenteeism = []
    for class_ in classes:
        # Students with less than 80% attendance in the current term
        students = class_.students
        try:
            iterator = students.all()
        except Exception:
            iterator = list(students)

        for student in iterator:
            present_count = Attendance.query.filter_by(
                student_id=student.id,
                class_id=class_.id,
                term=current_term,
                year=str(current_year),
                status="present",
            ).count()

            total_days = Attendance.query.filter_by(
                student_id=student.id,
                class_id=class_.id,
                term=current_term,
                year=str(current_year),
            ).count()

            if total_days > 10:  # Only consider students with enough data
                attendance_rate = present_count / total_days * 100
                if attendance_rate < 80:
                    chronic_absenteeism.append(
                        {
                            "student": student,
                            "class": class_,
                            "attendance_rate": attendance_rate,
                            "absent_days": total_days - present_count,
                        }
                    )

    # Get recent attendance activity (Attendance objects, with related Student & Class eager-loaded)
    recent_activity = (
        Attendance.query.options(
            joinedload(Attendance.student), joinedload(Attendance.classroom)  # type: ignore
        )
        .join(Student, Attendance.student_id == Student.id)
        .join(Class, Attendance.class_id == Class.id)
        .filter(Attendance.date >= today - timedelta(days=7))
        .order_by(Attendance.created_at.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "attendance/dashboard.html",
        classes=classes,
        today_attendance=today_attendance,
        monthly_trends=monthly_trends,
        chronic_absenteeism=chronic_absenteeism,
        recent_activity=recent_activity,
        today=today,
        current_term=current_term,
        current_year=current_year,
    )


# Routes for attendance analysis
@bp.route("/attendance-analytics/<int:class_id>")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def attendance_analytics(class_id):
    """Attendance analytics and trends"""
    class_ = Class.query.get_or_404(class_id)

    if not has_attendance_access(current_user, class_id):
        flash("Access denied!", "danger")
        return redirect(url_for("attendance.attendance_dashboard"))

    # Getting attendance data for analysis
    attendance_data = (
        db.session.query(
            Attendance.date,
            func.count(case((Attendance.status == "present", 1))).label("present"),
            func.count(case((Attendance.status == "absent", 1))).label("absent"),
            func.count(case((Attendance.status == "late", 1))).label("late"),
            func.count(case((Attendance.status == "excused", 1))).label("excused"),
        )
        .filter(
            Attendance.class_id == class_id,
            Attendance.date >= date.today() - timedelta(days=30),
        )
        .group_by(Attendance.date)
        .order_by(Attendance.date)
        .all()
    )

    # Student attendance summary
    student_attendance = (
        db.session.query(
            Student.id,
            Student.full_name,
            func.count(case((Attendance.status == "present", 1))).label("present_days"),
            func.count(Attendance.id).label("total_days"),
        )
        .join(Attendance, Student.id == Attendance.student_id)
        .filter(
            Attendance.class_id == class_id,
            Attendance.date >= date.today() - timedelta(days=30),
        )
        .group_by(Student.id, Student.full_name)
        .all()
    )

    # Metrics for ascertaining chronic absenteeism (missing 20%+ of attendance days)
    chronic_absenteeism = []
    for student in student_attendance:
        attendance_rate = (
            ((student.present_days / student.total_days) * 100)
            if student.total_days > 0
            else 0
        )
        if attendance_rate < 80:
            chronic_absenteeism.append(
                {
                    "student": student.full_name,
                    "attendance_rate": attendance_rate,
                    "absent_days": student.total_days - student.present_days,
                }
            )
    return render_template(
        "attendance/analytics.html",
        class_=class_,
        attendance_data=attendance_data,
        chronic_absenteeism=chronic_absenteeism,
    )


# Route to export attendance
@bp.route("/export-attendance/<int:class_id>/<term>/<year>")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def export_attendance(class_id, term, year):
    """Export attendancce data to CSV"""
    class_ = Class.query.get_or_404(class_id)

    if not has_attendance_access(current_user, class_id):
        flash("Accessed denied", "danger")
        return redirect(url_for("attendance.attendance_dashboard"))

    # Getting attendance data (join Student so ordering by surname works)
    attendance_records = (
        Attendance.query.filter_by(class_id=class_id, term=term, year=year)
        .join(Student, Attendance.student_id == Student.id)
        .order_by(Attendance.date, Student.surname)
        .all()
    )

    # Creating CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(["Date", "Student", "Status", "Excuse Reason", "Marked By", "Time"])

    # Write Data
    for record in attendance_records:
        writer.writerow(
            [
                record.date.strftime("%Y-%m-%d"),
                record.student.full_name,
                record.status,
                record.excuse_reason or "",
                record.marker.username if record.marker else "System",
                record.created_at.strftime("%H:%M:%S"),
            ]
        )

    # Preparing response
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"attendance_{class_.name}_{term}_{year}.csv",
    )


# ROute for absence with excuse
@bp.route("/excuse-absence/<int:attendance_id>", methods=["POST"])
@login_required
@role_required(["admin", "headteacher", "teacher"])
def excuse_absence(attendance_id):
    """Mark an absence as excused with a reason"""
    attendance = Attendance.query.get_or_404(attendance_id)

    if not has_attendance_access(current_user, attendance.class_id):
        flash("Access denied!", "danger")
        return jsonify({"success": False, "message": "Access denied"}), 403

    excuse_reason = request.form.get("excuse_reason")
    if not excuse_reason:
        return jsonify({"success": False, "message": "Excuse reason required"}), 400

    # Creating audit trail
    audit = AttendanceAudit(
        attendance_id=attendance.id,
        changed_by=current_user.id,
        change_type="update",
        old_status=attendance.status,
        new_status="excused",
        change_reason=f"Excused: {excuse_reason}",
    )
    db.session.add(audit)

    # Updating attendance
    attendance.status = "excused"
    attendance.excuse_reason = excuse_reason
    attendance.marked_by = current_user.id
    attendance.updated_at = datetime.now(timezone.utc)

    db.session.commit()

    return jsonify({"success": True, "message": "Absence excused successfully!"})


# Route for bulk attendance
@bp.route("/bulk-attendance", methods=["POST"])
@login_required
@role_required(["admin", "headteacher", "teacher"])
def bulk_attendance():
    """Bulk update attendance status"""
    data = request.get_json()
    class_id = data.get("class_id")
    date_str = data.get("date")
    term = data.get("term")
    year = data.get("year")
    status = data.get("status")
    student_ids = data.get("student_ids", [])

    if not all([class_id, date_str, term, year, status]):
        return (
            jsonify({"success": False, "message": "Missing required parameters"}),
            400,
        )

    try:
        # correct format token
        attendance_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"success": False, "message": "Invalid date format"}), 400

    if not has_attendance_access(current_user, class_id):
        return jsonify({"success": False, "message": "Access denied!"}), 403

    # Processing each student
    for student_id in student_ids:
        # Find existing records or create new one
        attendance = Attendance.query.filter_by(
            student_id=student_id,
            class_id=class_id,
            date=attendance_date,
            term=term,
            year=year,
        ).first()

        if attendance:
            # Create audit trail for update
            audit = AttendanceAudit(
                attendance_id=attendance.id,
                changed_by=current_user.id,
                change_type="update",
                old_status=attendance.status,
                new_status=status,
                change_reason="Bulk update",
            )
            db.session.add(audit)

            attendance.status = status
            # Ensure marked_by is stored as scalar id, not tuple
            attendance.marked_by = current_user.id
            attendance.updated_at = datetime.now(timezone.utc)
        else:
            # Create new attendance record
            attendance = Attendance(
                student_id=student_id,
                class_id=class_id,
                date=attendance_date,
                term=term,
                year=year,
                status=status,
                method="manual",
                marked_by=current_user.id,
            )
            db.session.add(attendance)

            # Create audit trail for new creation (attendance.id will be filled on flush)
            # We'll create audit with attendance_id after flush/commit. For simplicity,
            # create an audit without attendance_id and set it after commit or skip id.
            audit = AttendanceAudit(
                attendance_id=None,
                changed_by=current_user.id,
                change_type="create",
                new_status=status,
                change_reason="Bulk update",
            )
            db.session.add(audit)

    db.session.commit()

    return jsonify(
        {
            "success": True,
            "message": f"Attendance updated for {len(student_ids)} students",
        }
    )


# Route for attendance audit
@bp.route("/attendance-audit/<int:attendance_id>")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def attendance_audit(attendance_id):
    """View audit trail for an attendance record"""
    attendance = Attendance.query.get_or_404(attendance_id)
    audit_trail = (
        AttendanceAudit.query.filter_by(attendance_id=attendance_id)
        .order_by(AttendanceAudit.changed_at.desc())
        .all()
    )

    return render_template(
        "attendance/audit_trail.html", attendance=attendance, audit_trail=audit_trail
    )


# Route for selecting attendance date
@bp.route("/select-attendance-date", methods=["GET", "POST"])
@login_required
@role_required(["admin", "headteacher", "teacher"])
def select_attendance_date():
    """Select term, year, and date for attendance marking"""
    if request.method == "POST":
        term = request.form.get("term")
        year = request.form.get("year")
        attendance_date = request.form.get("attendance_date")
        class_id = request.form.get("class_id")

        if not all([term, year, attendance_date, class_id]):
            flash("Please fill all fields", "danger")
            return redirect(request.url)

        # Validating date
        selected_date = datetime.strptime(attendance_date, "%Y-%m-%d").date()  # type: ignore
        today = date.today()

        if selected_date > today:
            flash("You cannot mark attendance for future dates", "warning")
            return redirect(request.url)

        return redirect(
            url_for(
                "attendance.mark_attendance",
                class_id=class_id,
                term=term,
                year=year,
                date_str=attendance_date,
            )
        )

    # Get classes the user has access to
    if current_user.role in ["admin", "headteacher"]:
        classes = Class.query.filter(
            Class.is_alumni_class == False, Class.name.like("JHS%")
        ).all()

    else:
        teacher = Teacher.query.filter_by(email=current_user.email).first()
        classes = teacher.classes if teacher else []

    return render_template(
        "attendance/select_date.html",
        classes=classes,
        today=date.today(),
        current_year=datetime.now().year,
    )


# Route for term attendance
@bp.route("/term-attendance/", methods=["GET", "POST"])
@login_required
@role_required(["admin", "headteacher", "teacher"])
def term_attendance():
    """View term attendance summary for a class"""
    if request.method == "POST":
        class_id = request.form.get("class_id")
        term = request.form.get("term")
        year = request.form.get("year")

        if not all([class_id, term, year]):
            flash("Please select class, term, and year.", "danger")
            return redirect(request.url)

        return redirect(
            url_for(
                "attendance.term_attendance_report",
                class_id=class_id,
                term=term,
                year=year,
            )
        )
    # Getting classes the user has access to
    if current_user.role in ["admin", "headteacher"]:
        classes = Class.query.filter(
            Class.is_alumni_class == False, Class.name.like("JHS%")
        ).all()

    else:
        teacher = Teacher.query.filter_by(email=current_user.email).first()
        classes = teacher.classes if teacher else []

    return render_template(
        "attendance/select_term.html",
        classes=classes,
        today=date.today(),
        current_year=datetime.now().year,
    )


# Route to mark attendance
@bp.route(
    "/mark-attendance/<int:class_id>/<term>/<year>/<date_str>", methods=["GET", "POST"]
)
@login_required
def mark_attendance(class_id, term, year, date_str):
    """Mark attendance for a class with authorization"""
    class_ = Class.query.get_or_404(class_id)

    # Checking if user has access to mark attendance for this class
    if not has_attendance_access(current_user, class_id):
        flash("You do not have permission to mark attendance for this class!", "danger")
        return redirect(url_for("attendance.attendance_dashboard"))

    # Parsing data
    try:
        attendance_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid date format", "danger")
        return redirect(url_for("attendance.select_attendance_date"))

    # Checking if date is in the future
    today = date.today()
    if attendance_date > today:
        flash("You cannot mark attendance for future dates!", "warning")
        return redirect(url_for("attendance.select_attendance_date"))

    # Getting existing attendance records for this date
    attendance_records = Attendance.query.filter_by(
        class_id=class_id, term=term, year=year, date=attendance_date
    ).all()

    attendance_dict = {r.student_id: r for r in attendance_records}

    if request.method == "POST":
        # Verifying CSRF token
        if not validate_csrf(request.form.get("csrf_token")):
            flash("Invalid CSRF token", "danger")
            return redirect(
                url_for(
                    "attendance.mark_attendance",
                    class_id=class_id,
                    term=term,
                    year=year,
                    date_str=date_str,
                )
            )

        for student in class_.students:
            status = request.form.get(f"status_{student.id}", "absent")

            if student.id in attendance_dict:
                # Update existing records
                record = attendance_dict[student.id]
                if record.status != status:
                    record.status = status
                    record.method = "manual"
            else:
                # Create new record
                attendance = Attendance(
                    student_id=student.id,
                    class_id=class_id,
                    date=attendance_date,
                    term=term,
                    year=year,
                    status=status,
                    method="manual",
                )
                db.session.add(attendance)

        db.session.commit()
        flash("Attendance saved successfully!", "success")
        return redirect(
            url_for(
                "attendance.mark_attendance",
                class_id=class_id,
                term=term,
                year=year,
                date_str=date_str,
            )
        )

    return render_template(
        "attendance/mark_attendance.html",
        class_=class_,
        attendance_dict=attendance_dict,
        attendance_date=attendance_date,
        term=term,
        year=year,
        date_str=date_str,
        now=datetime.now,
    )


# Route for term attendance report
@bp.route("/term-attendance/<int:class_id>/<term>/<year>")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def term_attendance_report(class_id, term, year):
    """Generate term attendance report for selected class, term and year"""
    class_ = Class.query.get_or_404(class_id)

    # Check if user has access to view this class' attendance
    if not has_attendance_access(current_user, class_id):
        flash("You do not have permission to view attendance for this class!", "danger")
        return redirect(url_for("attendance.term_attendance"))

    # Getting all students in the class
    students = (
        Student.query.filter_by(class_id=class_id)
        .order_by(Student.surname, Student.first_name)
        .all()
    )

    # Getting all attendance for this term and year
    attendance_days = (
        db.session.query(Attendance.date)
        .filter(
            Attendance.class_id == class_id,
            Attendance.term == term,
            Attendance.year == year,
        )
        .distinct()
        .order_by(Attendance.date)
        .all()
    )

    attendance_days = [day[0] for day in attendance_days]

    # Getting attendance record for each student
    attendance_records = {}
    for student in students:
        records = Attendance.query.filter_by(
            student_id=student.id, class_id=class_id, term=term, year=year
        ).all()

        attendance_records[student.id] = {
            record.date: record.status for record in records
        }

    # Calculating summary statistics
    summary = {"total_days": len(attendance_days), "student_stats": {}}

    for student in students:
        present_count = sum(
            1
            for day in attendance_days
            if attendance_records.get(student.id, {}).get(day) == "present"
        )

        summary["student_stats"][student.id] = {
            "present": present_count,
            "absent": len(attendance_days) - present_count if attendance_days else 0,
            "percentage": (
                (present_count / len(attendance_days) * 100) if attendance_days else 0
            ),
        }

    return render_template(
        "attendance/term_attendance_report.html",
        class_=class_,
        students=students,
        attendance_days=attendance_days,
        attendance_records=attendance_records,
        summary=summary,
        term=term,
        year=year,
    )


# Helper function for attendance access
def has_attendance_access(user, class_id):
    """
    Check if user has permission to mark/view attendance for a class
    Admin, headteacher, and form teachers have access
    """
    if user.role in ["admin", "headteacher"]:
        return True

    if user.role == "teacher":
        # Check if this teacher is a form teacher for this class
        teacher = Teacher.query.filter_by(email=user.email).first()
        if teacher and class_id in [c.id for c in teacher.classes]:
            return True

    return False


def validate_csrf(token):
    """Validate CSRF token"""
    from flask_wtf.csrf import validate_csrf as validate

    try:
        validate(token)
        return True
    except Exception:
        return False


@bp.route("/scanner")
@login_required
@role_required(["admin", "teacher"])
def scanner():
    classes = Class.query.filter(
        Class.is_alumni_class == False, Class.name.like("JHS%")
    ).all()

    if not classes:
        flash("No classes available!", "warning")
    return render_template("attendance/scanner.html", classes=classes)


@bp.route("/scan", methods=["POST"])
@login_required
@role_required(["admin", "teacher"])
def process_scan():
    data = request.get_json()
    qr_data = data.get("qr_data")
    class_id = data.get("class_id")

    if not qr_data or not class_id:
        return jsonify({"success": False, "message": "Missing data"}), 400

    # Parse QR data
    parts = qr_data.split(":")
    if len(parts) < 2:
        return jsonify({"success": False, "message": "Invalid QR code!"}), 400

    qr_type = parts[0]

    if qr_type == "STUDENT":
        student_id = int(parts[1])
        student = Student.query.get(student_id)
        if not student:
            return jsonify({"success": False, "message": "Student not found!"}), 404

        # Check if already marked today
        today = datetime.now().date()
        existing = Attendance.query.filter_by(
            student_id=student_id,
            date=today,
            class_id=class_id,
        ).first()

        if existing:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"{student.full_name} already marked today",
                    }
                ),
                400,
            )

        # Creating attendance record
        attendance = Attendance(
            student_id=student_id,
            class_id=class_id,
            date=today,
            status="present",
            method="QR",
            scanned_by=current_user.id,
        )
        db.session.add(attendance)
        db.session.commit()

        announce(f"{student.full_name} marked present")

        return jsonify(
            {
                "success": True,
                "message": f"{student.full_name} marked present",
                "student": {
                    "id": student.id,
                    "name": student.full_name,
                    "class": (
                        student.classroom.name if student.classroom else "Unassigned"
                    ),
                },
            }
        )

    elif qr_type == "HALLPASS":
        hallpass_id = int(parts[1])
        hallpass = HallPass.query.get(hallpass_id)
        if not hallpass:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Hall-pass not found!",
                    }
                ),
                404,
            )

        # Mark hall pass as used
        hallpass.mark_used(current_user.id)

        return jsonify(
            {
                "success": True,
                "message": f"Hall pass for {hallpass.student.full_name} validated",
                "destination": hallpass.destination,
            }
        )

    return jsonify({"success": False, "message": "Unknown QR type"}), 400


# Manual Attendance Marking
from datetime import datetime
from flask import current_app


def current_term(today=None):
    # implement your actual school calendar mapping here.
    # This is a simple example fallback.
    today = today or datetime.utcnow().date()
    m = today.month
    if 1 <= m <= 4:
        return "Term 2"
    if 5 <= m <= 8:
        return "Term 3"
    return "Term 1"


# Manual Attendance ROute
@bp.route("/manual/<int:class_id>", methods=["GET", "POST"])
@login_required
@role_required(["admin", "teacher"])
def manual_attendance(class_id):
    class_ = Class.query.get_or_404(class_id)
    today = datetime.now().date()

    # Get existing attendance for the date & class
    attendance_records = Attendance.query.filter_by(class_id=class_id, date=today).all()
    attendance_dict = {r.student_id: r.status for r in attendance_records}

    # Provide defaults to template (so your form can include hidden selects)
    default_term = current_term()
    default_year = str(datetime.now().year)

    if request.method == "POST":
        # Prefer form values, else fallback to defaults
        term = request.form.get("term") or default_term
        year = request.form.get("year") or default_year

        # Validate required values early
        if not term or not year:
            flash("Please select Term and Year before saving attendance.", "warning")
            return redirect(url_for("attendance.manual_attendance", class_id=class_id))

        # Loop through students and create/update attendance rows
        for student in class_.students:
            status = request.form.get(f"status_{student.id}", "absent")

            if student.id in attendance_dict:
                # Update existing record object
                # Find the record (we have attendance_records list)
                record = next(
                    r for r in attendance_records if r.student_id == student.id
                )

                changed = False
                if record.status != status:
                    record.status = status
                    changed = True

                # ensure term/year are set on existing rows if missing or different
                if getattr(record, "term", None) != term:
                    setattr(record, "term", term)
                    changed = True
                if getattr(record, "year", None) != year:
                    setattr(record, "year", year)
                    changed = True

                # set marker: try both possible attribute names defensively
                if hasattr(record, "scanned_by"):
                    setattr(record, "scanned_by", current_user.id)
                if hasattr(record, "marked_by"):
                    setattr(record, "marked_by", current_user.id)

                if changed:
                    record.method = "manual"
                    # SQLAlchemy will pick up attribute changes automatically
            else:
                # Create new attendance record — set all required fields including term/year
                attendance = Attendance(
                    student_id=student.id,
                    class_id=class_id,
                    date=today,
                    term=term,
                    year=year,
                    status=status,
                    method="manual",
                )

                # set marker on whichever attribute exists on model
                if hasattr(attendance, "scanned_by"):
                    setattr(attendance, "scanned_by", current_user.id)
                if hasattr(attendance, "marked_by"):
                    setattr(attendance, "marked_by", current_user.id)

                db.session.add(attendance)

        # Try to commit and handle DB-level integrity errors gracefully
        try:
            db.session.commit()
        except Exception as exc:
            current_app.logger.exception("Failed saving manual attendance: %s", exc)
            db.session.rollback()
            flash(
                "Failed to save attendance (database error). Please check term/year and try again.",
                "danger",
            )
            return redirect(url_for("attendance.manual_attendance", class_id=class_id))

        announce(f"Attendance saved for {class_.name}")
        flash("Attendance saved successfully!", "success")
        return redirect(url_for("attendance.manual_attendance", class_id=class_id))

    # GET -> render form; pass defaults so template can include selects/hidden fields
    return render_template(
        "attendance/manual.html",
        class_=class_,
        attendance_dict=attendance_dict,
        today=today,
        default_term=default_term,
        default_year=default_year,
    )
