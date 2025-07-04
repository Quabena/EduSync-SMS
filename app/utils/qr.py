"""QR Ecosystem Implementation"""

import os
import qrcode
from flask import current_app
import qrcode.constants
from app import db
from app.models import Class, Student, HallPass
from datetime import datetime


def generate_qr_code(data, filename_prefix):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Saving to file
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.png"
    save_path = os.path.join(current_app.config["QR_DIR"], filename)
    img.save(save_path)  # type: ignore

    return filename, save_path


def generate_student_qr(student_id):
    student = Student.query.get(student_id)
    if not student:
        return None

    qr_data = f"STUDENT:{student_id}:{student.full_name.replace(' ', '_')}"
    return generate_qr_code(qr_data, f"student_{student.id}")


def generate_class_qr(class_id):
    class_ = Class.query.get(class_id)
    if not class_:
        return None

    qr_data = f"STUDENT:{class_id}:{class_.name.replace(' ', '_')}"
    return generate_qr_code(qr_data, f"class_{class_.id}")


def generate_hallpass(student_id, destination):
    student = Student.query.get(student_id)
    if not student:
        return None, None

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    qr_data = f"HALLPASS:{student.id}:{destination}:{timestamp}"
    filename, path = generate_qr_code(qr_data, f"hallpass_{student.id}")

    # Creating hallpass record
    hallpass = HallPass(
        student_id=student.id,
        destination=destination,
        qr_path=filename,
        issued_at=datetime.now(),
        status="active",
    )
    db.session.add(hallpass)
    db.session.commit()

    return filename, path
