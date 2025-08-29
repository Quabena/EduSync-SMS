from flask_wtf import FlaskForm
from flask_wtf.form import _Auto
from wtforms import (
    StringField,
    DateField,
    SelectField,
    TextAreaField,
    SubmitField,
    FileField,
    IntegerField,
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
        "Date of Birth",
        format="%Y-%m-%d",
        render_kw={"type": "date"},
        validators=[DataRequired()],
    )
    admission_date = DateField(
        "Admission Date",
        format="%Y-%m-%d",
        render_kw={"type": "date"},  # Added HTML5 date input
        validators=[DataRequired()],
    )
    hometown = StringField("Hometown", validators=[Optional()])
    father_name = StringField("Father's Name", validators=[Optional()])
    mother_name = StringField("Mother's Name", validators=[Optional()])
    guardian_name = StringField(
        "Guardian Name", validators=[DataRequired()]
    )  # Changed to required
    guardian_contact = StringField(
        "Guardian Contact", validators=[DataRequired()]
    )  # Changed to required
    medical_records = TextAreaField("Medical Records", validators=[Optional()])
    height = IntegerField("Height (cm)", validators=[Optional()])  # Added unit label
    weight = IntegerField("Weight (kg)", validators=[Optional()])  # Added unit label
    photo = FileField("Student Photo", validators=[Optional()])
    class_id = SelectField("Class", coerce=int, validators=[DataRequired()])
    learning_style = SelectField(
        "Learning Style",
        choices=[
            ("", "Not Assessed"),
            ("Visual", "Visual"),
            ("Auditory", "Auditory"),
            ("Kinesthetic", "Kinesthetic"),
            ("Reading/Writing", "Reading/Writing"),
        ],
        validators=[Optional()],
    )
    religion = SelectField(  # Added religion field
        "Religion",
        choices=[
            ("", "Select Religion"),
            ("Christian", "Christian"),
            ("Muslim", "Muslim"),
            ("Traditionalist", "Traditionalist"),
            ("Other", "Other"),
        ],
        validators=[Optional()],
    )
    submit = SubmitField("Save")

    def __init__(self, *args, **kwargs):
        super(StudentForm, self).__init__(*args, **kwargs)
        self.class_id.choices = [
            (c.id, c.name) for c in Class.query.order_by(Class.name).all()
        ]
