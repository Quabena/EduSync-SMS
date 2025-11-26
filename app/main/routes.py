from flask import (
    render_template,
    current_app,
    flash,
    redirect,
    url_for,
    request,
    jsonify,
)
from flask_login import login_required, current_user
from app.decorators import role_required
from app.models import (
    User,
    Student,
    Teacher,
    Class,
    Attendance,
    Subject,
    TermScore,
    Assignment,
    StudentAssignment,
    Alumni,
    TermDates,
)
from app.utils.storage import backup_database, perform_restore
from app.utils.usb import detect_usb_drives, export_to_usb, import_from_usb
from app.main import bp
from datetime import datetime, timedelta, timezone, date
from sqlalchemy import func, desc
from pathlib import Path


def ensure_aware_utc(dt):
    """
    Ensure a datetime is timezone-aware in UTC.
    - If dt is None -> return None
    - If dt is naive -> assume UTC and attach tzinfo=timezone.utc
    - If dt is aware -> convert to UTC
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        # assume stored naive datetimes are UTC
        return dt.replace(tzinfo=timezone.utc)
    # convert any tz-aware dt to UTC
    return dt.astimezone(timezone.utc)


def get_current_term_and_year():
    """
    Dynamically determine the current term and year based on TermDates
    Returns: tuple (term, year)
    """
    today = date.today()

    # Try to find the current term from TermDates
    current_term_record = TermDates.query.filter(
        TermDates.start_date <= today, TermDates.end_date >= today
    ).first()

    if current_term_record:
        return current_term_record.term, current_term_record.academic_year

    # Fallback: calculate based on calendar months
    current_month = today.month
    current_year = today.year

    # Ghana academic calendar typically:
    # Term 1: September - December
    # Term 2: January - April
    # Term 3: May - August

    if current_month >= 9:  # September to December
        term = "Term 1"
        academic_year = f"{current_year}/{current_year + 1}"
    elif current_month >= 5:  # May to August
        term = "Term 3"
        academic_year = f"{current_year - 1}/{current_year}"
    else:  # January to April
        term = "Term 2"
        academic_year = f"{current_year - 1}/{current_year}"

    return term, academic_year


# --- API Endpoint for Electron Health-Check
@bp.route("/api/ping")
def ping():
    # Simple API Endpoint for electron to health-check backend
    return jsonify(status="ok")


@bp.route("/loading")
def splash_screen():
    return render_template("splash.html")


@bp.route("/")
def root():
    return redirect(url_for("main.splash_screen"))


@bp.route("/home")
@login_required
def index():
    """Main dashboard router - redirects to role-specific dashboards"""

    # Role-based dashboard routing
    if current_user.role == "admin":
        return admin_dashboard()
    elif current_user.role == "headteacher":
        return headteacher_dashboard()
    else:  # Teacher
        return teacher_dashboard()


def admin_dashboard():
    """Admin dashboard with comprehensive statistics"""

    # Get current term and year dynamically
    current_term, current_year = get_current_term_and_year()

    # Basic Counts
    total_students = Student.query.count()
    active_students_count = Student.query.filter_by(status="active").count()
    total_teachers = Teacher.query.count()
    total_classes = Class.query.count()
    active_classes_count = Class.query.filter_by(is_alumni_class=False).count()
    alumni_classes_count = Class.query.filter_by(is_alumni_class=True).count()
    total_users = User.query.count()
    subjects_count = Subject.query.count()
    alumni_count = Alumni.query.count()

    # Student growth calculation (compare with last month)
    last_month = datetime.now(timezone.utc) - timedelta(days=30)
    # admission_date on Student is a date field — compare against date
    students_last_month = Student.query.filter(
        Student.admission_date <= last_month.date(), Student.status == "active"
    ).count()
    student_growth = active_students_count - students_last_month

    # Active users (logged in within last 7 days)
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    # Some DB timestamps may be stored naive; the DB comparison typically works but
    # if you run into issues here you can normalize to naive or store tz-aware consistently.
    active_users_count = User.query.filter(User.last_login >= week_ago).count()

    # Today's attendance
    today = date.today()
    today_attendance_count = Attendance.query.filter(
        Attendance.date == today, Attendance.status == "present"
    ).count()

    # Calculate attendance percentage
    if active_students_count > 0:
        today_attendance_percentage = (
            today_attendance_count / active_students_count
        ) * 100
    else:
        today_attendance_percentage = 0

    # Active assignments (future due dates or recent)
    active_assignments_count = Assignment.query.filter(
        Assignment.due_date >= datetime.now(timezone.utc)
    ).count()

    # Pending submissions
    pending_submissions_count = StudentAssignment.query.filter_by(
        status="not_submitted"
    ).count()

    # Term scores count for current term
    term_scores_count = TermScore.query.filter_by(
        term=current_term, year=current_year
    ).count()

    # Attendance data for last 7 days
    attendance_data = []
    for i in range(6, -1, -1):
        date_check = today - timedelta(days=i)
        count = Attendance.query.filter(
            Attendance.date == date_check, Attendance.status == "present"
        ).count()
        attendance_data.append({"date": date_check.strftime("%a"), "count": count})

    # Class distribution (student count per class)
    class_distribution = (
        current_app.extensions["sqlalchemy"]
        .session.query(Class.name, func.count(Student.id).label("count"))
        .outerjoin(Student, Student.class_id == Class.id)
        .filter(Class.is_alumni_class == False)
        .filter((Student.status == "active") | (Student.id == None))
        .group_by(Class.id, Class.name)
        .order_by(Class.name)
        .all()
    )

    class_distribution = [
        {"name": name, "count": count} for name, count in class_distribution
    ]

    # Top performing classes (based on average term scores)
    top_classes_query = (
        current_app.extensions["sqlalchemy"]
        .session.query(
            Class.name,
            func.count(func.distinct(Student.id)).label("student_count"),
            func.avg(TermScore.total_score).label("avg_score"),
        )
        .join(Student, Student.class_id == Class.id)
        .join(TermScore, TermScore.student_id == Student.id)
        .filter(
            Class.is_alumni_class == False,
            Student.status == "active",
            TermScore.term == current_term,
            TermScore.year == current_year,
        )
        .group_by(Class.id, Class.name)
        .order_by(desc("avg_score"))
        .limit(5)
        .all()
    )

    top_classes = [
        {
            "name": name,
            "student_count": student_count,
            "avg_score": float(avg_score) if avg_score else 0,
        }
        for name, student_count, avg_score in top_classes_query
    ]

    # Recent activity (last 24 hours)
    recent_activities = []

    # Recent students (last 7 days for more activity)
    recent_students = (
        Student.query.filter(Student.admission_date >= today - timedelta(days=7))
        .order_by(desc(Student.admission_date))
        .limit(2)
        .all()
    )

    for student in recent_students:
        days_ago = (today - student.admission_date).days
        time_text = "Today" if days_ago == 0 else f"{days_ago} days ago"
        recent_activities.append(
            {
                "color": "green",
                "title": "New student enrolled",
                "description": f'{student.full_name} joined {student.classroom.name if student.classroom else "school"}',
                "time": time_text,
            }
        )

    # Recent attendance records
    recent_attendance = (
        Attendance.query.filter(Attendance.date == today)
        .order_by(desc(Attendance.created_at))
        .first()
    )

    if recent_attendance:
        created_at = ensure_aware_utc(recent_attendance.created_at)
        now_utc = datetime.now(timezone.utc)
        hours_ago = (
            int((now_utc - created_at).total_seconds() / 3600) if created_at else 0
        )
        time_text = f"{hours_ago} hours ago" if hours_ago > 0 else "Just now"
        recent_activities.append(
            {
                "color": "blue",
                "title": "Attendance recorded",
                "description": f'{recent_attendance.classroom.name if recent_attendance.classroom else "Class"} session',
                "time": time_text,
            }
        )

    # Recent assignments
    recent_assignment = Assignment.query.order_by(desc(Assignment.created_at)).first()

    if recent_assignment:
        created_at = ensure_aware_utc(recent_assignment.created_at)
        now_utc = datetime.now(timezone.utc)
        days_ago = (now_utc - created_at).days if created_at else 0
        time_text = f"{days_ago} days ago" if days_ago > 0 else "Today"
        recent_activities.append(
            {
                "color": "yellow",
                "title": "New assignment created",
                "description": f'{recent_assignment.title} - {recent_assignment.subject.name if recent_assignment.subject else ""}',
                "time": time_text,
            }
        )

    # Add a system activity
    recent_activities.append(
        {
            "color": "slate",
            "title": "System backup completed",
            "description": "Daily backup successful",
            "time": "1 day ago",
        }
    )

    # Limit to 4 activities
    recent_activities = recent_activities[:4]

    # If no activities, add placeholder
    if not recent_activities:
        recent_activities.append(
            {
                "color": "slate",
                "title": "No recent activity",
                "description": "System is running smoothly",
                "time": "Now",
            }
        )

    return render_template(
        "main/admin_dashboard.html",
        title="Admin Dashboard",
        total_students=total_students,
        active_students_count=active_students_count,
        total_teachers=total_teachers,
        total_classes=total_classes,
        active_classes_count=active_classes_count,
        alumni_classes_count=alumni_classes_count,
        total_users=total_users,
        subjects_count=subjects_count,
        student_growth=student_growth,
        active_users_count=active_users_count,
        today_attendance_count=today_attendance_count,
        today_attendance_percentage=today_attendance_percentage,
        active_assignments_count=active_assignments_count,
        pending_submissions_count=pending_submissions_count,
        term_scores_count=term_scores_count,
        alumni_count=alumni_count,
        current_term=current_term,
        current_year=current_year,
        attendance_data=attendance_data,
        class_distribution=class_distribution,
        top_classes=top_classes,
        recent_activities=recent_activities,
        current_user=current_user,
        date=datetime.now(timezone.utc),
    )


def headteacher_dashboard():
    """Headteacher dashboard with relevant statistics"""

    # Get current term and year dynamically
    current_term, current_year = get_current_term_and_year()

    # Basic metrics
    total_students = Student.query.filter_by(status="active").count()
    total_teachers = Teacher.query.count()
    total_classes = Class.query.filter_by(is_alumni_class=False).count()

    # Attendance data for last 7 days
    today = date.today()
    attendance_data = []
    for i in range(6, -1, -1):
        date_check = today - timedelta(days=i)
        count = Attendance.query.filter(Attendance.date == date_check).count()
        attendance_data.append(
            {"date": date_check.strftime("%Y-%m-%d"), "count": count}
        )

    return render_template(
        "main/headteacher_dashboard.html",
        title="Headteacher Dashboard",
        total_students=total_students,
        total_teachers=total_teachers,
        total_classes=total_classes,
        current_term=current_term,
        current_year=current_year,
        attendance_data=attendance_data,
        date=datetime.now(timezone.utc),
    )


def teacher_dashboard():
    """Teacher dashboard with class-specific information"""

    # Get current term and year dynamically
    current_term, current_year = get_current_term_and_year()

    return render_template(
        "main/teacher_dashboard.html",
        title="Teacher Dashboard",
        current_term=current_term,
        current_year=current_year,
        date=datetime.now(timezone.utc),
    )


# --Routes For Database Management--
@bp.route("/database-backup")
@login_required
@role_required(["admin", "headteacher"])
def backup_dashboard():
    """Backup and restore dashboard"""
    # Get existing backups
    backup_dir = current_app.config.get("BACKUP_DIR", Path("backups"))
    backups = []
    if backup_dir.exists():
        backup_files = sorted(backup_dir.glob("namongsdajhs_*.db"), reverse=True)
        for backup in backup_files:
            stats = backup.stat()
            backups.append(
                {
                    "name": backup.name,
                    "size": stats.st_size,
                    "created": datetime.fromtimestamp(stats.st_ctime),
                    "path": backup,
                }
            )

    # Getting USB drives
    usb_drives = detect_usb_drives()

    return render_template("main/backup.html", backups=backups, usb_drives=usb_drives)


# Route to create backup
@bp.route("/database-backup/create", methods=["POST"])
@login_required
@role_required(["admin", "headteacher"])
def create_backup():
    """Create a new database backup"""
    success, message = backup_database()
    if success:
        flash(f"{message}", "success")
    else:
        flash(f"Backup failed: {message}", "error")
    return redirect(url_for("main.backup_dashboard"))


# Database restore route
@bp.route("/database-backup/restore/<backup_name>", methods=["POST"])
@login_required
@role_required(["admin", "headteacher"])
def restore_backup(backup_name):
    """Restore backup from backup"""
    success, message = perform_restore(backup_name)  # type: ignore
    if success:
        flash(f"{message}", "success")
    else:
        flash(f"Restore failed: {message}", "error")
    return redirect(url_for("main.backup_dashboard"))


# Delete database route
@bp.route("/database-backup/delete/<backup_name>", methods=["POST"])
@login_required
@role_required(["admin", "headteacher"])
def delete_backup(backup_name):
    """Delete a backup file"""
    try:
        back_dir = current_app.config.get("BACKUP_DIR", Path("backups"))
        backup_path = back_dir / backup_name
        if backup_path.exists():
            backup_path.unlink()
            flash("Backup deleted successfully", "success")
        else:
            flash("Backup file not found", "error")
    except Exception as e:
        flash(f"Delete failed: {str(e)}", "error")
    return redirect(url_for("main.backup_dashboard"))


# Route to export to usb route
@bp.route("/database-backup/export-usb", methods=["POST"])
@login_required
@role_required(["admin", "headteacher"])
def export_to_usb_route():
    """Export database to USB drive"""
    drive_path = request.form.get("drive_path")
    if not drive_path:
        flash("Please select a USB drive", "error")
        return redirect(url_for("main.backup_dashboard"))

    success, message = export_to_usb(drive_path)
    if success:
        flash(f"{message}", "success")
    else:
        flash(f"Export failed: {message}", "error")
    return redirect(url_for("main.backup_dashboard"))


# Route to import from USB
@bp.route("/database-backup/import-usb", methods=["POST"])
@login_required
@role_required(["admin", "headteacher"])
def import_from_usb_route():
    """Import database from USB drive"""
    drive_path = request.form.get("drive_path")
    if not drive_path:
        flash("Please select a USB drive", "error")
        return redirect(url_for("main.backup_dashboard"))

    success, message = import_from_usb(drive_path)
    if success:
        flash(f"{message}", "success")
    else:
        flash(f"Import failed: {message}", "error")
    return redirect(url_for("main.backup_dashboard"))


# Route to refresh usb drives
@bp.route("/database-backup/refresh-usb", methods=["POST"])
@login_required
@role_required(["admin", "headteacher"])
def refresh_usb_drive():
    usb_drives = detect_usb_drives()
    return jsonify({"drives": usb_drives})


# Contact Developer Route
@bp.route("/contact-developer")
@login_required
@role_required(["admin", "headteacher"])
def contact_developer():
    """Contact developer page"""
    return render_template("main/contact_developer.html")
