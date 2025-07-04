from flask_wtf import FlaskForm
from flask_wtf.form import _Auto
from wtforms import (
    StringField,
    DateField,
    SelectField,
    TextAreaField,
    SubmitField,
    FileField,
)
from wtforms.validators import DataRequired, Optional
from app.models import Class


class StudentForm(FlaskForm):
    first_name = StringField("First Name", validators=[DataRequired()])
    middle_name = StringField("Middle Name", validators=[Optional()])
    surname = StringField("Surname", validators=[DataRequired()])
    gender = SelectField(
        "Gender",
        choices=[("Male", "Male"), ("Female", "Female")],
        validators=[DataRequired()],
    )
    date_of_birth = DateField(
        "Date of Birth", format="%Y-%m-%d", validators=[DataRequired()]
    )
    hometown = StringField("Hometown", validators=[Optional()])
    father_name = StringField("Father's Name", validators=[Optional()])
    mother_name = StringField("Mother's Name", validators=[Optional()])
    guardian_name = StringField("Guardian Name", validators=[Optional()])
    guardian_contact = StringField("Guardian Contact", validators=[Optional()])
    medical_records = TextAreaField("Medical Records", validators=[Optional()])
    photo = FileField("Student Photo", validators=[Optional()])
    class_id = SelectField("Class", coerce=int, validators=[DataRequired()])
    learning_style = SelectField(
        "Learning Style",
        choices=[
            ("", "Not Assessed"),
            ("visual", "Visual"),
            ("auditory", "Auditory"),
            ("kinesthetic", "Kinesthetic"),
        ],
        validators=[Optional()],
    )
    submit = SubmitField("Save")

    def __init__(self, *args, **kwargs):
        super(StudentForm, self).__init__(*args, **kwargs)
        self.class_id.choices = [
            (c.id, c.name) for c in Class.query.order_by(Class.name).all()
        ]
