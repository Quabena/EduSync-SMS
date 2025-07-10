from flask_wtf import FlaskForm
from flask_wtf.form import _Auto
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired
from app.models import Teacher


class ClassForm(FlaskForm):
    name = StringField("Class Name", validators=[DataRequired()])
    level = SelectField(
        "Level",
        choices=[
            ("JHS1", "JHS1"),
            ("JHS2", "JHS2"),
            ("JHS3", "JHS3"),
        ],
        validators=[DataRequired()],
    )
    section = StringField("A, B", validators=[DataRequired()])
    teacher_id = SelectField(
        "Form Master" if Teacher.gender == "Male" else "Mistress",
        validators=[DataRequired()],
    )
    submit = SubmitField("Save")

    def __init__(self, *args, **kwargs):
        super(ClassForm, self).__init__(*args, **kwargs)
        self.teacher_id.choices = [
            (t.id, t.full_name) for t in Teacher.query.order_by(Teacher.surname).all()
        ]
