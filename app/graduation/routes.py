from flask import render_template, redirect, request, flash, url_for, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Student, GraduationStatus, Alumni, Class
from app.decorators import role_required
from datetime import datetime, timezone
from sqlalchemy import extract
from app.graduation import bp


@bp.route("/graduation")
@login_required
@role_required(["admin", "headteacher"])
def graduation_management():
    """Main Graudation Management Page"""
    # Getting students who are candidates for graduation (final years')
    final_year_classes = Class.query.filter(
        (Class.level.ilike("%JHS 3%"))
        | (Class.level.ilike("%Form 3%"))
        | (Class.level.ilike("%Year 3%")),
        Class.is_alumni_class == False,
    ).all()

    final_year_class_ids = [c.id for c in final_year_classes]
    graduation_candidates = Student.query.filter(
        Student.class_id.in_(final_year_class_ids), Student.status == "active"
    ).all()

    # GEtting recent graduations
    recent_graduations = (
        GraduationStatus.query.order_by(GraduationStatus.graduation_date.desc())
        .limit(10)
        .all()
    )

    # Read query parameters (default = 1)
    candidates_page = request.args.get("candidates_page", 1, type=int)
    recent_page = request.args.get("recent_page", 1, type=int)

    return render_template(
        "graduation/management.html",
        candidates=graduation_candidates,
        recent_graduations=recent_graduations,
        candidates_page=candidates_page,
        recent_page=recent_page,
    )


# Route to graduate students
@bp.route("/graduate-student/<int:student_id>", methods=["GET", "POST"])
@login_required
@role_required(["admin", "headteacher"])
def graduate_students(student_id):
    """Graduate student and move to alumni"""
    student = Student.query.get_or_404(student_id)

    if request.method == "POST":
        graduation_year = request.form.get("graduation_year")
        graduation_date = request.form.get("graduation_date")
        final_grade = request.form.get("final_grade")
        remarks = request.form.get("remarks")

        if not graduation_year:
            flash("Graduation year is required", "danger")
            return redirect(url_for("alumni.graduate_student", student_id=student_id))

        try:
            # Get or create alumni class for this graduation year
            alumni_class = Class.get_alumni_class(graduation_year)

            # Store original class before moving to alumni
            original_class_id = student.class_id

            # Update student to alumni class and status
            student.original_class_id = original_class_id
            student.class_id = alumni_class.id
            student.status = "graduated"

            # Create graduation record
            graduation_record = GraduationStatus(
                student_id=student.id,
                graduation_year=graduation_year,
                graduation_date=(
                    datetime.strptime(graduation_date, "%Y-%m-%d").date()
                    if graduation_date
                    else None
                ),
                final_grade=final_grade,
                remarks=remarks,
            )

            # Archive student to alumni table
            alumni = Alumni(
                original_student_id=student.id,
                first_name=student.first_name,
                middle_name=student.middle_name,
                surname=student.surname,
                gender=student.gender,
                date_of_birth=student.date_of_birth,
                admission_date=student.admission_date or datetime.now().date(),
                graduation_year=graduation_year,
                graduation_date=(
                    datetime.strptime(graduation_date, "%Y-%m-%d").date()
                    if graduation_date
                    else datetime.now().date()
                ),
                hometown=student.hometown,
                father_name=student.father_name,
                mother_name=student.mother_name,
                guardian_name=student.guardian_name,
                guardian_contact=student.guardian_contact,
                religion=student.religion,
                medical_records=student.medical_records,
                photo_path=student.photo_path,
                final_class=student.classroom.name if student.classroom else "Unknown",
            )

            db.session.add(graduation_record)
            db.session.add(alumni)
            db.session.commit()

            flash(
                f"{student.full_name} has been graduated successfully and moved to Alumni Class!",
                "success",
            )
            return redirect(url_for("graduation.graduation_management"))

        except Exception as e:
            db.session.rollback()
            flash(f"Error during graduation: {str(e)}", "danger")
            return redirect(
                url_for("graduation.graduate_student", student_id=student_id)
            )

    current_year = datetime.now().year
    return render_template(
        "graduation/graduate_student.html",
        student=student,
        current_year=current_year,
        now=lambda: datetime.now(timezone.utc),
    )


@bp.route("/alumni")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def alumni_list():
    """View all alumni"""
    year = request.args.get("year")

    # Get alumni from both Alumni table and Student table with alumni status
    alumni_query = Alumni.query
    if year:
        alumni_query = alumni_query.filter_by(graduation_year=year)

    alumni_from_table = alumni_query.order_by(
        Alumni.graduation_year.desc(), Alumni.surname
    ).all()

    # Also get graduated students from Student table
    graduate_students = (
        Student.query.filter_by(status="graduated")
        .order_by(Student.surname, Student.first_name)
        .all()
    )

    # Combine and sort
    all_alumni = list(alumni_from_table)
    for student in graduate_students:
        # Check if student already exists in alumni table
        if not any(
            alum.original_student_id == student.id for alum in alumni_from_table
        ):
            # Creating a temporary alumni object for display
            class AlumniProxy:
                def __init__(self, student):
                    self.id = student.id
                    self.original_student_id = student.id
                    self.full_name = student.full_name
                    self.graduation_year = "Unknown"
                    self.final_class = (
                        student.classroom.name if student.classroom else "Unknown"
                    )
                    self.gender = student.gender
                    self.date_of_birth = student.date_of_birth
                    self.photo_path = student.photo_path

            all_alumni.append(AlumniProxy(student))

    # Getting distinct graduation years for filter
    graduate_years = (
        db.session.query(Alumni.graduation_year)
        .distinct()
        .order_by(Alumni.graduation_year.desc())
        .all()
    )
    years = [year[0] for year in graduate_years]

    return render_template(
        "graduation/alumni_list.html",
        alumni=all_alumni,
        years=years,
        selected_year=year,
        now=lambda: datetime.now(timezone.utc),
    )


# Route to view all alumni classes
@bp.route("/alumni-classes")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def alumni_classes():
    """View all alumni classes"""
    alumni_classes = (
        Class.query.filter_by(is_alumni_class=True).order_by(Class.name.desc()).all()
    )

    # Get student counts for each alumni class
    class_data = []
    for alumni_class in alumni_classes:
        student_count = Student.query.filter_by(
            class_id=alumni_class.id, status="graduated"
        ).count()
        class_data.append({"class": alumni_class, "student_count": student_count})

    return render_template("graduation/alumni_classes.html", class_data=class_data)


# ---Alumni class detail route---
@bp.route("/alumni-class/<int:class_id>")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def alumni_class_detail(class_id):
    """View students in a specific alumni class"""
    alumni_class = Class.query.get_or_404(class_id)

    if not alumni_class.is_alumni_class:
        flash("This is not an alumni class", "warning")
        return redirect(url_for("graduation.alumni_classes"))

    students = (
        Student.query.filter_by(class_id=class_id, status="graduated")
        .order_by(Student.surname, Student.first_name)
        .all()
    )

    return render_template(
        "graduation/alumni_class_detail.html",
        alumni_class=alumni_class,
        students=students,
    )


# ---Route to revert alumni---
@bp.route("/revert-graduation/<int:student_id>", methods=["POST"])
@login_required
@role_required(["admin", "headteacher"])
def revert_alumni(student_id):
    """Revert a student's graduation status (for corrections only!)"""
    student = Student.query.get_or_404(student_id)

    if student.status != "graduated":
        flash("Student is graduated", "warning")
        return redirect(url_for("students.detail", student_id=student_id))

    # Move student back to original class if available
    if student.original_class_id:
        student.class_id = student.original_class_id
        student.original_class_id = None

    student.status = "active"

    # Remove from alumni table is exists
    alumni_record = Alumni.query.filter_by(original_student_id=student.id).first()
    if alumni_record:
        db.session.delete(alumni_record)

    # Remove graduation status
    graduate_record = GraduationStatus.query.filter_by(student_id=student.id).first()
    if graduate_record:
        db.session.delete(graduate_record)

    db.session.commit()

    flash(f"{student.full_name}'s graduation has been reverted successfully", "success")
    return redirect(url_for("students.detail", student_id=student_id))


@bp.route("/alumni/<int:alumni_id>")
@login_required
@role_required(["admin", "headteacher", "teacher"])
def alumni_detail(alumni_id):
    """View alumni details"""
    alumni = Alumni.query.get_or_404(alumni_id)

    # Try to get graduation record if available
    graduation_record = GraduationStatus.query.filter_by(
        student_id=alumni.original_student_id
    ).first()

    return render_template(
        "graduation/alumni_detail.html",
        alumni=alumni,
        graduation_record=graduation_record,
    )


@bp.route("/graduation-statistics")
@login_required
@role_required(["admin", "headteacher"])
def graduation_statistics():
    """View graduation statistics"""
    # Get graduation counts by year
    year_counts = (
        db.session.query(Alumni.graduation_year, db.func.count(Alumni.id))
        .group_by(Alumni.graduation_year)
        .order_by(Alumni.graduation_year.desc())
        .all()
    )

    # Get gender distribution for latest graduation year
    latest_year = db.session.query(db.func.max(Alumni.graduation_year)).scalar()

    gender_distribution = []
    if latest_year:
        gender_distribution = (
            db.session.query(Alumni.gender, db.func.count(Alumni.id))
            .filter(Alumni.graduation_year == latest_year)
            .group_by(Alumni.gender)
            .all()
        )

    # Get class distribution for latest graduation year
    class_distribution = []
    if latest_year:
        class_distribution = (
            db.session.query(Alumni.final_class, db.func.count(Alumni.id))
            .filter(Alumni.graduation_year == latest_year)
            .group_by(Alumni.final_class)
            .all()
        )

    return render_template(
        "graduation/statistics.html",
        year_counts=year_counts,
        gender_distribution=gender_distribution,
        class_distribution=class_distribution,
        latest_year=latest_year,
    )
