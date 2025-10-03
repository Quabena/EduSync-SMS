from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Student, Teacher
from sqlalchemy import or_

bp = Blueprint("search", __name__, url_prefix="/search")


@bp.route("/api", methods=["GET"])
@login_required
def api_search():
    query = request.args.get("q", "").strip()

    if len(query) < 2:
        return jsonify({"students": [], "teachers": []})

    try:
        pattern = f"%{query}%"

        # Search students
        students = (
            Student.query.filter(
                or_(
                    Student.first_name.ilike(pattern),
                    Student.middle_name.ilike(pattern),
                    Student.surname.ilike(pattern),
                    Student.guardian_name.ilike(pattern),
                )
            )
            .limit(10)
            .all()
        )

        # Search teachers
        teachers = (
            Teacher.query.filter(
                or_(
                    Teacher.first_name.ilike(pattern),
                    Teacher.middle_name.ilike(pattern),
                    Teacher.surname.ilike(pattern),
                    Teacher.staff_id.ilike(pattern),
                )
            )
            .limit(10)
            .all()
        )

        return jsonify(
            {
                "students": [
                    {
                        "id": s.id,
                        "full_name": s.full_name,
                        "guardian_name": s.guardian_name or "No guardian",
                    }
                    for s in students
                ],
                "teachers": [
                    {
                        "id": t.id,
                        "full_name": t.full_name,
                        "staff_id": t.staff_id or "No staff ID",
                    }
                    for t in teachers
                ],
            }
        )

    except Exception as e:
        print(f"Search error: {e}")
        return jsonify({"students": [], "teachers": []})
