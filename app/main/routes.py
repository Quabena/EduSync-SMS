from flask import render_template, current_app
from flask_login import login_required, current_user
from app.decorators import role_required
from app.models import User, Student, Teacher, Class, Attendance
from app.main import bp
from datetime import datetime, timedelta, timezone


@bp.route("/")
@login_required
def index():
    # System metrics
    total_students = Student.query.count()
    total_teachers = Teacher.query.count()
    total_classes = Class.query.count()
    total_users = User.query.count()

    # Recent Attendance (last 7 days)
    attendance_data = []
    for i in range(6, -1, -1):
        date = (datetime.now() - timedelta(days=i)).date()
        count = Attendance.query.filter(Attendance.date == date).count()
        attendance_data.append({"date": date.strftime("%Y-%m-%d"), "count": count})

    # Role-based dashboard
    if current_user.role == "admin":
        return render_template(
            "main/admin_dashboard.html",
            title="Admin Dashboard",
            total_students=total_students,
            total_teachers=total_teachers,
            total_classes=total_classes,
            total_users=total_users,
            attendance_data=attendance_data,
            date=datetime.now(timezone.utc),
        )
    elif current_user.role == "headteacher":
        return render_template(
            "main/headteacher_dashboard.html",
            title="Headteacher Dashboard",
            attendance_data=attendance_data,
        )
    else:  # Last one left (for teacher)
        return render_template("main/teacher_dashboard.html", title="Teacher Dashboard")

    return render_template("main/index.html", title="Dashboard")
