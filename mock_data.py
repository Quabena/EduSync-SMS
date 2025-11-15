# mock_data.py
import random
from datetime import datetime, timedelta, date
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
    TeacherSubjectClass,
    TermScore,
    SchoolInfo,
    TermDates,
    StudentRemarks,
    GraduationStatus,
    Alumni,
)

fake = Faker()

# Constants for controlled data generation
NUM_CLASSES = 6
NUM_SUBJECTS = 10
NUM_TEACHERS = 15
NUM_STUDENTS = 50
NUM_USERS = 8
NUM_ASSIGNMENTS = 30
DAYS_OF_ATTENDANCE = 90  # ~3 months
ATTENDANCE_PROBABILITY = 0.85  # 85% chance of attendance


def create_school_info():
    """Create default school information"""
    school_info = SchoolInfo(
        name="Namong SDA JHS",
        motto="Knowledge, Excellence, Integrity",
        address="P.O. Box AB 123, Kumasi\nAshanti Region",
        phone="0234567890",
        email="info@nsdajhs.edu.gh",
        website="https://nsdajhs.edu.gh",
        logo_path="school_logo.png",
    )
    db.session.add(school_info)
    db.session.commit()
    print("Created school information")
    return school_info


def create_term_dates():
    """Create term dates for current and previous years (robust to month rollover)."""
    term_dates = []
    current_year = datetime.now().year

    def safe_date_from_year_and_month(y, month, day):
        """
        Convert possibly out-of-range month into a valid date by carrying months into next year(s).
        Example: (2024, 13, 15) -> date(2025, 1, 15)
        """
        year_offset, month_in_year = divmod(month - 1, 12)
        real_year = y + year_offset
        real_month = month_in_year + 1
        return date(real_year, real_month, day)

    for year in range(current_year - 2, current_year + 1):
        for term_num, term_name in enumerate(["Term 1", "Term 2", "Term 3"], 1):
            start_month = (term_num - 1) * 4 + 1
            end_month = start_month + 3
            vacation_month = end_month + 1
            reopening_month = vacation_month + 2

            start_date = safe_date_from_year_and_month(year, start_month, 1)
            end_date = safe_date_from_year_and_month(year, end_month, 28)
            vacation_date = safe_date_from_year_and_month(year, vacation_month, 15)
            reopening_date = safe_date_from_year_and_month(year, reopening_month, 8)

            term_date = TermDates(
                academic_year=f"{year}/{year+1}",
                term=term_name,
                start_date=start_date,
                end_date=end_date,
                vacation_date=vacation_date,
                reopening_date=reopening_date,
            )
            term_dates.append(term_date)
            db.session.add(term_date)

    db.session.commit()
    print(f"Created {len(term_dates)} term date records")
    return term_dates


def create_classes():
    classes = []
    levels = ["JHS 1", "JHS 2", "JHS 3"]
    sections = ["A", "B"]
    master_classes = ["JHS 1", "JHS 2", "JHS 3"]

    for _ in range(NUM_CLASSES):
        level = random.choice(levels)
        section = random.choice(sections)
        master_class = random.choice(master_classes)
        class_ = Class(
            name=f"{level} {section}",
            level=level,
            section=section,
            master_class=master_class,
            is_alumni_class=False,
        )
        classes.append(class_)
        db.session.add(class_)

    current_year = datetime.now().year
    for year in range(current_year - 3, current_year):
        alumni_class = Class(
            name=f"Alumni - Class of {year}",
            level="Alumni",
            section="A",
            master_class="Alumni",
            is_alumni_class=True,
        )
        classes.append(alumni_class)
        db.session.add(alumni_class)

    try:
        db.session.commit()
        print(f"Created {len(classes)} classes (including alumni classes)")
        return classes
    except IntegrityError:
        db.session.rollback()
        return create_classes()


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
    """
    Create teachers. Ensure teacher is added to session *before* mutating relationships
    to avoid SAWarning where relationship changes happen on objects not in session.
    """
    teachers = []
    specializations = random.choices(subjects, k=NUM_TEACHERS)

    for i in range(NUM_TEACHERS):
        gender = random.choice(["Male", "Female"])
        first_name = (
            fake.first_name_male() if gender == "Male" else fake.first_name_female()
        )

        # Build teacher without setting relationship attributes that reference other persistent objects
        teacher = Teacher(
            first_name=first_name,
            middle_name=fake.first_name(),
            surname=fake.last_name(),
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
            certificate_paths="certificates/"
            + ",".join(
                [
                    f"{fake.file_name(extension='pdf')}"
                    for _ in range(random.randint(1, 3))
                ]
            ),
        )

        # Add to session first
        db.session.add(teacher)
        # Flush not strictly necessary here, but safe if we ever need id immediately:
        # db.session.flush()

        # Now it's safe to set relationships referencing persistent Subject/Class objects
        # assign specialization safely
        teacher.specialization = specializations[i]

        # Assign to 1-3 random classes (only non-alumni classes)
        active_classes = [c for c in classes if not c.is_alumni_class]
        k = min(3, len(active_classes))
        if k >= 1:
            selected_classes = random.sample(active_classes, k=random.randint(1, k))
            teacher.classes.extend(selected_classes)

        teachers.append(teacher)

    db.session.commit()
    print(f"Created {len(teachers)} teachers")
    return teachers


def create_teacher_subject_assignments(teachers, classes, subjects):
    """Create TeacherSubjectClass assignments"""
    assignments = []

    for teacher in teachers:
        active_classes = [c for c in classes if not c.is_alumni_class]
        if not active_classes or not subjects:
            continue

        num_assignments = random.randint(2, min(4, len(subjects), len(active_classes)))

        for _ in range(num_assignments):
            subject = random.choice(subjects)
            class_ = random.choice(active_classes)

            existing = TeacherSubjectClass.query.filter_by(
                teacher_id=teacher.id, subject_id=subject.id, class_id=class_.id
            ).first()

            if not existing:
                assignment = TeacherSubjectClass(
                    teacher_id=teacher.id,
                    subject_id=subject.id,
                    class_id=class_.id,
                    is_active=True,
                )
                assignments.append(assignment)
                db.session.add(assignment)

    db.session.commit()
    print(f"Created {len(assignments)} teacher-subject-class assignments")
    return assignments


def create_students(classes, subjects):
    """
    Create students. Add student to session before mutating relationships
    (student.subjects) to avoid SAWarning and missing association rows.
    """
    students = []
    learning_styles = ["Visual", "Auditory", "Kinesthetic", "Reading/Writing"]
    religions = ["Christian", "Muslim", "Traditionalist", "None"]
    photo_paths = [None]

    active_classes = [c for c in classes if not c.is_alumni_class]
    if not active_classes:
        print("No active classes available for student creation")
        return []

    for i in range(NUM_STUDENTS):
        gender = random.choice(["Male", "Female"])
        first_name = (
            fake.first_name_male() if gender == "Male" else fake.first_name_female()
        )

        student_class = random.choice(active_classes)

        student = Student(
            first_name=first_name,
            middle_name=fake.first_name(),
            surname=fake.last_name(),
            gender=gender,
            date_of_birth=fake.date_of_birth(minimum_age=10, maximum_age=18),
            admission_date=date(
                random.randint(2017, 2022), random.randint(1, 12), random.randint(1, 28)
            ),
            hometown=fake.city(),
            father_name=fake.name_male(),
            mother_name=fake.name_female(),
            guardian_name=fake.name(),
            guardian_contact=fake.numerify("05########"),
            medical_records=fake.text(max_nb_chars=200),
            class_id=student_class.id,
            original_class_id=student_class.id,
            status="active",
            religion=random.choice(religions),
            height=random.randint(140, 190),
            weight=random.randint(40, 90),
            photo_path=random.choice(photo_paths),
            learning_style=random.choice(learning_styles),
        )

        # Add student to session before setting relationships
        db.session.add(student)
        # If we need id immediately: db.session.flush()

        # Enroll in 5-8 subjects defensively
        max_k = min(8, len(subjects))
        if max_k >= 5:
            k = random.randint(5, max_k)
        else:
            k = max_k
        if k > 0:
            selected_subjects = random.sample(subjects, k=k)
            student.subjects.extend(selected_subjects)

        students.append(student)

    db.session.commit()
    print(f"Created {len(students)} active students")
    return students


def create_graduated_students(classes, subjects):
    """Create some graduated students for testing the alumni system"""
    graduated_students = []
    learning_styles = ["Visual", "Auditory", "Kinesthetic", "Reading/Writing"]
    religions = ["Christian", "Muslim", "Traditionalist", "None"]

    alumni_classes = [c for c in classes if c.is_alumni_class]
    if not alumni_classes:
        print("No alumni classes found for graduated students")
        return []

    for i in range(10):
        gender = random.choice(["Male", "Female"])
        first_name = (
            fake.first_name_male() if gender == "Male" else fake.first_name_female()
        )

        alumni_class = random.choice(alumni_classes)
        graduation_year = alumni_class.name.split(" ")[-1]

        original_classes = [c for c in classes if not c.is_alumni_class]
        if not original_classes:
            print(
                "No original (active) classes available — skipping graduated student creation"
            )
            break
        original_class = random.choice(original_classes)

        student = Student(
            first_name=first_name,
            middle_name=fake.first_name(),
            surname=fake.last_name(),
            gender=gender,
            date_of_birth=fake.date_of_birth(minimum_age=18, maximum_age=25),
            admission_date=date(
                int(graduation_year) - 3, random.randint(1, 12), random.randint(1, 28)
            ),
            hometown=fake.city(),
            father_name=fake.name_male(),
            mother_name=fake.name_female(),
            guardian_name=fake.name(),
            guardian_contact=fake.numerify("05########"),
            medical_records=fake.text(max_nb_chars=200),
            class_id=alumni_class.id,
            original_class_id=original_class.id,
            status="graduated",
            religion=random.choice(religions),
            height=random.randint(160, 190),
            weight=random.randint(50, 90),
            learning_style=random.choice(learning_styles),
        )

        # Add and flush so student.id exists for GraduationStatus/Alumni
        db.session.add(student)
        try:
            db.session.flush()
        except Exception as exc:
            db.session.rollback()
            print(
                f"Error flushing student to DB for {first_name} {student.surname}: {exc}"
            )
            raise

        # Enroll in subjects defensively
        max_k = min(8, len(subjects))
        if max_k >= 5:
            k = random.randint(5, max_k)
        else:
            k = max_k
        if k > 0:
            selected_subjects = random.sample(subjects, k=k)
            student.subjects.extend(selected_subjects)

        graduated_students.append(student)

        # GraduationStatus
        graduation_status = GraduationStatus(
            student_id=student.id,
            graduation_year=graduation_year,
            graduation_date=date(int(graduation_year), 7, 15),
            status="completed",
            final_grade=random.choice(["A", "B", "C"]),
            remarks=fake.sentence(),
        )
        db.session.add(graduation_status)

        # Alumni record (original_student_id is now present)
        alumni = Alumni(
            original_student_id=student.id,
            first_name=student.first_name,
            middle_name=student.middle_name,
            surname=student.surname,
            gender=student.gender,
            date_of_birth=student.date_of_birth,
            admission_date=student.admission_date,
            graduation_year=graduation_year,
            graduation_date=date(int(graduation_year), 7, 15),
            hometown=student.hometown,
            father_name=student.father_name,
            mother_name=student.mother_name,
            guardian_name=student.guardian_name,
            guardian_contact=student.guardian_contact,
            religion=student.religion,
            medical_records=student.medical_records,
            photo_path=student.photo_path,
            final_class=original_class.name,
        )
        db.session.add(alumni)

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        print(f"Error committing graduated students batch: {exc}")
        raise

    print(f"Created {len(graduated_students)} graduated students with alumni records")
    return graduated_students


def create_term_scores(students, subjects, teachers):
    term_scores = []
    terms = ["Term 1", "Term 2", "Term 3"]
    years = ["2024", "2025"]

    for student in students:
        if student.status != "active":
            continue

        for subject in student.subjects:
            for term in terms:
                for year in years:
                    if random.random() > 0.7:
                        continue

                    assignment = TeacherSubjectClass.query.filter_by(
                        subject_id=subject.id, class_id=student.class_id, is_active=True
                    ).first()

                    if not assignment:
                        continue

                    individual_test = round(random.uniform(0, 15), 1)
                    group_work = round(random.uniform(0, 15), 1)
                    class_test = round(random.uniform(0, 15), 1)
                    project = round(random.uniform(0, 15), 1)
                    exam_score = round(random.uniform(0, 100), 1)

                    term_score = TermScore(
                        student_id=student.id,
                        subject_id=subject.id,
                        class_id=student.class_id,
                        teacher_id=assignment.teacher_id,
                        term=term,
                        year=year,
                        individual_test=individual_test,
                        group_work=group_work,
                        class_test=class_test,
                        project=project,
                        exam_score=exam_score,
                    )

                    term_score.calculate_totals()
                    term_scores.append(term_score)
                    db.session.add(term_score)

    db.session.commit()
    print(f"Created {len(term_scores)} term scores")
    return term_scores


def create_student_remarks(students, teachers):
    remarks_list = []
    terms = ["Term 1", "Term 2", "Term 3"]
    current_year = str(datetime.now().year)

    for student in students:
        if student.status != "active":
            continue

        for term in terms:
            if random.random() > 0.6:
                continue

            class_teachers = [
                t for t in teachers if student.class_id in [c.id for c in t.classes]
            ]
            teacher = (
                random.choice(class_teachers)
                if class_teachers
                else random.choice(teachers)
            )

            remark = StudentRemarks(
                student_id=student.id,
                teacher_id=teacher.id,
                term=term,
                year=current_year,
                conduct=fake.paragraph(nb_sentences=2),
                attitude=fake.paragraph(nb_sentences=2),
                interests=fake.paragraph(nb_sentences=1),
                remarks=fake.paragraph(nb_sentences=3),
            )
            remarks_list.append(remark)
            db.session.add(remark)

    db.session.commit()
    print(f"Created {len(remarks_list)} student remarks")
    return remarks_list


def create_users(teachers):
    users = []
    admin = User(username="admin", email="admin@school.edu.gh", role="admin")
    admin.set_password("admin123")
    users.append(admin)
    db.session.add(admin)

    headteacher = User(
        username="headteacher", email="head@school.edu.gh", role="headteacher"
    )
    headteacher.set_password("head123")
    users.append(headteacher)
    db.session.add(headteacher)

    for i, teacher in enumerate(teachers[: NUM_USERS - 2]):
        user = User(username=f"teacher{i+1}", email=teacher.email, role="teacher")
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
                if random.random() > 0.7:
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
        return "1"
    if score >= 70:
        return "2"
    if score >= 60:
        return "3"
    if score >= 50:
        return "4"
    if score >= 40:
        return "5"
    return "9"


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
    terms = ["Term 1", "Term 2", "Term 3"]
    current_year = str(datetime.now().year)

    for single_date in (start_date + timedelta(n) for n in range(DAYS_OF_ATTENDANCE)):
        if single_date.weekday() >= 5:
            continue

        if single_date.month <= 4:
            term = "Term 1"
        elif single_date.month <= 8:
            term = "Term 2"
        else:
            term = "Term 3"

        for student in students:
            if student.status != "active":
                continue

            if random.random() > ATTENDANCE_PROBABILITY:
                continue

            status = random.choices(
                ["present", "absent", "late"], weights=[0.85, 0.1, 0.05]
            )[0]

            record = Attendance(
                student_id=student.id,
                class_id=student.class_id,
                date=single_date,
                term=term,
                year=current_year,
                status=status,
                method=random.choice(["manual", "QR"]),
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
        if student.status != "active":
            continue

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
        sample_subjects = subjects[:]
        if len(sample_subjects) < 5:
            chosen = sample_subjects
        else:
            chosen = random.sample(
                sample_subjects, k=random.randint(5, min(8, len(sample_subjects)))
            )
        for subject in chosen:
            for term in terms:
                if random.random() > 0.6:
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

    active_students = [s for s in students if s.status == "active"]

    for student in random.sample(active_students, k=min(200, len(active_students))):
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
    active_classes = [c for c in classes if not c.is_alumni_class]

    for class_ in active_classes:
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
    active_classes = [c for c in classes if not c.is_alumni_class]
    if not active_classes:
        return entries

    for _ in range(100):
        mood_entry = MoodEntry(
            class_id=random.choice(active_classes).id,
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
    active_classes = [c for c in classes if not c.is_alumni_class]
    if not active_classes or not teachers or not subjects:
        return assignments

    for _ in range(NUM_ASSIGNMENTS):
        assignment = Assignment(
            title=fake.catch_phrase(),
            description=fake.text(max_nb_chars=200),
            subject_id=random.choice(subjects).id,
            class_id=random.choice(active_classes).id,
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
    active_students = [s for s in students if s.status == "active"]
    if not active_students:
        return submissions

    for assignment in assignments:
        candidates = random.sample(active_students, k=min(30, len(active_students)))
        for student in candidates:
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

    db.drop_all()
    db.create_all()

    create_school_info()
    create_term_dates()
    classes = create_classes()
    subjects = create_subjects()
    teachers = create_teachers(classes, subjects)
    teacher_assignments = create_teacher_subject_assignments(
        teachers, classes, subjects
    )
    students = create_students(classes, subjects)
    graduated_students = create_graduated_students(classes, subjects)
    all_students = students + graduated_students
    term_scores = create_term_scores(all_students, subjects, teachers)
    student_remarks = create_student_remarks(all_students, teachers)
    users = create_users(teachers)

    create_academic_records(all_students, subjects)
    create_medical_records(all_students)
    create_attendances(all_students, classes)
    enrollments = create_enrollments(all_students, classes)
    create_grades(enrollments, subjects)
    create_hallpasses(all_students, users)
    create_classrooms(classes)
    create_mood_entries(classes, users)

    assignments = create_assignments(teachers, classes, subjects)
    create_student_assignments(assignments, all_students)

    print("Mock data generation completed successfully!")
    print(f"Summary:")
    print(f"- {len(students)} active students")
    print(f"- {len(graduated_students)} graduated students")
    print(f"- {len([c for c in classes if not c.is_alumni_class])} active classes")
    print(f"- {len([c for c in classes if c.is_alumni_class])} alumni classes")


if __name__ == "__main__":
    from app import create_app

    app = create_app()
    with app.app_context():
        generate_mock_data()
