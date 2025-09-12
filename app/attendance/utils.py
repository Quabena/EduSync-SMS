# attendance/utils.py - Create this new file for utility functions
from datetime import datetime, timedelta, date
from flask import current_app
from app import db
from app.models import Class
from app.models import Attendance, SchoolCalendar, Student
from sqlalchemy import func, case


def get_attendance_stats(class_id, start_date, end_date):
    """Get comprehensive attendance statistics for a class"""
    stats = (
        db.session.query(
            func.count(Attendance.id).label("total_records"),
            func.count(case((Attendance.status == "present", 1))).label(
                "present_count"
            ),
            func.count(case((Attendance.status == "absent", 1))).label("absent_count"),
            func.count(case((Attendance.status == "late", 1))).label("late_count"),
            func.count(case((Attendance.status == "excused", 1))).label(
                "excused_count"
            ),
        )
        .filter(
            Attendance.class_id == class_id,
            Attendance.date.between(start_date, end_date),
        )
        .first()
    )

    if not stats:  # no rows at all
        return {
            "total": 0,
            "present": 0,
            "absent": 0,
            "late": 0,
            "excused": 0,
            "attendance_rate": 0,
        }

    return {
        "total": stats.total_records,
        "present": stats.present_count,
        "absent": stats.absent_count,
        "late": stats.late_count,
        "excused": stats.excused_count,
        "attendance_rate": (
            (stats.present_count / stats.total_records * 100)
            if stats.total_records > 0
            else 0
        ),
    }


def get_student_attendance_trend(student_id, days=30):
    """Get attendance trend for a student over specified days"""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    records = (
        Attendance.query.filter(
            Attendance.student_id == student_id,
            Attendance.date.between(start_date, end_date),
        )
        .order_by(Attendance.date)
        .all()
    )

    return [
        {
            "date": record.date,
            "status": record.status,
            "excused": record.status == "excused",
        }
        for record in records
    ]


def check_chronic_absenteeism(class_id, threshold=0.8):
    """Identify students with chronic absenteeism"""
    # Get school days in current term
    current_term = "Term 1"  # This should be dynamic
    current_year = str(datetime.now().year)

    school_days = SchoolCalendar.query.filter_by(
        day_type="school_day", term=current_term, year=current_year
    ).count()

    if school_days == 0:
        return []

    # Get attendance for each student
    students = Student.query.filter_by(class_id=class_id).all()
    chronic_absentees = []

    for student in students:
        present_days = Attendance.query.filter_by(
            student_id=student.id,
            status="present",
            term=current_term,
            year=current_year,
        ).count()

        attendance_rate = present_days / school_days
        if attendance_rate < threshold:
            chronic_absentees.append(
                {
                    "student": student,
                    "attendance_rate": attendance_rate,
                    "absent_days": school_days - present_days,
                }
            )

    return chronic_absentees


def generate_attendance_report(class_id, term, year, format="csv"):
    """Generate comprehensive attendance report"""
    attendance_data = (
        Attendance.query.filter_by(class_id=class_id, term=term, year=year)
        .order_by(Attendance.date, Student.surname)
        .all()
    )

    # This would generate a comprehensive report
    # Implementation would depend on the desired format (CSV, PDF, etc.)
    return attendance_data


def get_daily_attendance_rate(class_id, date):
    """Get attendance rate for a specific class on a specific date"""
    present_count = Attendance.query.filter_by(
        class_id=class_id, date=date, status="present"
    ).count()

    total_count = Attendance.query.filter_by(class_id=class_id, date=date).count()

    return (present_count / total_count * 100) if total_count > 0 else 0


def get_class_attendance_summary(class_id, start_date, end_date):
    """Get comprehensive attendance summary for a class"""
    attendance_data = Attendance.query.filter(
        Attendance.class_id == class_id, Attendance.date.between(start_date, end_date)
    ).all()

    summary = {
        "total_days": (end_date - start_date).days + 1,
        "present": 0,
        "absent": 0,
        "late": 0,
        "excused": 0,
        "records": len(attendance_data),
    }

    for record in attendance_data:
        summary[record.status] += 1

    summary["attendance_rate"] = (
        (summary["present"] / summary["records"] * 100) if summary["records"] > 0 else 0
    )

    return summary


def get_recent_attendance_activity(limit=10):
    """Get recent attendance marking activity"""
    return (
        Attendance.query.join(Student)
        .join(Class)
        .order_by(Attendance.created_at.desc())
        .limit(limit)
        .all()
    )
