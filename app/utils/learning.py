from app.models import Student, AcademicRecord, Subject
from app import db


def generate_learning_path(student_id):
    student = Student.query.get(student_id)
    if not student:
        return None

    # Get student's academic records
    records = AcademicRecord.query.filter_by(student_id=student_id).all()

    # Analyze performance
    subject_scores = {}
    for record in records:
        if record.subject_id not in subject_scores:
            subject_scores[record.subject_id] = []
        subject_scores[record.subject_id].append(record.score)

    # Calculate average scores
    subject_avg = {}
    for subject_id, scores in subject_scores.items():
        subject_avg[subject_id] = sum(scores) / len(scores)

    # Identify weak areas (scores below 60%)
    weak_subjects = []
    for subject_id, avg_score in subject_avg.items():
        if avg_score < 60:
            subject = Subject.query.get(subject_id)
            if subject:
                weak_subjects.append(
                    {
                        "subject": subject.name,
                        "avg_score": avg_score,
                        "resources": recommend_resources(
                            subject_id, student.learning_style
                        ),
                    }
                )

    # Create learning path
    learning_path = {
        "student": student.full_name,
        "learning_style": student.learning_style,
        "strong_subjects": [],
        "weak_subjects": weak_subjects,
        "recommendations": [],
    }

    # Add general recommendations based on learning style
    if student.learning_style == "visual":
        learning_path["recommendations"].append(
            {
                "type": "Study Tip",
                "content": "Use diagrams, charts, and color-coding to organize information",
            }
        )
        learning_path["recommendations"].append(
            {"type": "Resource", "content": "Watch educational videos on key topics"}
        )
    elif student.learning_style == "auditory":
        learning_path["recommendations"].append(
            {
                "type": "Study Tip",
                "content": "Record lectures and listen to them, or explain concepts out loud",
            }
        )
        learning_path["recommendations"].append(
            {
                "type": "Resource",
                "content": "Listen to educational podcasts on difficult subjects",
            }
        )
    else:  # kinesthetic
        learning_path["recommendations"].append(
            {
                "type": "Study Tip",
                "content": "Use physical objects or role-playing to understand concepts",
            }
        )
        learning_path["recommendations"].append(
            {
                "type": "Resource",
                "content": "Use interactive simulations and hands-on activities",
            }
        )

    return learning_path


def recommend_resources(subject_id, learning_style):
    # In a real system, this would query a resource database
    # For now, return mock resources based on subject and learning style

    subject = Subject.query.get(subject_id)
    if subject is None:
        return [{"type": "Error", "title": "Subject not found"}]

    resources = []

    # General resources for all styles
    resources.append({"type": "Textbook", "title": f"{subject.name} Core Textbook"})

    # Style-specific resources
    if learning_style == "visual":
        resources.append({"type": "Video", "title": f"Visual Guide to {subject.name}"})
        resources.append(
            {"type": "Infographic", "title": f"{subject.name} Key Concepts"}
        )
    elif learning_style == "auditory":
        resources.append({"type": "Podcast", "title": f"{subject.name} Explained"})
        resources.append({"type": "Audio Lesson", "title": f"Mastering {subject.name}"})
    else:  # kinesthetic
        resources.append(
            {"type": "Simulation", "title": f"Interactive {subject.name} Lab"}
        )
        resources.append(
            {"type": "Activity", "title": f"Hands-on {subject.name} Exercises"}
        )

    return resources


def assess_learning_style(student_id):
    """
    Placeholder for learning style assessment.
    To be developed in a real system later to analyze student
    performance data
    """

    student = Student.query.get(student_id)
    if not student:
        return None

    # Real Assessment system to be built later

    # Random assignment for demonstration
    import random

    styles = ["visual", "auditory", "kinesthetic"]
    student.learning_style = random.choice(styles)
    db.session.commit()
    return student.learning_style
