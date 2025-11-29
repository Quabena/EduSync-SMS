from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timezone, time
from sqlalchemy import event, func
from sqlalchemy.orm import validates
from sqlalchemy.ext.hybrid import hybrid_property
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
    is_alumni_class = db.Column(
        db.Boolean, default=False
    )  # Flag to identify alumni classes

    students = db.relationship(
        "Student",
        back_populates="classroom",
        foreign_keys="Student.class_id",
        lazy="dynamic",
    )

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

    def get_active_students(self):
        """Get only active students (non-alumni)"""
        return self.students.filter(Student.status == "active").all()

    @classmethod
    def get_alumni_class(cls, graduation_year):
        """Get or create alumni class for a specific graduation year"""
        alumni_class_name = f"Alumni - Class of {graduation_year}"
        alumni_class = cls.query.filter_by(
            name=alumni_class_name, is_alumni_class=True
        ).first()

        if not alumni_class:
            alumni_class = cls(
                name=alumni_class_name,
                level="Alumni",
                section="A",
                master_class="Alumni",
                is_alumni_class=True,
            )
            db.session.add(alumni_class)
            db.session.commit()

        return alumni_class

    @classmethod
    def get_active_classes(cls):
        """Get all non-alumni classes"""
        return cls.query.filter_by(is_alumni_class=False).order_by(cls.name).all()

    def get_promotion_paths(self):
        """Getting available promotion paths from this class"""
        return (
            PromotionPath.query.filter_by(from_class_id=self.id, is_active=True)
            .order_by(PromotionPath.order)
            .all()
        )

    def get_students_eligible_for_promotion(self):
        """Getting students who can be promoted (active students)"""
        return self.students.filter(Student.status == "active").all()

    @classmethod
    def get_promotion_hierarchy(cls):
        """Getting the promotion hierarchy"""
        paths = (
            PromotionPath.query.filter_by(is_active=True)
            .order_by(PromotionPath.order)
            .all()
        )
        hierarchy = {}
        for path in paths:
            if path.from_class_id not in hierarchy:
                hierarchy[path.from_class_id] = []
            hierarchy[path.from_class_id].append(path.to_class)
        return hierarchy


# Subject Class Model
class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    code = db.Column(db.String(10))
    is_core = db.Column(db.Boolean, default=False)

    def __init__(self, name, code, is_core=False):
        self.name = name
        self.code = code
        self.is_core = is_core

    students = db.relationship(
        "Student", secondary=student_subject, back_populates="subjects"
    )
    teachers = db.relationship("Teacher", back_populates="specialization")

    class_assignments = db.relationship("TeacherSubjectClass", back_populates="subject")

    def __repr__(self) -> str:
        return self.name


# School Info Model Class
class SchoolInfo(db.Model):
    """Store school information for reports"""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    motto = db.Column(db.String(200))
    address = db.Column(db.Text)
    phone = db.Column(db.String(10))
    email = db.Column(db.String(120))
    website = db.Column(db.String(200))
    logo_path = db.Column(db.String(200))

    def __repr__(self) -> str:
        return f"<SchoolInfo {self.name}>"

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


# Class for Term Dates
class TermDates(db.Model):
    """Store term dates for academic years"""

    id = db.Column(db.Integer, primary_key=True)
    academic_year = db.Column(db.String(20), nullable=False)
    term = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    vacation_date = db.Column(db.Date, nullable=False)
    reopening_date = db.Column(db.Date, nullable=False)

    def __repr__(self) -> str:
        return f"<TermDates {self.academic_year} {self.term}>"

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


# Class for leaving remarks on students
class StudentRemarks(db.Model):
    """Store teacher remarks for students"""

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    term = db.Column(db.String(20), nullable=False)
    year = db.Column(db.String(10), nullable=False)
    conduct = db.Column(db.Text)
    attitude = db.Column(db.Text)
    interests = db.Column(db.Text)
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    # Relationships
    student = db.relationship("Student", backref="student_remarks")
    teacher = db.relationship("Teacher", backref="given_remarks")

    def __repr__(self) -> str:
        return f"<StudentRemarks {self.student_id} {self.term} {self.year}>"

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


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
    live_at = db.Column(db.String(100))
    digital_address = db.Column(db.String(12))
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
    status = db.Column(db.String(20), default="active")
    updated_at = db.Column(
        db.DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )
    interest = db.Column(
        db.String(20)
    )  # Will be used for creating the learning style assessment engine
    original_class_id = db.Column(db.Integer, db.ForeignKey("class.id"))

    # Relationships
    subjects = db.relationship(
        "Subject", secondary=student_subject, back_populates="students"
    )
    academic_records = db.relationship("AcademicRecord", back_populates="student")
    term_scores = db.relationship("TermScore", back_populates="student")
    classroom = db.relationship(
        "Class", foreign_keys=[class_id], back_populates="students"
    )
    original_class = db.relationship(
        "Class", foreign_keys=[original_class_id], backref="former_students"
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

    @hybrid_property
    def full_name(self):  # type: ignore
        return f"{self.first_name or ''} {self.middle_name or ''} {self.surname or ''}".strip()

    @full_name.expression
    def full_name(cls):
        return func.concat(cls.first_name, " ", cls.middle_name, " ", cls.surname)

    def is_active(self):
        """Check if student is currently active (not graduated)"""
        return self.status == "active" and not self.classroom.name.startswith("Alumni")

    def __repr__(self) -> str:
        return self.full_name

    def promote_student(self, to_class_id, promoted_by_user, notes=None):
        """Promoting a student to another class"""
        from_class_id = self.class_id
        self.class_id = to_class_id

        # Creating promotion record
        promotion = PromotionRecord(
            student_id=self.id,
            from_class_id=from_class_id,
            to_class_id=to_class_id,
            promoted_by=promoted_by_user.id,
            notes=notes,
        )
        db.session.add(promotion)
        db.session.commit()

        return promotion


# ---Model for tracking student's Graduation Status---
class GraduationStatus(db.Model):
    """Track student graduation status"""

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    graduation_year = db.Column(db.String(10), nullable=False)
    graduation_date = db.Column(db.Date)
    status = db.Column(
        db.String(20), default="completed"
    )  # completed, transferred, dropped-out
    final_grade = db.Column(db.String(5))
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    # Relationships
    student = db.relationship("Student", backref="graduation_records")

    def __repr__(self) -> str:
        return f"<GraduationStatus {self.student_id} {self.graduation_year}>"

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


# --- Student Promotion Model ---
class PromotionPath(db.Model):
    """Path for student promotion between classes"""

    id = db.Column(db.Integer, primary_key=True)
    from_class_id = db.Column(db.Integer, db.ForeignKey("class.id"), nullable=False)
    to_class_id = db.Column(db.Integer, db.ForeignKey("class.id"), nullable=False)
    order = db.Column(db.Integer, default=0)  # For ordering multiple paths
    is_active = db.Column(db.Boolean, default=True)

    # RElationships
    from_class = db.relationship(
        "Class", foreign_keys=[from_class_id], backref="promotion_paths_from"
    )
    to_class = db.relationship(
        "Class", foreign_keys=[to_class_id], backref="promotion_paths_to"
    )

    def __repr__(self) -> str:
        return f"<PromotionPath {self.from_class.name} -> {self.to_class.name}>"

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class PromotionRecord(db.Model):
    """Tracking student promotion history"""

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    from_class_id = db.Column(db.Integer, db.ForeignKey("class.id"), nullable=False)
    to_class_id = db.Column(db.Integer, db.ForeignKey("class.id"), nullable=False)
    promoted_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    promotion_date = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    notes = db.Column(db.Text)

    # Relationships
    student = db.relationship("Student", backref="promotion_history")
    from_class = db.relationship("Class", foreign_keys=[from_class_id])
    to_class = db.relationship("Class", foreign_keys=[to_class_id])
    promoter = db.relationship("User", foreign_keys=[promoted_by])

    def __repr__(self) -> str:
        return f"<PromotionRecord {self.student.full_name} {self.from_class.name}->{self.to_class.name}>"

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


# ---Alumni---
class Alumni(db.Model):
    """Archive for graduated students"""

    id = db.Column(db.Integer, primary_key=True)
    original_student_id = db.Column(db.Integer, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    middle_name = db.Column(db.String(50))
    surname = db.Column(db.String(50), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    admission_date = db.Column(db.Date, nullable=False)
    graduation_year = db.Column(db.String(10), nullable=False)
    graduation_date = db.Column(db.Date, nullable=False)
    hometown = db.Column(db.String(100))
    father_name = db.Column(db.String(100))
    mother_name = db.Column(db.String(100))
    guardian_name = db.Column(db.String(100))
    guardian_contact = db.Column(db.String(10))
    religion = db.Column(db.String(100), nullable=True)
    medical_records = db.Column(db.Text)
    photo_path = db.Column(db.String(200))
    final_class = db.Column(db.String(50))  # class of 2024 etc.
    archived_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<Alumni {self.first_name} {self.surname} ({self.graduation_year})>"

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    @hybrid_property
    def full_name(self):  # type: ignore
        return f"{self.first_name or ''} {self.middle_name or ''} {self.surname or ''}".strip()

    @property
    def age(self):
        today = date.today()
        born = self.date_of_birth
        return (
            today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        )


# Teacher Class Model
class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    middle_name = db.Column(db.String(50))
    surname = db.Column(db.String(50), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    date_posted_to_present_station = db.Column(db.Date)
    first_appointment_date = db.Column(db.Date)
    last_promotion_date = db.Column(db.Date)
    hometown = db.Column(db.String(100))
    hometown_district = db.Column(db.String(100))
    hometown_region = db.Column(db.String(100))
    religion = db.Column(db.String(50))
    ghana_card = db.Column(db.String(15))
    live_at = db.Column(db.String(100))
    digital_address = db.Column(db.String(12))
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
    current_rank = db.Column(db.String(100))
    salary_grade = db.Column(db.String(5))
    salary_grade_type = db.Column(db.String(3))
    emergency_contact_name = db.Column(db.String(100))
    emergency_contact_number = db.Column(db.String(10))
    photo_path = db.Column(db.String(200))
    certificate_paths = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default="Active")
    staff_role = db.Column(db.String(20))
    marital_status = db.Column(db.String(20))

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
        scaled_exam = (self.exam_score / 100) * 50 if self.exam_score else 0

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
    excuse_reason = db.Column(db.Text, nullable=True)  # Reason for excused absence
    marked_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    # Relationships
    student = db.relationship("Student", backref="attendance_records")
    classroom = db.relationship("Class", backref="attendance_records")
    marker = db.relationship("User", foreign_keys=[marked_by])

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


# Attendance audit class
class AttendanceAudit(db.Model):
    """Track changes to attendance records"""

    id = db.Column(db.Integer, primary_key=True)
    attendance_id = db.Column(
        db.Integer, db.ForeignKey("attendance.id"), nullable=False
    )
    changed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    change_type = db.Column(db.String(10), nullable=False)  # create, update, delete
    old_status = db.Column(db.String(10), nullable=True)
    new_status = db.Column(db.String(10), nullable=True)
    change_reason = db.Column(db.Text, nullable=True)
    changed_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    # Relationships
    attendance = db.relationship("Attendance", backref="audit_trail")
    user = db.relationship("User", foreign_keys=[changed_by])

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


# Teachers Attendance Model
class TeacherAttendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(
        db.String(20), nullable=False
    )  # will have present, absent, excused, late
    check_in_time = db.Column(db.Time, nullable=True)
    check_out_time = db.Column(db.Time, nullable=True)
    late_minutes = db.Column(db.Integer, default=0)
    excuse_reason = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    marked_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    # Relationships
    teacher = db.relationship("Teacher", backref="attendance_records")
    marker_user = db.relationship("User", foreign_keys=[marked_by])

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def is_late(self):
        return self.status == "late" or self.late_minutes > 0

    def __repr__(self) -> str:
        return f"<TeacherAttendance {self.teacher_id} {self.date} {self.status}>"


class TeacherAttendanceAudit(db.Model):

    __tablename__ = "teacher_attendance_audit"

    """Track changes to teacher attendance records"""
    id = db.Column(db.Integer, primary_key=True)
    attendance_id = db.Column(
        db.Integer, db.ForeignKey("teacher_attendance.id"), nullable=False
    )
    changed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    change_type = db.Column(db.String(10), nullable=False)  # create, update, delete
    old_status = db.Column(db.String(20), nullable=True)
    new_status = db.Column(db.String(20), nullable=True)
    old_check_in = db.Column(db.Time, nullable=False)
    new_check_in = db.Column(db.Time, nullable=False)
    change_reason = db.Column(db.Text, nullable=True)
    changed_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    # Relationships
    attendance = db.relationship("TeacherAttendance", backref="audit_trail")
    user = db.relationship("User", foreign_keys=[changed_by])

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class AttendanceSettings(db.Model):
    """Store attendance settings [working hours, late thresholds, etc.]"""

    id = db.Column(db.Integer, primary_key=True)
    school_start_time = db.Column(db.Time, default=time(8, 0))  # 8:00 AM
    school_end_time = db.Column(db.Time, default=time(14, 0))  # 2:00 PM
    late_threshold_minutes = db.Column(db.Integer, default=15)  # 15 minutes late
    half_day_threshold_hours = db.Column(db.Integer, default=4)  # 4 hours for half day
    auto_mark_absent = db.Column(db.Boolean, default=True)
    updated_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


# School Calendar Model
class SchoolCalendar(db.Model):
    """Storing school days, holidays, and events"""

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    day_type = db.Column(
        db.String(20), nullable=False
    )  # For school day, holiday, weekend, event
    description = db.Column(db.Text, nullable=True)
    term = db.Column(db.String(20), nullable=True)
    year = db.Column(db.String(10), nullable=True)

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def is_school_day(cls, date):
        day = cls.query.filter_by(date=date).first()
        return day and day.day_type == "school_day"


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
