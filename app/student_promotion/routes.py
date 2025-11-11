from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app.decorators import role_required
from datetime import datetime
from sqlalchemy import or_, and_

from app import db
from app.models import Class, Student, PromotionPath, PromotionRecord

import _json

from app.student_promotion import bp


@bp.route("/", methods=["GET", "POST"])
@login_required
@role_required(["admin", "headteacher"])
def index():
    return render_template("student_promotion/index.html")


@bp.route("/dashboard", methods=["GET", "POST"])
@login_required
@role_required(["admin", "headteacher"])
def promotion_dashboard():
    """Main Promotion Dashboard"""
    # Getting all active classes (non-alumni)
    classes = Class.get_active_classes()

    # Getting promotion hierarchy
    hierarchy = Class.get_promotion_hierarchy()

    # Getting statistics
    total_students = Student.query.filter_by(status="active").count()
    classes_with_students = []

    for class_ in classes:
        student_count = len(class_.get_students_eligible_for_promotion())
        promotion_paths = class_.get_promotion_paths()

        if student_count > 0:
            classes_with_students.append(
                {
                    "class": class_,
                    "student_count": student_count,
                    "promotion_paths": promotion_paths,
                }
            )
    return render_template(
        "student_promotion/dashboard.html",
        classes_with_students=classes_with_students,
        hierarchy=hierarchy,
        total_students=total_students,
    )


# --- Routes for bulk promotion ---
@bp.route("/bulk-promotion", methods=["GET", "POST"])
@login_required
@role_required(["admin", "headteacher"])
def bulk_promotion():
    class_id = request.args.get("class_id", type=int)
    target_class_id = request.args.get("class_id", type=int)

    current_class = None
    target_class = None
    students = []

    if class_id:
        current_class = Class.query.get_or_404(class_id)
        students = current_class.get_students_eligible_for_promotion()

        if target_class_id:
            target_class = Class.query.get_or_404(target_class_id)

    classes = Class.get_active_classes()

    if request.method == "POST":
        student_ids = request.form.getlist("student_ids")
        target_class_id = request.form.get("target_class_id", type=int)

        promotion_notes = request.form.get("promotion_notes", "")

        if not student_ids or not target_class_id:
            flash("Please select students and target class.", "error")
            return redirect(
                url_for("student_promotion.bulk_promotion", class_id=class_id)
            )

        target_class = Class.query.get_or_404(target_class_id)
        promoted_count = 0

        for student_id in student_ids:
            student = Student.query.get(student_id)
            if student and student.status == "active":
                student.promote_student(target_class_id, current_user, promotion_notes)
                promoted_count += 1

        flash(
            f"Successfully promoted {promoted_count} students to {target_class.name}!",
            "success",
        )
        return redirect(url_for("student_promotion.promotion_dashboard"))

    return render_template(
        "student_promotion/bulk_promotion.html",
        current_class=current_class,
        target_class=target_class,
        students=students,
        classes=classes,
    )


# --- Route for single promotion ---
@bp.route("/single-promotion", methods=["GET", "POST"])
@login_required
@role_required(["admin", "headteacher"])
def individual_promotion():
    """Individual student promotion interface"""
    student_id = request.args.get("student_id", type=int)
    student = None
    promotion_paths = []

    if student_id:
        student = Student.query.get_or_404(student_id)
        if student.classroom:
            promotion_paths = student.classroom.get_promotion_paths()

    # Search functionality
    search_query = request.args.get("search", "")
    students = []

    if search_query:
        students = (
            Student.query.filter(
                and_(
                    Student.status == "active",
                    or_(
                        Student.first_name.ilike(f"%{search_query}%"),
                        Student.middle_name.ilike(f"%{search_query}%"),
                        Student.surname.ilike(f"%{search_query}%"),
                        Student.full_name.ilike(f"%{search_query}%"),
                    ),
                )
            )
            .limit(50)
            .all()
        )

    if request.method == "POST":
        student_id = request.form.get("student_id", type=int)
        target_class_id = request.form.get("target_class_id", type=int)
        promotion_notes = request.form.get("promotion_notes", "")

        if not student_id or not target_class_id:
            flash("Please select a student and target class.", "error")
            return redirect(url_for("student_promotion.individual_promotion"))

        student = Student.query.get_or_404(student_id)
        target_class = Class.query.get_or_404(target_class_id)

        # Checking if promotion path already exists
        valid_path = PromotionPath.query.filter_by(
            from_class_id=student.class_id, to_class_id=target_class_id, is_active=True
        ).first()

        if not valid_path:
            flash("Invalid promotion path selected!", "error")
            return redirect(
                url_for("student_promotion.individual_promotion", student_id=student_id)
            )

        student.promote_student(target_class_id, current_user, promotion_notes)

        flash(
            f"Successfully promoted {student.full_name} to {target_class.name}!",
            "success",
        )
        return redirect(
            url_for("student_promotion.individual_promotion", student_id=student_id)
        )
    return render_template(
        "student_promotion/individual_promotion.html",
        student=student,
        students=students,
        promotion_paths=promotion_paths,
        search_query=search_query,
    )


# --- Promotion history route ---
@bp.route("/promotion-history", methods=["GET"])
@login_required
@role_required(["admin", "headteacher"])
def promotion_history():
    # Filtering parameters
    student_id = request.args.get("student_id", type=int)
    class_id = request.args.get("class_id", type=int)
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    # Building query
    query = PromotionRecord.query.join(Student).join(
        Class, PromotionRecord.from_class_id == Class.id
    )

    if student_id:
        query = query.filter(PromotionRecord.student_id == student_id)

    if class_id:
        query = query.filter(PromotionRecord.from_class_id == class_id)

    if start_date:
        query = query.filter(
            PromotionRecord.promotion_date >= datetime.strptime(start_date, "%d-%m-%Y")
        )

    if end_date:
        query = query.filter(
            PromotionRecord.promotion_date <= datetime.strptime(end_date, "%d-%m-%Y")
        )

    records = query.order_by(PromotionRecord.promotion_date.desc()).all()

    students = Student.query.filter_by(status="active").all()
    classes = Class.get_active_classes()

    return render_template(
        "student_promotion/history.html",
        records=records,
        students=students,
        classes=classes,
        student_id=student_id,
        class_id=class_id,
        start_date=start_date,
        end_date=end_date,
    )


# --- Route for managing promotion paths ---
@bp.route("/manage-paths", methods=["GET", "POST"])
@login_required
@role_required(["admin", "headteacher"])
def manage_promotion_paths():
    """Promotion paths between classes"""
    if request.method == "POST":
        if "add_path" in request.form:
            from_class_id = request.form.get("from_class_id", type=int)
            to_class_id = request.form.get("to_class_id", type=int)
            order = request.form.get("order", 0, type=int)

            if from_class_id == to_class_id:
                flash("You cannot create promotion path to the same class.", "error")
            else:
                # Check if path already exists
                existing_path = PromotionPath.query.filter_by(
                    from_class_id=from_class_id, to_class_id=to_class_id
                ).first()

                if existing_path:
                    flash("Promotion path already exists!", "error")
                else:
                    path = PromotionPath(
                        from_class_id=from_class_id,
                        to_class_id=to_class_id,
                        order=order,
                    )
                    db.session.add(path)
                    db.session.commit()
                    flash("Promotion path added successfully!", "success")

        elif "toggle_path" in request.form:
            path_id = request.form.get("path_id", type=int)
            path = PromotionPath.query.get_or_404(path_id)
            path.is_active = not path.is_active
            db.session.commit()
            flash("Promotion path updated successfully!", "success")

        elif "delete_path" in request.form:
            path_id = request.form.get("path_id", type=int)
            path = PromotionPath.query.get_or_404(path_id)
            db.session.delete(path)
            db.session.commit()
            flash("Promotion path deleted successfully!", "success")

        return redirect(url_for("student_promotion.manage_promotion_paths"))

    paths = PromotionPath.query.order_by(
        PromotionPath.order, PromotionPath.from_class_id
    ).all()
    classes = Class.get_active_classes()

    return render_template(
        "student_promotion/manage_paths.html", paths=paths, classes=classes
    )


# API endpoints for AJAX
@login_required
def get_students_by_class():
    """API endpoint to get students by class"""
    class_id = request.args.get("class_id", type=int)
    if not class_id:
        return jsonify([])

    class_ = Class.query.get_or_404(class_id)
    students = class_.get_students_eligible_for_promotion()

    student_data = [
        {
            "id": student.id,
            "full_name": student.full_name,
            "student_id": student.id,  # I may take this off later
            "current_class": student.classroom.name if student.classroom else "None",
        }
        for student in students
    ]

    return jsonify(student_data)


@login_required
def get_promotion_paths():
    """API endpoint to get promotion paths for a class"""
    class_id = request.args.get("class_id", type=int)
    if not class_id:
        return jsonify([])

    class_ = Class.query.get_or_404(class_id)
    paths = class_.get_promotion_paths()

    path_data = [
        {
            "id": path.to_class_id,
            "name": path.to_class.level,
            "description": f"Promote to {path.to_class.name}",
        }
        for path in paths
    ]

    return jsonify(path_data)
