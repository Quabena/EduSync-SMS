# mock_data.py
import random
from datetime import datetime, timedelta
from faker import Faker
from sqlalchemy.exc import IntegrityError
from app.models import (
    db,
    Class,
    Subject,
    Student,
    Teacher,
    AcademicRecord,
    MedicalRecord,
    Attendance,
    Enrollment,
    Grade,
    HallPass,
    Classroom,
    MoodEntry,
    User,
    Assignment,
    StudentAssignment,
)

fake = Faker()

# Constants for controlled data generation
NUM_CLASSES = 5
NUM_SUBJECTS = 10
NUM_TEACHERS = 15
NUM_STUDENTS = 50
NUM_USERS = 8
NUM_ASSIGNMENTS = 30
DAYS_OF_ATTENDANCE = 90  # ~3 months
ATTENDANCE_PROBABILITY = 0.85  # 85% chance of attendance


def create_classes():
    classes = []
    levels = ["JHS 1", "JHS 2", "JHS 3"]
    sections = ["A", "B", "C", "D"]

    for _ in range(NUM_CLASSES):
        level = random.choice(levels)
        section = random.choice(sections)
        class_ = Class(name=f"{level} {section}", level=level, section=section)
        classes.append(class_)
        db.session.add(class_)

    try:
        db.session.commit()
        print(f"Created {len(classes)} classes")
        return classes
    except IntegrityError:
        db.session.rollback()
        return create_classes()  # Retry if duplicate name


def create_subjects():
    subjects = []
    subject_names = [
        "Mathematics",
        "English Language",
        "Integrated Science",
        "Social Studies",
        "Computing",
        "Religious and Moral Education",
        "French",
        "Ghanaian Language",
        "Career Technology",
        "Creative Arts",
    ]

    for i, name in enumerate(subject_names[:NUM_SUBJECTS]):
        code = f"SUB{i+1:03d}"
        subject = Subject(name=name, code=code)
        subjects.append(subject)
        db.session.add(subject)

    db.session.commit()
    print(f"Created {len(subjects)} subjects")
    return subjects


def create_teachers(classes, subjects):
    teachers = []
    specializations = random.choices(subjects, k=NUM_TEACHERS)

    for i in range(NUM_TEACHERS):
        gender = random.choice(["Male", "Female"])
        first_name = (
            fake.first_name_male() if gender == "Male" else fake.first_name_female()
        )

        teacher = Teacher(
            first_name=first_name,
            middle_name=fake.first_name(),
            surnname=fake.last_name(),
            gender=gender,
            date_of_birth=fake.date_of_birth(minimum_age=25, maximum_age=60),
            hometown=fake.city(),
            college_attended=fake.company(),
            area_of_specialization=fake.job(),
            academic_certificate=random.choice(["B.Ed", "M.Ed", "PhD"]),
            academic_area_of_study=random.choice(
                ["Education", "Mathematics", "Science"]
            ),
            academic_college=fake.company(),
            professional_certificate=random.choice(
                ["Teacher Cert A", "Diploma", "PGCE"]
            ),
            professional_area_of_study=random.choice(
                ["Teaching", "Education Management"]
            ),
            professional_college=fake.company(),
            staff_id=f"STAFF{i:04d}",
            registered_number=f"TCH-{fake.unique.random_number(digits=6)}",
            ntc_number=f"NTC-{fake.unique.random_number(digits=8)}",
            ssnit_number=f"SSN-{fake.unique.random_number(digits=9)}",
            phone_number=fake.unique.numerify("05########"),
            email=fake.unique.email(),
            emergency_contact_name=fake.name(),
            emergency_contact_number=fake.numerify("05########"),
            specialization=specializations[i],
        )

        # Assign to 1-3 random classes
        selected_classes = random.sample(
            classes, k=random.randint(1, min(3, len(classes)))
        )
        teacher.classes.extend(selected_classes)
        teachers.append(teacher)
        db.session.add(teacher)

    db.session.commit()
    print(f"Created {len(teachers)} teachers")
    return teachers


def create_students(classes, subjects):
    students = []
    learning_styles = ["Visual", "Auditory", "Kinesthetic", "Reading/Writing"]

    for i in range(NUM_STUDENTS):
        gender = random.choice(["Male", "Female"])
        first_name = (
            fake.first_name_male() if gender == "Male" else fake.first_name_female()
        )

        student = Student(
            first_name=first_name,
            middle_name=fake.first_name(),
            surname=fake.last_name(),
            gender=gender,
            date_of_birth=fake.date_of_birth(minimum_age=10, maximum_age=18),
            hometown=fake.city(),
            father_name=fake.name_male(),
            mother_name=fake.name_female(),
            guardian_name=fake.name(),
            guardian_contact=fake.numerify("05########"),
            medical_records=fake.text(max_nb_chars=200),
            class_id=random.choice(classes).id,
            learning_style=random.choice(learning_styles),
        )

        # Enroll in 5-8 subjects
        selected_subjects = random.sample(
            subjects, k=random.randint(5, min(8, len(subjects)))
        )
        student.subjects.extend(selected_subjects)
        students.append(student)
        db.session.add(student)

    db.session.commit()
    print(f"Created {len(students)} students")
    return students


def create_users(teachers):
    users = []
    roles = ["admin", "headteacher", "teacher"]

    # Create admin user
    admin = User(username="admin", email="admin@school.edu.gh", role="admin")
    admin.set_password("admin123")
    users.append(admin)
    db.session.add(admin)

    # Create headteacher
    headteacher = User(
        username="headteacher", email="head@school.edu.gh", role="headteacher"
    )
    headteacher.set_password("head123")
    users.append(headteacher)
    db.session.add(headteacher)

    # Create teacher users
    for i, teacher in enumerate(
        random.sample(teachers, k=min(NUM_USERS - 2, len(teachers)))
    ):
        user = User(
            username=f"teacher{i+1}",
            email=f"teacher{i+1}@school.edu.gh",
            role="teacher",
        )
        user.set_password(f"teacher{i+1}")
        users.append(user)
        db.session.add(user)

    db.session.commit()
    print(f"Created {len(users)} users")
    return users


def create_academic_records(students, subjects):
    records = []
    terms = ["1st Term", "2nd Term", "3rd Term"]
    current_year = datetime.now().year

    for student in students:
        for subject in student.subjects:
            for term in terms:
                # Only create records for some terms
                if random.random() > 0.7:  # 30% chance to skip
                    continue

                score = round(random.uniform(25, 100), 1)
                record = AcademicRecord(
                    student_id=student.id,
                    subject_id=subject.id,
                    term=term,
                    year=str(current_year - random.randint(0, 2)),
                    score=score,
                    grade=get_grade(score),
                    remarks=fake.sentence(),
                )
                records.append(record)
                db.session.add(record)

    db.session.commit()
    print(f"Created {len(records)} academic records")
    return records


def get_grade(score):
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    if score >= 50:
        return "D"
    return "F"


def create_medical_records(students):
    records = []
    conditions = [
        "Asthma",
        "Allergies",
        "Diabetes",
        "Epilepsy",
        "ADHD",
        "Dyslexia",
        "Visual Impairment",
        "Hearing Impairment",
    ]

    for student in students:
        # 30% of students have medical records
        if random.random() < 0.3:
            record = MedicalRecord(
                student_id=student.id,
                condition=random.choice(conditions),
                diagnosis_date=fake.date_between(start_date="-5y", end_date="today"),
                treatment=fake.text(max_nb_chars=100),
                notes=fake.text(max_nb_chars=150),
            )
            records.append(record)
            db.session.add(record)

    db.session.commit()
    print(f"Created {len(records)} medical records")
    return records


def create_attendances(students, classes):
    records = []
    start_date = datetime.now() - timedelta(days=DAYS_OF_ATTENDANCE)

    for single_date in (start_date + timedelta(n) for n in range(DAYS_OF_ATTENDANCE)):
        # Skip weekends
        if single_date.weekday() >= 5:  # 5=Sat, 6=Sun
            continue

        for student in students:
            # Skip some attendance records based on probability
            if random.random() > ATTENDANCE_PROBABILITY:
                continue

            status = random.choices(
                ["Present", "Absent", "Late"], weights=[0.85, 0.1, 0.05]
            )[0]

            record = Attendance(
                student_id=student.id,
                class_id=student.class_id,
                date=single_date,
                status=status,
                method=random.choice(["Manual", "QR"]),
            )
            records.append(record)
            db.session.add(record)

    db.session.commit()
    print(f"Created {len(records)} attendance records")
    return records


def create_enrollments(students, classes):
    enrollments = []
    current_year = datetime.now().year

    for student in students:
        enrollment = Enrollment(
            student_id=student.id,
            class_id=student.class_id,
            session_year=f"{current_year}/{current_year+1}",
        )
        enrollments.append(enrollment)
        db.session.add(enrollment)

    db.session.commit()
    print(f"Created {len(enrollments)} enrollments")
    return enrollments


def create_grades(enrollments, subjects):
    grades = []
    terms = ["1st Term", "2nd Term", "3rd Term"]

    for enrollment in enrollments:
        for subject in random.sample(subjects, k=random.randint(5, 8)):
            for term in terms:
                if random.random() > 0.6:  # 40% chance to create grade
                    score = round(random.uniform(25, 100), 1)
                    grade = Grade(
                        enrollment_id=enrollment.id,
                        subject_id=subject.id,
                        term=term,
                        score=score,
                        remarks=get_grade_remarks(score),
                    )
                    grades.append(grade)
                    db.session.add(grade)

    db.session.commit()
    print(f"Created {len(grades)} grades")
    return grades


def get_grade_remarks(score):
    if score >= 80:
        return "Excellent"
    if score >= 70:
        return "Very Good"
    if score >= 60:
        return "Good"
    if score >= 50:
        return "Satisfactory"
    return "Needs Improvement"


def create_hallpasses(students, users):
    hallpasses = []
    destinations = ["Library", "Restroom", "Office", "Clinic", "Guidance Counselor"]

    for student in random.sample(students, k=min(200, len(students))):
        # Create hallpass within last 30 days
        issued_at = fake.date_time_between(start_date="-30d", end_date="now")

        hallpass = HallPass(
            student_id=student.id,
            destination=random.choice(destinations),
            qr_path=f"/qr_codes/{fake.uuid4()}.png",
            issued_at=issued_at,
            status=random.choices(
                ["active", "used", "expired"], weights=[0.2, 0.7, 0.1]
            )[0],
        )

        # If used, set scanned details
        if hallpass.status == "used":
            hallpass.scanned_at = issued_at + timedelta(minutes=random.randint(1, 30))
            hallpass.scanned_by = random.choice(users).id

        hallpasses.append(hallpass)
        db.session.add(hallpass)

    db.session.commit()
    print(f"Created {len(hallpasses)} hall passes")
    return hallpasses


def create_classrooms(classes):
    classrooms = []
    for class_ in classes:
        classroom = Classroom(
            mood_data={"happy": random.randint(0, 10), "sad": random.randint(0, 5)},
            qr_code=f"CLASSQR-{class_.id}",
        )
        classrooms.append(classroom)
        db.session.add(classroom)

    db.session.commit()
    print(f"Created {len(classrooms)} classrooms")
    return classrooms


def create_mood_entries(classes, users):
    entries = []
    sentiments = ["positive", "negative", "neutral"]

    for _ in range(100):  # Create 100 mood entries
        mood_entry = MoodEntry(
            class_id=random.choice(classes).id,
            notes=fake.sentence(),
            sentiment=random.choice(sentiments),
            polarity=round(random.uniform(-1, 1), 2),
            recorded_by=random.choice(users).id,
        )
        entries.append(mood_entry)
        db.session.add(mood_entry)

    db.session.commit()
    print(f"Created {len(entries)} mood entries")
    return entries


def create_assignments(teachers, classes, subjects):
    assignments = []

    for _ in range(NUM_ASSIGNMENTS):
        assignment = Assignment(
            title=fake.catch_phrase(),
            description=fake.text(max_nb_chars=200),
            subject_id=random.choice(subjects).id,
            class_id=random.choice(classes).id,
            teacher_id=random.choice(teachers).id,
            due_date=fake.future_datetime(end_date="+30d"),
            total_marks=random.choice([20, 30, 40, 50, 100]),
            document_path=f"/assignments/{fake.file_name(extension='pdf')}",
        )
        assignments.append(assignment)
        db.session.add(assignment)

    db.session.commit()
    print(f"Created {len(assignments)} assignments")
    return assignments


def create_student_assignments(assignments, students):
    submissions = []
    statuses = ["not_submitted", "submitted", "graded"]

    for assignment in assignments:
        for student in random.sample(students, k=min(30, len(students))):
            # Only create if student is in the assignment's class
            if student.class_id != assignment.class_id:
                continue

            status = random.choice(statuses)
            submission = StudentAssignment(
                student_id=student.id, assignment_id=assignment.id, status=status
            )

            if status != "not_submitted":
                submission.submitted_at = fake.date_time_between(
                    start_date=assignment.created_at, end_date=assignment.due_date
                )
                submission.submission_path = (
                    f"/submissions/{fake.file_name(extension='pdf')}"
                )

                if status == "graded":
                    submission.marks_obtained = round(
                        random.uniform(0, assignment.total_marks), 1
                    )
                    submission.feedback = fake.text(max_nb_chars=100)

            submissions.append(submission)
            db.session.add(submission)

    db.session.commit()
    print(f"Created {len(submissions)} student assignments")
    return submissions


def generate_mock_data():
    print("Starting mock data generation...")

    # Clear existing data (use with caution!)
    db.drop_all()
    db.create_all()

    # Create data in proper dependency order
    classes = create_classes()
    subjects = create_subjects()
    teachers = create_teachers(classes, subjects)
    students = create_students(classes, subjects)
    users = create_users(teachers)

    # Create related records
    create_academic_records(students, subjects)
    create_medical_records(students)
    create_attendances(students, classes)
    enrollments = create_enrollments(students, classes)
    create_grades(enrollments, subjects)
    create_hallpasses(students, users)
    create_classrooms(classes)
    create_mood_entries(classes, users)

    # Assignment-related data
    assignments = create_assignments(teachers, classes, subjects)
    create_student_assignments(assignments, students)

    print("Mock data generation completed successfully!")


if __name__ == "__main__":
    from app import create_app

    app = create_app()
    with app.app_context():
        generate_mock_data()
