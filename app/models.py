from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timezone
from sqlalchemy import event
from sqlalchemy.orm import validates
import os
from flask import current_app


# Association tables
student_subject = db.Table(
    "student_subject",
    db.Column("student_id", db.Integer, db.ForeignKey("student.id"), primary_key=True),
    db.Column("subject_id", db.Integer, db.ForeignKey("subject.id"), primary_key=True),
)

teacher_class = db.Table(
    "teacher_class",
    db.Column("teacher_id", db.Integer, db.ForeignKey("teacher.id"), primary_key=True),
    db.Column("class_id", db.Integer, db.ForeignKey("class.id"), primary_key=True),
)

# Association table for teacher-subject-class assignments
# teacher_subject_class = db.Table(
#     "teacher_subject_class",
#     db.Column("teacher_id", db.Integer, db.ForeignKey("teacher.id"), primary_key=True),
#     db.Column("subject_id", db.Integer, db.ForeignKey("subject.id"), primary_key=True),
#     db.Column("class_id", db.Integer, db.ForeignKey("class.id"), primary_key=True),
# )


# Class Model
class Class(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    level = db.Column(db.String(20))
    section = db.Column(db.String(1))
    master_class = db.Column(db.String(50))  # For grouping classes

    students = db.relationship("Student", backref="classroom", lazy=True)
    teachers = db.relationship(
        "Teacher", secondary=teacher_class, back_populates="classes"
    )
    subject_assignments = db.relationship(
        "TeacherSubjectClass", back_populates="class_"
    )

    def __repr__(self) -> str:
        return self.name

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


# Subject Class Model
class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    code = db.Column(db.String(10))

    def __init__(self, name, code):
        self.name = name
        self.code = code

    students = db.relationship(
        "Student", secondary=student_subject, back_populates="subjects"
    )
    teachers = db.relationship("Teacher", back_populates="specialization")

    class_assignments = db.relationship("TeacherSubjectClass", back_populates="subject")

    def __repr__(self) -> str:
        return self.name


# TeacherSubjectClass Model for tracking sybject assignments to teachers
class TeacherSubjectClass(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"))
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"))
    class_id = db.Column(db.Integer, db.ForeignKey("class.id"))
    is_active = db.Column(db.Boolean, default=True)

    # Add unique constraint instead of composite primary key
    __table_args__ = (
        db.UniqueConstraint(
            "teacher_id", "subject_id", "class_id", name="unique_assignment"
        ),
    )

    # Relationships
    teacher = db.relationship("Teacher", back_populates="subject_assignments")
    subject = db.relationship("Subject", back_populates="class_assignments")
    class_ = db.relationship("Class", back_populates="subject_assignments")

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


# Student Class Model
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    middle_name = db.Column(db.String(50))
    surname = db.Column(db.String(50), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    admission_date = db.Column(db.Date, nullable=True)
    hometown = db.Column(db.String(100))
    father_name = db.Column(db.String(100))
    mother_name = db.Column(db.String(100))
    guardian_name = db.Column(db.String(100))
    guardian_contact = db.Column(db.String(20))
    religion = db.Column(db.String(100), nullable=True)
    medical_records = db.Column(db.Text)
    height = db.Column(db.Integer, nullable=True)
    weight = db.Column(db.Integer, nullable=True)
    photo_path = db.Column(db.String(200))
    class_id = db.Column(db.Integer, db.ForeignKey("class.id"))
    learning_style = db.Column(
        db.String(20)
    )  # Will be used for creating the learning style assessment engine

    # Relationships
    subjects = db.relationship(
        "Subject", secondary=student_subject, back_populates="students"
    )
    academic_records = db.relationship("AcademicRecord", back_populates="student")
    term_scores = db.relationship("TermScore", back_populates="student")

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def age(self):
        today = date.today()
        born = self.date_of_birth
        return (
            today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        )

    @property
    def full_name(self):
        return (
            f"{self.first_name} {self.middle_name} {self.surname}"
            if self.middle_name
            else f"{self.first_name} {self.surname}"
        )

    def __repr__(self) -> str:
        return self.full_name


# Teacher Class Model
class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    middle_name = db.Column(db.String(50))
    surname = db.Column(db.String(50), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    hometown = db.Column(db.String(100))
    college_attended = db.Column(db.String(100))
    area_of_specialization = db.Column(db.String(100))
    academic_certificate = db.Column(db.String(100))
    academic_area_of_study = db.Column(db.String(100))
    academic_college = db.Column(db.String(100))
    professional_certificate = db.Column(db.String(100))
    professional_area_of_study = db.Column(db.String(100))
    professional_college = db.Column(db.String(100))
    staff_id = db.Column(db.String(20), unique=True)
    registered_number = db.Column(db.String(20), unique=True)
    ntc_number = db.Column(db.String(20), unique=True)
    ssnit_number = db.Column(db.String(20), unique=True)
    phone_number = db.Column(db.String(10), unique=True)
    email = db.Column(db.String(120), unique=True)
    emergency_contact_name = db.Column(db.String(100))
    emergency_contact_number = db.Column(db.String(10))
    photo_path = db.Column(db.String(200))
    certificate_paths = db.Column(db.Text, nullable=True)

    # Relationships
    specialization_id = db.Column(db.Integer, db.ForeignKey("subject.id"))
    specialization = db.relationship("Subject", back_populates="teachers")
    classes = db.relationship(
        "Class", secondary=teacher_class, back_populates="teachers"
    )
    subject_assignments = db.relationship(
        "TeacherSubjectClass", back_populates="teacher"
    )

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def age(self):
        today = date.today()
        born = self.date_of_birth
        return (
            today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        )

    @property
    def full_name(self):
        return (
            f"{self.first_name} {self.middle_name} {self.surname}"
            if self.middle_name
            else f"{self.first_name} {self.surname}"
        )

    def __repr__(self) -> str:
        return self.full_name


# TermScore Model for scoring component scores
class TermScore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("class.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    term = db.Column(db.String(20), nullable=False)
    year = db.Column(db.String(10), nullable=False)
    individual_test = db.Column(db.Float, default=0.0)
    group_work = db.Column(db.Float, default=0.0)
    class_test = db.Column(db.Float, default=0.0)
    project = db.Column(db.Float, default=0.0)
    class_total = db.Column(db.Float, default=0.0)  # Sum of the above 60
    exam_score = db.Column(db.Float, default=0.0)  # 100 marks max
    total_score = db.Column(db.Float, default=0.0)

    # Relationships
    student = db.relationship("Student", back_populates="term_scores")
    subject = db.relationship("Subject")
    class_ = db.relationship("Class")
    teacher = db.relationship("Teacher")

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    def calculate_totals(self):
        # Calculate class total (sum of components, max is 60)
        self.class_total = min(
            (self.individual_test or 0)
            + (self.group_work or 0)
            + (self.class_test or 0)
            + (self.project or 0),
            60,
        )

        # Scaling class total to 50%
        scaled_class = (self.class_total / 60) * 50 if self.class_total else 0

        # Scaling exam score to 50%
        scaled_exam = (self.class_total / 100) * 50 if self.exam_score else 0

        # Calculating total score (100%)
        self.total_score = scaled_class + scaled_exam

        return self.total_score


# Academic Records Model
class AcademicRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"))
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"))
    term = db.Column(db.String(20))
    year = db.Column(db.String(10))
    score = db.Column(db.Float)
    grade = db.Column(db.String(2))
    remarks = db.Column(db.Text)

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    # Relationships
    student = db.relationship("Student", back_populates="academic_records")
    subject = db.relationship("Subject")


# Medical Records Model
class MedicalRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"))
    condition = db.Column(db.String(100))
    diagnosis_date = db.Column(db.Date)
    treatment = db.Column(db.Text)
    notes = db.Column(db.Text)

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    # Relationship
    student = db.relationship("Student", backref="medical_history")


# Attendance Class Model
class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("class.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    term = db.Column(db.String(20), nullable=False)
    year = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(10), nullable=False)
    method = db.Column(db.String(10))  # Manual input, or QR

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


# Enrollment Class Model
class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"))
    class_id = db.Column(db.Integer, db.ForeignKey("class.id"))
    session_year = db.Column(db.String(20), nullable=False)

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


# Grade Class Model
class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(
        db.Integer, db.ForeignKey("enrollment.id"), nullable=False
    )
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    term = db.Column(db.String(10), nullable=False)
    score = db.Column(db.Float, nullable=False)
    remarks = db.Column(db.String(200))

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class HallPass(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    destination = db.Column(db.String(100), nullable=False)
    qr_path = db.Column(db.String(200), nullable=False)
    issued_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    scanned_at = db.Column(db.DateTime)
    scanned_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    status = db.Column(
        db.String(20), default="active"
    )  # Could be active, unused, expired

    student = db.relationship("Student", backref=db.backref("hallpasses", lazy=True))
    scanner = db.relationship("User", foreign_keys=[scanned_by])

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def is_active(self):
        return (
            self.status == "active"
            and (datetime.now(timezone.utc) - self.issued_at).total_seconds() < 3600
        )  # valid for 1 hour

    def mark_used(self, user_id):
        self.status = "used"
        self.scanned_at = datetime.now(timezone.utc)
        self.scanned_by = user_id
        db.session.commit()


# Classroom class
class Classroom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mood_data = db.Column(db.JSON)  # for mood-tracking
    qr_code = db.Column(db.String(100))  # Class-specific QR

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


# MoodEntry class - for classroom mood tracking/analysis
class MoodEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("class.id"), nullable=False)
    notes = db.Column(db.Text, nullable=False)
    sentiment = db.Column(
        db.String(20), nullable=False
    )  # positive, negative or neutral
    polarity = db.Column(db.Float, nullable=False)  # for sentiment score (-1 to 1)
    recorded_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    recorded_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    # Relationships
    classroom = db.relationship("Class", backref=db.backref("mood_entries", lazy=True))
    recorder = db.relationship("User", foreign_keys=[recorded_by])

    def __repr__(self) -> str:
        return f"<MoodEntry {self.id} for Class {self.class_id} - {self.sentiment}>"


# User Class Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), nullable=False)  # admin, headteacher, teacher
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime)

    def __init__(self, username, email, role):
        self.username = username
        self.email = email
        self.role = role

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


# Assignment Class Model
class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("class.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    due_date = db.Column(db.DateTime)
    total_marks = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    document_path = db.Column(db.String(200))

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    # Relationships
    subject = db.relationship("Subject")
    classroom = db.relationship("Class")
    teacher = db.relationship("Teacher")
    submissions = db.relationship("StudentAssignment", back_populates="assignment")

    def __repr__(self) -> str:
        return f"<Assignment {self.title}>"


# StudentAssignment Class Model
class StudentAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    assignment_id = db.Column(
        db.Integer, db.ForeignKey("assignment.id"), nullable=False
    )
    submission_path = db.Column(db.String(200))  # For student's submission
    submitted_at = db.Column(db.DateTime)
    marks_obtained = db.Column(db.Float)
    feedback = db.Column(db.Text)
    status = db.Column(
        db.String(20), default="not_submitted"
    )  # will be not_submitted, submitted, graded

    # Relationships
    student = db.relationship("Student", backref="assignments")
    assignment = db.relationship("Assignment", back_populates="submissions")

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def status_class(self):
        return {
            "not_submitted": "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
            "submitted": "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
            "graded": "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
        }.get(self.status, "")

    def __repr__(self) -> str:
        return f"<Submission {self.id} for {self.assignment.title}>"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Event Listeners for file cleanup
@event.listens_for(Student, "after_delete")
@event.listens_for(Teacher, "after_delete")
def delete_photos(mapper, connection, target):
    if target.photo_path:
        try:
            photo_path = os.path.join(
                current_app.config["DOCUMENT_DIR"], target.photo_path
            )
            if os.path.exists(photo_path):
                os.remove(photo_path)
        except Exception as e:
            current_app.logger.error(f"Error deleting photo: {str(e)}")
