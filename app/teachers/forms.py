from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    DateField,
    SelectField,
    TextAreaField,
    SubmitField,
    FileField,
    TelField,
    EmailField,
)
from wtforms.validators import DataRequired, Optional, Email
from app.models import Subject, Class
from datetime import date
from wtforms.fields import MultipleFileField, SelectMultipleField


class TeacherForm(FlaskForm):
    first_name = StringField("First Name", validators=[DataRequired()])
    middle_name = StringField("Middle Name", validators=[Optional()])
    surname = StringField("Surname", validators=[DataRequired()])
    gender = SelectField(
        "Gender",
        choices=[("Male", "Male"), ("Female", "Female"), ("Other", "Other")],
        validators=[DataRequired()],
    )
    date_of_birth = DateField(
        "Date of Birth", format="%Y-%m-%d", validators=[DataRequired()]
    )
    hometown = StringField("Hometown", validators=[Optional()])
    college_attended = StringField("College Attended", validators=[Optional()])
    area_of_specialization = StringField(
        "Area of Specialization", validators=[Optional()]
    )
    academic_certificate = StringField("Academic Certificate", validators=[Optional()])
    academic_area_of_study = StringField(
        "Academic Area of Study", validators=[Optional()]
    )
    academic_college = StringField("Academic College", validators=[Optional()])
    professional_certificate = StringField(
        "Professional Certificate", validators=[Optional()]
    )
    professional_area_of_study = StringField(
        "Professional Area of Study", validators=[Optional()]
    )
    professional_college = StringField("Professional College", validators=[Optional()])
    staff_id = StringField("Staff ID", validators=[DataRequired()])
    registered_number = StringField("Registered Number", validators=[Optional()])
    ntc_number = StringField("NTC Number", validators=[Optional()])
    ssnit_number = StringField("SSNIT Number", validators=[Optional()])
    phone_number = TelField("Phone Number", validators=[DataRequired()])
    email = EmailField("Email", validators=[Optional(), Email()])
    emergency_contact_name = StringField(
        "Emergency Contact Name", validators=[DataRequired()]
    )
    emergency_contact_number = TelField(
        "Emergency Contact Number", validators=[DataRequired()]
    )
    photo = FileField("Photo", validators=[Optional()])
    certificates = MultipleFileField("Certificates (PDF)", validators=[Optional()])
    specialization_id = SelectField(
        "Specialization Subject", coerce=int, validators=[DataRequired()]
    )
    assigned_classes = SelectMultipleField(
        "Assigned Classes",
        coerce=int,
        choices=[],
        validators=[Optional()],
    )
    submit = SubmitField("Save")

    def __init__(self, *args, **kwargs):
        super(TeacherForm, self).__init__(*args, **kwargs)
        self.specialization_id.choices = [
            (s.id, s.name) for s in Subject.query.order_by(Subject.name).all()
        ]
        self.assigned_classes.choices = [
            (c.id, c.name) for c in Class.query.order_by(Class.name).all()
        ]
