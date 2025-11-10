from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta, timezone
from sqlalchemy import func, extract, and_, or_
import calendar
from app import db
from app.models import (
    Teacher,
    TeacherAttendance,
    TeacherAttendanceAudit,
    AttendanceSettings,
    User,
    TermDates,
)
from app.teacher_attendance import bp
from app.decorators import role_required


@bp.route("/index", methods=["GET", "POST"])
@login_required
@role_required(["admin", "headteacher"])
def index():
    teachers = Teacher.query.all()
    return render_template("teacher_attendance/index.html", teachers=teachers)


@bp.route("/mark", methods=["GET", "POST"])
@login_required
def mark_teacher_attendance():
    if current_user.role not in ["admin", "headteacher"]:
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("index"))

    today = date.today()
    selected_date = request.args.get("date", today.isoformat())

    try:
        selected_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
    except ValueError:
        selected_date = today

    # Get all active teachers
    teachers = Teacher.query.filter_by(status="Active").all()

    # Get existing attendance records for the selected date
    existing_attendance = {
        att.teacher_id: att
        for att in TeacherAttendance.query.filter_by(date=selected_date).all()
    }

    if request.method == "POST":
        for teacher in teachers:
            teacher_id = str(teacher.id)
            status = request.form.get(f"status_{teacher_id}")
            check_in = request.form.get(f"check_in_{teacher_id}")
            check_out = request.form.get(f"check_out_{teacher_id}")
            excuse_reason = request.form.get(f"excuse_reason_{teacher_id}")
            notes = request.form.get(f"notes_{teacher_id}")

            if status:
                # Convert time strings to time objects
                check_in_time = None
                check_out_time = None
                late_minutes = 0

                if check_in:
                    try:
                        check_in_time = datetime.strptime(check_in, "%H:%M").time()
                        # Calculate late minutes
                        settings = AttendanceSettings.query.first()
                        if settings and check_in_time > settings.school_start_time:
                            delta = datetime.combine(
                                date.today(), check_in_time
                            ) - datetime.combine(
                                date.today(), settings.school_start_time
                            )
                            late_minutes = int(delta.total_seconds() / 60)
                    except ValueError:
                        check_in_time = None

                if check_out:
                    try:
                        check_out_time = datetime.strptime(check_out, "%H:%M").time()
                    except ValueError:
                        check_out_time = None

                # Update or create attendance record
                if teacher_id in existing_attendance:
                    attendance = existing_attendance[teacher_id]
                    # Create audit trail for changes
                    if (
                        attendance.status != status
                        or attendance.check_in_time != check_in_time
                        or attendance.check_out_time != check_out_time
                    ):

                        audit = TeacherAttendanceAudit(
                            attendance_id=attendance.id,
                            changed_by=current_user.id,
                            change_type="update",
                            old_status=attendance.status,
                            new_status=status,
                            old_check_in=attendance.check_in_time,
                            new_check_in=check_in_time,
                            change_reason=f"Updated by {current_user.username}",
                        )
                        db.session.add(audit)

                    attendance.status = status
                    attendance.check_in_time = check_in_time
                    attendance.check_out_time = check_out_time
                    attendance.late_minutes = late_minutes
                    attendance.excuse_reason = (
                        excuse_reason if status == "excused" else None
                    )
                    attendance.notes = notes
                    attendance.updated_at = datetime.now(timezone.utc)
                else:
                    attendance = TeacherAttendance(
                        teacher_id=teacher.id,
                        date=selected_date,
                        status=status,
                        check_in_time=check_in_time,
                        check_out_time=check_out_time,
                        late_minutes=late_minutes,
                        excuse_reason=excuse_reason if status == "excused" else None,
                        notes=notes,
                        marked_by=current_user.id,
                    )
                    db.session.add(attendance)

        db.session.commit()
        flash("Teacher attendance marked successfully!", "success")
        return redirect(
            url_for(
                "teacher_attendance.mark_teacher_attendance",
                date=selected_date.isoformat(),
            )
        )

    # Get attendance settings
    settings = AttendanceSettings.query.first()
    if not settings:
        settings = AttendanceSettings()
        db.session.add(settings)
        db.session.commit()

    return render_template(
        "teacher_attendance/mark_attendance.html",
        teachers=teachers,
        existing_attendance=existing_attendance,
        selected_date=selected_date,
        settings=settings,
    )


@bp.route("/records", methods=["GET"])
@login_required
def teacher_attendance_records():
    if current_user.role not in ["admin", "headteacher"]:
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("index"))

    # Filter parameters
    teacher_id = request.args.get("teacher_id", type=int)
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    status = request.args.get("status")

    # Build query
    query = TeacherAttendance.query.join(Teacher)

    if teacher_id:
        query = query.filter(TeacherAttendance.teacher_id == teacher_id)
    if start_date:
        query = query.filter(
            TeacherAttendance.date >= datetime.strptime(start_date, "%Y-%m-%d").date()
        )
    if end_date:
        query = query.filter(
            TeacherAttendance.date <= datetime.strptime(end_date, "%Y-%m-%d").date()
        )
    if status:
        query = query.filter(TeacherAttendance.status == status)

    records = query.order_by(TeacherAttendance.date.desc()).all()
    teachers = Teacher.query.filter_by(status="Active").all()

    return render_template(
        "teacher_attendance/records.html",
        records=records,
        teachers=teachers,
        teacher_id=teacher_id,
        start_date=start_date,
        end_date=end_date,
        status=status,
    )


@bp.route("/analytics", methods=["GET"])
@login_required
def teacher_attendance_analytics():
    if current_user.role not in ["admin", "headteacher"]:
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("index"))

    teacher_id = request.args.get("teacher_id", type=int)
    period = request.args.get("period", "month")  # week, month, term, year
    custom_start = request.args.get("custom_start")
    custom_end = request.args.get("custom_end")

    # Date range calculation
    end_date = date.today()
    if period == "week":
        start_date = end_date - timedelta(days=7)
    elif period == "month":
        start_date = end_date - timedelta(days=30)
    elif period == "term":
        # Get current term dates
        current_term = TermDates.query.filter(
            TermDates.start_date <= end_date, TermDates.end_date >= end_date
        ).first()
        if current_term:
            start_date = current_term.start_date
            end_date = current_term.end_date
        else:
            start_date = end_date - timedelta(days=90)  # Fallback to 90 days
    elif period == "year":
        start_date = end_date - timedelta(days=365)
    elif period == "custom" and custom_start and custom_end:
        start_date = datetime.strptime(custom_start, "%Y-%m-%d").date()
        end_date = datetime.strptime(custom_end, "%Y-%m-%d").date()
    else:
        start_date = end_date - timedelta(days=30)  # Default to month

    # Build query
    query = db.session.query(
        TeacherAttendance.teacher_id,
        TeacherAttendance.status,
        func.count(TeacherAttendance.id).label("count"),
    ).filter(TeacherAttendance.date.between(start_date, end_date))

    if teacher_id:
        query = query.filter(TeacherAttendance.teacher_id == teacher_id)
        teacher = Teacher.query.get(teacher_id)
    else:
        teacher = None

    attendance_stats = query.group_by(
        TeacherAttendance.teacher_id, TeacherAttendance.status
    ).all()

    # Process statistics
    stats = {}
    for stat in attendance_stats:
        if stat.teacher_id not in stats:
            stats[stat.teacher_id] = {
                "present": 0,
                "absent": 0,
                "late": 0,
                "excused": 0,
                "total": 0,
            }
        stats[stat.teacher_id][stat.status] = stat.count
        stats[stat.teacher_id]["total"] += stat.count

    # Calculate percentages and additional metrics
    for teacher_id, stat in stats.items():
        total_days = stat["total"]
        if total_days > 0:
            stat["present_percentage"] = round((stat["present"] / total_days) * 100, 1)
            stat["absent_percentage"] = round((stat["absent"] / total_days) * 100, 1)
            stat["late_percentage"] = round((stat["late"] / total_days) * 100, 1)
            stat["attendance_rate"] = round(
                ((stat["present"] + stat["late"]) / total_days) * 100, 1
            )
        else:
            stat.update(
                {
                    "present_percentage": 0,
                    "absent_percentage": 0,
                    "late_percentage": 0,
                    "attendance_rate": 0,
                }
            )

    # Weekly trend data
    weekly_trend = get_weekly_trend_data(teacher_id, start_date, end_date)

    teachers = Teacher.query.filter_by(status="Active").all()

    return render_template(
        "teacher_attendance/analytics.html",
        stats=stats,
        weekly_trend=weekly_trend,
        teachers=teachers,
        teacher=teacher,
        teacher_id=teacher_id,
        period=period,
        start_date=start_date,
        end_date=end_date,
        custom_start=custom_start,
        custom_end=custom_end,
    )


from sqlalchemy import func


def get_weekly_trend_data(teacher_id, start_date, end_date):
    """Get weekly attendance trend data for charts"""

    # Detect database type (SQLite vs Postgres)
    if db.engine.url.drivername.startswith("sqlite"):
        # SQLite uses strftime to group by year-week number
        week_func = func.strftime("%Y-%W", TeacherAttendance.date)
    else:
        # PostgreSQL uses date_trunc
        week_func = func.date_trunc("week", TeacherAttendance.date)

    query = db.session.query(
        week_func.label("week"),
        TeacherAttendance.status,
        func.count(TeacherAttendance.id).label("count"),
    ).filter(TeacherAttendance.date.between(start_date, end_date))

    if teacher_id:
        query = query.filter(TeacherAttendance.teacher_id == teacher_id)

    weekly_data = (
        query.group_by(week_func, TeacherAttendance.status).order_by("week").all()
    )

    # Process for charting
    trend_data = {}
    for data in weekly_data:
        # Handle week field format differences
        week_value = data.week
        if isinstance(week_value, str):
            # SQLite returns strings like "2025-45"
            week_str = week_value
        else:
            # PostgreSQL returns datetime
            week_str = week_value.strftime("%Y-%m-%d")

        if week_str not in trend_data:
            trend_data[week_str] = {"present": 0, "absent": 0, "late": 0, "excused": 0}
        trend_data[week_str][data.status] = data.count

    return trend_data


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def attendance_settings():
    if current_user.role not in ["admin", "headteacher"]:
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("index"))

    settings = AttendanceSettings.query.first()
    if not settings:
        settings = AttendanceSettings()
        db.session.add(settings)
        db.session.commit()

    if request.method == "POST":
        settings.school_start_time = datetime.strptime(
            request.form["school_start_time"], "%H:%M"
        ).time()
        settings.school_end_time = datetime.strptime(
            request.form["school_end_time"], "%H:%M"
        ).time()
        settings.late_threshold_minutes = int(request.form["late_threshold_minutes"])
        settings.half_day_threshold_hours = int(
            request.form["half_day_threshold_hours"]
        )
        settings.auto_mark_absent = "auto_mark_absent" in request.form
        settings.updated_by = current_user.id
        settings.updated_at = datetime.now(timezone.utc)

        db.session.commit()
        flash("Attendance settings updated successfully!", "success")
        return redirect(url_for("teacher_attendance.attendance_settings"))

    return render_template("teacher_attendance/settings.html", settings=settings)
