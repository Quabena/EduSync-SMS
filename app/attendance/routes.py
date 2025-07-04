from app.utils.voice import announce
from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from app.decorators import role_required
from app import db
from app.models import Student, Class, Attendance, HallPass
from app.attendance import bp
from datetime import datetime
import json


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
