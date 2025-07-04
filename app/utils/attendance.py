"""
Cheat detection algorithm.
This is necessary to detect cheating in attendance
registration.
"""

from datetime import datetime, timedelta
from app.models import Attendance, HallPass
from app import db


def detect_cheating(class_id, date=None):
    if date is None:
        date = datetime.now().date()

    # Getting all attendance for the class on the given date
    attendance_records = Attendance.query.filter_by(class_id=class_id, date=date).all()

    # Analyzing patterns
    alerts = []

    # Checking for duplicate scans
    student_records = {}
    for record in attendance_records:
        if record.student_id in student_records:
            student_records[record.student_id].append(record)
        else:
            student_records[record.student_id] = [record]

    for student_id, records in student_records.items():
        if len(records) > 1:
            # Checking multiple attendance records for same student
            times = [r.timestamp.strftime("%H:%M:%S") for r in records if r.timestamp]
            alerts.append(
                {
                    "type": "multiple_records",
                    "student_id": student_id,
                    "message": f'Student has multiple attendance records: {", ".join(times)}',
                }
            )

    # Checking hall-passes during class time
    hallpasses = HallPass.query.filter(
        HallPass.issued_at >= datetime.combine(date, datetime.min.time()),
        HallPass.issued_at <= datetime.combine(date, datetime.max.time()),
        HallPass.student.has(class_id=class_id),
    ).all()

    for pass_ in hallpasses:
        # Checking if hall-pass was active during class but student was marked present
        attendance = next(
            (r for r in attendance_records if r.student_id == pass_.student_id), None
        )
        if attendance and attendance.status == "present":
            # Checking if hall-pass overlaps with class time
            if (
                pass_.issued_at.time()
                < datetime.now().time()
                < (pass_.issued_at + timedelta(minutes=15)).time()
            ):
                alerts.append(
                    {
                        "type": "hallpass_overlap",
                        "student_id": pass_.student_id,
                        "message": f"Student was marked present but had active hall-pass to {pass_.destination}",
                    }
                )

    # Detecting suspicious timing patterns
    qr_records = [r for r in attendance_records if r.method == "QR"]
    if len(qr_records) > 3:
        # Checking for clustered timestamps
        timestamps = sorted([r.timestamp for r in qr_records if r.timestamp])
        time_diffs = [
            (timestamps[i + 1]) - timestamps[i].total_seconds()
            for i in range(len(timestamps) - 1)
        ]

        # If many scans within short time then there is a possible QR sharing
        if any(diff < 5 for diff in time_diffs):  # if less than 5 seconds between scans
            alerts.append(
                {
                    "type": "clustered_scans",
                    "message": f"Multiple QR scans detected in rapid succession - possible QR sharing!",
                }
            )
    return alerts
