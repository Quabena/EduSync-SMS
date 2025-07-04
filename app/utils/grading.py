import pytesseract
from PIL import Image
import re
from app.models import Assignment, Student, Subject
from app import db
import os


def process_assignement(image_path, assignment_id):
    # Performing OCR
    text = pytesseract.image_to_string(Image.open(image_path))

    # Getting assignment details
    assignment = Assignment.query.get(assignment_id)
    if not assignment:
        return None, "Assignment not found!"

    # Extracting answers using question numbers
    answers = {}
    question_pattern = re.compile(r"Q(\d+)[:.)\s]*(.*?)(?=(Q\d+|$))", re.DOTALL)
    for match in question_pattern.finditer(text):
        q_num = int(match.group(1))
        answer = match.group(2).strip()
        answers[q_num] = answer

    # Grading assignment (simple implementation)
    total_questions = len(assignment.questions)
    correct_answers = 0

    for q_num, question in assignment.questions.items():
        student_answer = answers.get(q_num, "").lower()
        correct_answer = question["answer"].lower()

        # Simple grading using exact match grading
        if student_answer == correct_answer:
            correct_answers += 1

    score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0

    # Generating feedback
    feedback = generate_feedback(score, assignment.subject_id)

    return score, feedback


def generate_feedback(score, subject_id):
    subject = Subject.query.get(subject_id)
    subject_name = subject.name if subject else "this subject"

    if score >= 90:
        return f"Excellent work! You've demonstrated mastery of {subject_name}"
    elif score >= 75:
        return f"Good job! You have a strong understanding of {subject_name}, with room for improvement in some areas."
    elif score >= 60:
        return f"Fair performance. Review exams material and focus on areas where you struggled."
    elif score >= 50:
        return f"Needs improvement. Please review the core concepts of {subject_name} and seek help if needed."
    else:
        return f"Significant improvement needed. See teacher in charge to review the fundamentals of {subject_name}."
