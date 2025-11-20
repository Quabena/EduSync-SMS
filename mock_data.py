# mock_data.py
import random
from datetime import datetime, timedelta, date, time
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
    PromotionPath,
    PromotionRecord,
    TeacherAttendance,
    AttendanceSettings,
    SchoolCalendar,
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
    """Create term dates for current and previous years"""
    term_dates = []
    current_year = datetime.now().year

    for year in range(current_year - 2, current_year + 1):
        # Term 1: January - April
        term1 = TermDates(
            academic_year=f"{year}/{year+1}",
            term="Term 1",
            start_date=date(year, 1, 10),
            end_date=date(year, 4, 5),
            vacation_date=date(year, 4, 6),
            reopening_date=date(year, 5, 6),
        )

        # Term 2: May - August
        term2 = TermDates(
            academic_year=f"{year}/{year+1}",
            term="Term 2",
            start_date=date(year, 5, 7),
            end_date=date(year, 8, 2),
            vacation_date=date(year, 8, 3),
            reopening_date=date(year, 9, 3),
        )

        # Term 3: September - December
        term3 = TermDates(
            academic_year=f"{year}/{year+1}",
            term="Term 3",
            start_date=date(year, 9, 4),
            end_date=date(year, 12, 15),
            vacation_date=date(year, 12, 16),
            reopening_date=date(year + 1, 1, 8),
        )

        term_dates.extend([term1, term2, term3])
        db.session.add_all([term1, term2, term3])

    db.session.commit()
    print(f"Created {len(term_dates)} term date records")
    return term_dates


def create_classes():
    classes = []
    levels = ["JHS 1", "JHS 2", "JHS 3"]
    sections = ["A", "B"]

    for level in levels:
        for section in sections:
            class_ = Class(
                name=f"{level} {section}",
                level=level,
                section=section,
                master_class=level,
                is_alumni_class=False,
            )
            classes.append(class_)
            db.session.add(class_)

    # Create alumni classes
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
        return Class.query.all()


def create_subjects():
    subjects = []
    subject_data = [
        ("Mathematics", "MATH", True),
        ("English Language", "ENG", True),
        ("Integrated Science", "SCI", True),
        ("Social Studies", "SOC", True),
        ("Computing", "COMP", False),
        ("Religious and Moral Education", "RME", False),
        ("French", "FREN", False),
        ("Ghanaian Language", "LANG", False),
        ("Career Technology", "TECH", False),
        ("Creative Arts", "ARTS", False),
    ]

    for name, code, is_core in subject_data:
        subject = Subject(name=name, code=code, is_core=is_core)
        subjects.append(subject)
        db.session.add(subject)

    db.session.commit()
    print(f"Created {len(subjects)} subjects")
    return subjects


def create_teachers(classes, subjects):
    teachers = []
    ranks = ["Assistant Director", "Director", "Principal", "Head"]
    staff_roles = ["Teacher", "Head of Department", "Assistant Head", "Coordinator"]
    marital_statuses = ["Single", "Married", "Divorced", "Widowed"]

    for i in range(NUM_TEACHERS):
        gender = random.choice(["Male", "Female"])
        first_name = (
            fake.first_name_male() if gender == "Male" else fake.first_name_female()
        )

        teacher = Teacher(
            first_name=first_name,
            middle_name=fake.first_name(),
            surname=fake.last_name(),
            gender=gender,
            date_of_birth=fake.date_of_birth(minimum_age=25, maximum_age=60),
            date_posted_to_present_station=fake.date_between(
                start_date="-10y", end_date="today"
            ),
            first_appointment_date=fake.date_between(start_date="-20y", end_date="-5y"),
            last_promotion_date=fake.date_between(start_date="-5y", end_date="today"),
            hometown=fake.city(),
            live_at=fake.city(),
            digital_address=fake.bothify("??-####-####"),
            college_attended=fake.company() + " University",
            area_of_specialization=random.choice(
                ["Mathematics", "Science", "Languages", "Arts"]
            ),
            academic_certificate=random.choice(["B.Ed", "M.Ed", "PhD", "Diploma"]),
            academic_area_of_study=random.choice(
                ["Education", "Mathematics", "Science", "English"]
            ),
            academic_college=fake.company() + " University",
            professional_certificate=random.choice(
                ["Teacher Cert A", "Diploma", "PGCE"]
            ),
            professional_area_of_study=random.choice(
                ["Teaching", "Education Management"]
            ),
            professional_college=fake.company() + " College",
            staff_id=f"STAFF{i+1:04d}",
            registered_number=f"TCH{fake.unique.random_number(digits=6)}",
            ntc_number=f"NTC{fake.unique.random_number(digits=8)}",
            ssnit_number=f"SSN{fake.unique.random_number(digits=9)}",
            phone_number=fake.unique.numerify("05########"),
            email=fake.unique.email(),
            current_rank=random.choice(ranks),
            salary_grade=random.choice(["15", "16", "17", "18"]),
            salary_grade_type=random.choice(["SS", "TS"]),
            emergency_contact_name=fake.name(),
            emergency_contact_number=fake.numerify("05########"),
            certificate_paths=",".join(
                [f"cert_{i}.pdf" for i in range(1, random.randint(2, 4))]
            ),
            status=random.choice(["Active", "On Leave", "Retired"]),
            staff_role=random.choice(staff_roles),
            marital_status=random.choice(marital_statuses),
            specialization=random.choice(subjects),
        )

        db.session.add(teacher)
        teachers.append(teacher)

        # Assign to 1-3 random classes (only non-alumni classes)
        active_classes = [c for c in classes if not c.is_alumni_class]
        if active_classes:
            selected_classes = random.sample(
                active_classes, k=min(3, len(active_classes))
            )
            teacher.classes.extend(selected_classes)

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

        # Each teacher gets 2-4 subject-class assignments
        num_assignments = random.randint(2, min(4, len(subjects), len(active_classes)))
        assigned_combinations = set()

        for _ in range(num_assignments):
            subject = random.choice(subjects)
            class_ = random.choice(active_classes)

            # Avoid duplicate assignments
            combo = (teacher.id, subject.id, class_.id)
            if combo in assigned_combinations:
                continue

            assigned_combinations.add(combo)

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
    students = []
    interests = [
        "Sports",
        "Arts",
        "Science",
        "Technology",
        "Music",
        "Reading",
        "Dancing",
    ]
    religions = ["Christian", "Muslim", "Traditionalist", "None"]

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
            admission_date=fake.date_between(start_date="-5y", end_date="today"),
            hometown=fake.city(),
            live_at=fake.city(),
            digital_address=fake.bothify("??-####-####"),
            father_name=fake.name_male(),
            mother_name=fake.name_female(),
            guardian_name=fake.name(),
            guardian_contact=fake.numerify("05########"),
            religion=random.choice(religions),
            medical_records=(
                fake.text(max_nb_chars=200) if random.random() < 0.3 else None
            ),
            height=random.randint(140, 190),
            weight=random.randint(40, 90),
            class_id=student_class.id,
            original_class_id=student_class.id,
            status="active",
            interest=random.choice(interests),
        )

        db.session.add(student)
        students.append(student)

        # Enroll in 5-8 subjects
        if subjects:
            num_subjects = random.randint(5, min(8, len(subjects)))
            selected_subjects = random.sample(subjects, num_subjects)
            student.subjects.extend(selected_subjects)

    db.session.commit()
    print(f"Created {len(students)} active students")
    return students


def create_graduated_students(classes, subjects):
    """Create some graduated students for testing the alumni system"""
    graduated_students = []
    interests = [
        "Sports",
        "Arts",
        "Science",
        "Technology",
        "Music",
        "Reading",
        "Dancing",
    ]
    religions = ["Christian", "Muslim", "Traditionalist", "None"]

    alumni_classes = [c for c in classes if c.is_alumni_class]
    if not alumni_classes:
        print("No alumni classes found for graduated students")
        return []

    for i in range(10):  # Create 10 graduated students
        gender = random.choice(["Male", "Female"])
        first_name = (
            fake.first_name_male() if gender == "Male" else fake.first_name_female()
        )

        alumni_class = random.choice(alumni_classes)
        graduation_year = alumni_class.name.split(" ")[
            -1
        ]  # Extract year from "Alumni - Class of YYYY"

        # Use an active class as original class
        original_classes = [c for c in classes if not c.is_alumni_class]
        if not original_classes:
            continue
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
            live_at=fake.city(),
            digital_address=fake.bothify("??-####-####"),
            father_name=fake.name_male(),
            mother_name=fake.name_female(),
            guardian_name=fake.name(),
            guardian_contact=fake.numerify("05########"),
            religion=random.choice(religions),
            medical_records=(
                fake.text(max_nb_chars=200) if random.random() < 0.3 else None
            ),
            class_id=alumni_class.id,
            original_class_id=original_class.id,
            status="graduated",
            interest=random.choice(interests),
        )

        db.session.add(student)
        db.session.flush()  # Get the student ID

        # Enroll in subjects
        if subjects:
            num_subjects = random.randint(5, min(8, len(subjects)))
            selected_subjects = random.sample(subjects, num_subjects)
            student.subjects.extend(selected_subjects)

        graduated_students.append(student)

        # Create GraduationStatus record
        graduation_status = GraduationStatus(
            student_id=student.id,
            graduation_year=graduation_year,
            graduation_date=date(int(graduation_year), 7, 15),
            status="completed",
            final_grade=random.choice(["A", "B", "C"]),
            remarks=fake.sentence(),
        )
        db.session.add(graduation_status)

        # Create Alumni record
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
            final_class=original_class.name,
        )
        db.session.add(alumni)

    db.session.commit()
    print(f"Created {len(graduated_students)} graduated students with alumni records")
    return graduated_students


def create_promotion_paths(classes):
    """Create promotion paths between classes"""
    paths = []
    active_classes = [c for c in classes if not c.is_alumni_class]

    # Create logical promotion paths: JHS 1 -> JHS 2 -> JHS 3
    jhs1_classes = [c for c in active_classes if c.level == "JHS 1"]
    jhs2_classes = [c for c in active_classes if c.level == "JHS 2"]
    jhs3_classes = [c for c in active_classes if c.level == "JHS 3"]

    for from_class in jhs1_classes:
        for to_class in jhs2_classes:
            path = PromotionPath(
                from_class_id=from_class.id,
                to_class_id=to_class.id,
                order=1,
                is_active=True,
            )
            paths.append(path)
            db.session.add(path)

    for from_class in jhs2_classes:
        for to_class in jhs3_classes:
            path = PromotionPath(
                from_class_id=from_class.id,
                to_class_id=to_class.id,
                order=2,
                is_active=True,
            )
            paths.append(path)
            db.session.add(path)

    # JHS 3 to Alumni
    current_year = datetime.now().year
    alumni_class = Class.query.filter_by(
        name=f"Alumni - Class of {current_year}"
    ).first()
    if alumni_class:
        for from_class in jhs3_classes:
            path = PromotionPath(
                from_class_id=from_class.id,
                to_class_id=alumni_class.id,
                order=3,
                is_active=True,
            )
            paths.append(path)
            db.session.add(path)

    db.session.commit()
    print(f"Created {len(paths)} promotion paths")
    return paths


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
                    if random.random() > 0.7:  # 30% chance to create score
                        continue

                    # Find teacher assignment for this subject and class
                    assignment = TeacherSubjectClass.query.filter_by(
                        subject_id=subject.id, class_id=student.class_id, is_active=True
                    ).first()

                    if not assignment:
                        continue

                    # Generate component scores
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
            if random.random() > 0.6:  # 40% chance to create remarks
                continue

            # Find teachers who teach this student's class
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

    # Create admin user
    admin = User(username="admin", email="admin@school.edu.gh", role="admin")
    admin.set_password("admin123")
    users.append(admin)
    db.session.add(admin)

    # Create headteacher user
    headteacher = User(
        username="headteacher", email="head@school.edu.gh", role="headteacher"
    )
    headteacher.set_password("head123")
    users.append(headteacher)
    db.session.add(headteacher)

    # Create teacher users
    for i, teacher in enumerate(teachers[: NUM_USERS - 2]):
        user = User(username=f"teacher{i+1}", email=teacher.email, role="teacher")
        user.set_password(f"teacher{i+1}")
        users.append(user)
        db.session.add(user)

    db.session.commit()
    print(f"Created {len(users)} users")
    return users


def create_attendance_settings(users):
    """Create default attendance settings"""
    settings = AttendanceSettings(
        school_start_time=time(8, 0),  # 8:00 AM
        school_end_time=time(14, 0),  # 2:00 PM
        late_threshold_minutes=15,
        half_day_threshold_hours=4,
        auto_mark_absent=True,
        updated_by=users[0].id,  # Use first user (admin)
    )
    db.session.add(settings)
    db.session.commit()
    print("Created attendance settings")
    return settings


def create_school_calendar():
    """Create school calendar with school days and holidays"""
    calendar_entries = []
    current_year = datetime.now().year
    start_date = date(current_year, 1, 1)
    end_date = date(current_year, 12, 31)

    # Major holidays in Ghana
    holidays = [
        (date(current_year, 1, 1), "New Year's Day"),
        (date(current_year, 3, 6), "Independence Day"),
        (date(current_year, 4, 10), "Easter Friday"),
        (date(current_year, 5, 1), "Labour Day"),
        (date(current_year, 12, 25), "Christmas Day"),
        (date(current_year, 12, 26), "Boxing Day"),
    ]

    single_date = start_date
    while single_date <= end_date:
        # Skip weekends
        if single_date.weekday() >= 5:
            day_type = "weekend"
            description = "Weekend"
        else:
            # Check if it's a holiday
            holiday = next((h for h in holidays if h[0] == single_date), None)
            if holiday:
                day_type = "holiday"
                description = holiday[1]
            else:
                day_type = "school_day"
                description = "Regular school day"

        calendar_entry = SchoolCalendar(
            date=single_date,
            day_type=day_type,
            description=description,
            term=get_term_for_date(single_date),
            year=str(current_year),
        )
        calendar_entries.append(calendar_entry)
        db.session.add(calendar_entry)

        single_date += timedelta(days=1)

    db.session.commit()
    print(f"Created {len(calendar_entries)} school calendar entries")
    return calendar_entries


def get_term_for_date(date_obj):
    """Determine term based on date"""
    month = date_obj.month
    if 1 <= month <= 4:
        return "Term 1"
    elif 5 <= month <= 8:
        return "Term 2"
    else:
        return "Term 3"


def create_teacher_attendance(teachers, users):
    """Create teacher attendance records"""
    records = []
    start_date = datetime.now() - timedelta(days=30)

    for single_date in (start_date + timedelta(n) for n in range(30)):
        if single_date.weekday() >= 5:  # Skip weekends
            continue

        for teacher in teachers:
            if teacher.status != "Active":
                continue

            status = random.choices(
                ["present", "absent", "late", "excused"],
                weights=[0.80, 0.10, 0.05, 0.05],
            )[0]

            record = TeacherAttendance(
                teacher_id=teacher.id,
                date=single_date.date(),
                status=status,
                check_in_time=(
                    time(7, random.randint(30, 59))
                    if status in ["present", "late"]
                    else None
                ),
                check_out_time=(
                    time(14, random.randint(0, 30))
                    if status in ["present", "late"]
                    else None
                ),
                late_minutes=random.randint(1, 30) if status == "late" else 0,
                excuse_reason=fake.sentence() if status == "excused" else None,
                marked_by=random.choice(users).id,
            )
            records.append(record)
            db.session.add(record)

    db.session.commit()
    print(f"Created {len(records)} teacher attendance records")
    return records


def create_academic_records(students, subjects):
    records = []
    terms = ["Term 1", "Term 2", "Term 3"]
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
    elif score >= 70:
        return "2"
    elif score >= 60:
        return "3"
    elif score >= 50:
        return "4"
    elif score >= 40:
        return "5"
    else:
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
        if random.random() < 0.3:  # 30% of students have medical records
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
        if single_date.weekday() >= 5:  # Skip weekends
            continue

        # Determine term based on month
        month = single_date.month
        if 1 <= month <= 4:
            term = "Term 1"
        elif 5 <= month <= 8:
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
                date=single_date.date(),
                term=term,
                year=current_year,
                status=status,
                method=random.choice(["manual", "QR"]),
                excuse_reason=(
                    fake.sentence()
                    if status == "absent" and random.random() < 0.3
                    else None
                ),
                marked_by=1,  # Default to admin user
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
    terms = ["Term 1", "Term 2", "Term 3"]

    for enrollment in enrollments:
        # Each student takes 5-8 subjects
        num_subjects = random.randint(5, min(8, len(subjects)))
        student_subjects = random.sample(subjects, num_subjects)

        for subject in student_subjects:
            for term in terms:
                if random.random() > 0.6:  # 40% chance to create grade
                    continue

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
    elif score >= 70:
        return "Very Good"
    elif score >= 60:
        return "Good"
    elif score >= 50:
        return "Satisfactory"
    else:
        return "Needs Improvement"


def create_hallpasses(students, users):
    hallpasses = []
    destinations = ["Library", "Restroom", "Office", "Clinic", "Guidance Counselor"]

    active_students = [s for s in students if s.status == "active"]

    for student in random.sample(active_students, k=min(20, len(active_students))):
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
            mood_data={
                "happy": random.randint(0, 10),
                "sad": random.randint(0, 5),
                "excited": random.randint(0, 8),
                "focused": random.randint(0, 9),
            },
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

    for _ in range(50):  # Create 50 mood entries
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

    if not active_classes:
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
        # Get students in the same class as the assignment
        class_students = [
            s for s in active_students if s.class_id == assignment.class_id
        ]
        if not class_students:
            continue

        # Randomly select some students to have submissions
        for student in random.sample(class_students, k=min(10, len(class_students))):
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

    # Clear existing data and create tables
    db.drop_all()
    db.create_all()

    # Create core data
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

    # Create promotion system
    create_promotion_paths(classes)

    # Create academic data
    term_scores = create_term_scores(all_students, subjects, teachers)
    student_remarks = create_student_remarks(all_students, teachers)

    # Create users and system data
    users = create_users(teachers)
    create_attendance_settings(users)
    create_school_calendar()

    # Create additional records
    create_academic_records(all_students, subjects)
    create_medical_records(all_students)
    create_attendances(all_students, classes)
    create_teacher_attendance(teachers, users)
    enrollments = create_enrollments(all_students, classes)
    create_grades(enrollments, subjects)
    create_hallpasses(all_students, users)
    create_classrooms(classes)
    create_mood_entries(classes, users)

    # Create assignments
    assignments = create_assignments(teachers, classes, subjects)
    create_student_assignments(assignments, all_students)

    print("\nMock data generation completed successfully!")
    print(f"Summary:")
    print(f"- {len(students)} active students")
    print(f"- {len(graduated_students)} graduated students")
    print(f"- {len(teachers)} teachers")
    print(f"- {len([c for c in classes if not c.is_alumni_class])} active classes")
    print(f"- {len([c for c in classes if c.is_alumni_class])} alumni classes")
    print(f"- {len(subjects)} subjects")
    print(f"- {len(users)} users")
    print(f"- {len(term_scores)} term scores")
    print(f"- {len(teacher_assignments)} teacher-subject-class assignments")


if __name__ == "__main__":
    from app import create_app

    app = create_app()
    with app.app_context():
        generate_mock_data()
