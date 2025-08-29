from app.utils.voice import announce
from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from app.decorators import role_required
from app import db
from app.models import User, Student, Class, Attendance, HallPass, Teacher
from app.attendance import bp
from datetime import datetime, timedelta
import json
from sqlalchemy import func, extract


# Routes for attendance dashboard
@bp.route("/")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def attendance_dashboard():
    """Attendance dashboard showing overview and recent records"""
    # Getting classes the user has access to
    if current_user.role in ["admin", "headteacher"]:
        classes = Class.query.all()
    else:
        # Only showing classes assigned to, for teachers.
        teacher = Teacher.query.filter_by(email=current_user.email).first()

        if teacher:
            classes = teacher.classes
        else:
            classes = []

    # Getting current date
    today = datetime.now().date()

    # Getting attendance summary for today
    today_attendance = {}
    for class_ in classes:
        attendance_count = Attendance.query.filter_by(
            class_id=class_.id, date=today
        ).count()

        present_count = Attendance.query.filter_by(
            class_id=class_.id, date=today, status="present"
        ).count()

        today_attendance[class_.id] = {
            "total": attendance_count,
            "present": present_count,
            "absent": attendance_count - present_count if attendance_count > 0 else 0,
        }

    return render_template(
        "attendance/dashboard.html",
        classes=classes,
        today_attendance=today_attendance,
        today=today,
    )


# Route for term attendance
@bp.route("/term-attendance/<int:class_id>/<term>/<year>")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def term_attendance(class_id, term, year):
    """View term attendance for a class"""
    class_ = Class.query.get_or_404(class_id)

    # Checking if user has access to this class
    if not has_attendance_access(current_user, class_id):
        flash("You don't have permission to view attendance for this class", "danger")
        return redirect(url_for("attendance.dashboard"))

    # Getting students in the class
    students = (
        Student.query.filter_by(class_id=class_id)
        .order_by(Student.surname, Student.first_name)
        .all()
    )

    # Getting all school days in the term (Might be good if I create a Term model for this)
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

    # Getting attendance records for each student
    attendance_records = {}
    for student in students:
        records = Attendance.query.filter_by(
            student_id=student.id, class_id=class_id, term=term, year=year
        ).all()

        attendance_records[student.id] = {
            record.date: record.status for record in records
        }

    # Calculating summary stats
    summary = {"total_days": len(attendance_days), "student_stats": {}}

    for student in students:
        present_count = sum(
            1
            for date in attendance_days
            if attendance_records.get(student.id, {}).get(date) == "present"
        )

        summary["student_stats"][student.id] = {
            "present": present_count,
            "absent": len(attendance_days) - present_count,
            "percentage": (
                (present_count) / len(attendance_days) * 100 if attendance_days else 0
            ),
        }

    return render_template(
        "attendance/term_attendance.html",
        class_=class_,
        students=students,
        attendance_days=attendance_days,
        attendance_records=attendance_records,
        summary=summary,
        term=term,
        year=year,
    )


# Route to mark attendance
@bp.route("/mark-attendance/<int:class_id>", methods=["GET", "POST"])
@login_required
def mark_attendance(class_id):
    """Mark attendance for a class with authorization"""
    class_ = Class.query.get_or_404(class_id)

    # Checking if user has access to mark attendance for this class
    if not has_attendance_access(current_user, class_id):
        flash("You do not have permission to mark attendance for this class!", "danger")
        return redirect(url_for("attendance.dashboard"))

    # Getting current date and term/year
    today = datetime.now().date()
    term = "Term 1"  # THis would be dynamically determined based on date
    year = str(datetime.now().year)

    # getting existing attendance records for today
    attendance_records = Attendance.query.filter_by(class_id=class_id, date=today).all()

    attendance_dict = {r.student_id: r for r in attendance_records}

    if request.method == "POST":
        for student in class_.students:
            status = request.form.get(f"status_{student.id}", "absent")

            if student.id in attendance_dict:
                # Update existing record
                record = attendance_dict[student.id]
                if record.status != status:
                    record.status = status
                    record.method = "manual"
            else:
                # Create a new record
                attendance = Attendance(
                    student_id=student.id,
                    class_id=class_id,
                    date=today,
                    term=term,
                    year=year,
                    status=status,
                    method="manual",
                )
                db.session.commit()
                flash("Attendance saved successfully!", "success")
                return redirect(
                    url_for("attendance.mark_attendance", class_id=class_id)
                )

    return render_template(
        "attendance/mark_attendance.html",
        class_=class_,
        attendance_dict=attendance_dict,
        today=today,
    )


# Helper function for attendance access
def has_attendance_access(user, class_id):
    """Checking if user has permission to
    mark/view attendance for a class,
    and form teachers have access
    """
    if user.role in ["admin", "headteacher"]:
        return True

    if user.role == "teacher":
        # Check if teacher is the form teacher for this class
        teacher = Teacher.query.filter_by(email=user.email).first()
        if teacher and class_id in [c.id for c in teacher.classes]:
            return True

    return False


@bp.route("/scanner")
@login_required
@role_required(["admin", "teacher"])
def scanner():
    classes = Class.query.all()
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
@bp.route("/manual/<int:class_id>", methods=["GET", "POST"])
@login_required
@role_required(["admin", "teacher"])
def manual_attendance(class_id):
    class_ = Class.query.get_or_404(class_id)
    today = datetime.now().date()

    # Getting existing attendance
    attendance_records = Attendance.query.filter_by(class_id=class_id, date=today).all()

    # Creating a dict for a quick lookup
    attendance_dict = {r.student_id: r.status for r in attendance_records}

    if request.method == "POST":
        for student in class_.students:
            status = request.form.get(f"status_{student.id}", "absent")

            if student.id in attendance_dict:
                # Update existing record
                record = next(
                    r for r in attendance_records if r.student_id == student.id
                )
                if record.status != status:
                    record.status = status
                    record.method = "manual"
                    record.scanned_by = current_user.id

            else:
                # Create new record
                attendance = Attendance(
                    student_id=student.id,
                    class_id=class_id,
                    date=today,
                    status=status,
                    method="manual",
                    scanned_by=current_user.id,
                )
                db.session.add(attendance)

        db.session.commit()
        announce(f"Attendance saved for {class_.name}")
        flash("Attendance saved successfully!", "success")
        return redirect(url_for("attendance.manual_attendance", class_id=class_id))

    return render_template(
        "attendance/manual.html",
        class_=class_,
        attendance_dict=attendance_dict,
        today=today,
    )
