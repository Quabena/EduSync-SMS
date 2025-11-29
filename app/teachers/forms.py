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
    date_posted_to_present_station = DateField(
        "Date Posted Here", format="%Y-%m-%d", validators=[DataRequired()]
    )
    last_promotion_date = DateField(
        "Last Promotion Date", format="%Y-%m-%d", validators=[DataRequired()]
    )
    first_appointment_date = DateField(
        "Date of First Appointment", format="%Y-%m-%d", validators=[DataRequired()]
    )
    hometown = StringField("Hometown", validators=[Optional()])
    hometown_district = StringField("Hometown District", validators=[Optional()])
    live_at = StringField("Residence", validators=[Optional()])
    digital_address = StringField("Residence", validators=[Optional()])
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
    ghana_card = StringField("Ghana Card", validators=[DataRequired()])
    salary_grade = StringField("Salary Grade", validators=[DataRequired()])
    salary_grade_type = SelectField(
        "Salary Grade Type",
        choices=[("PSH", "PSH"), ("PSL", "PSL")],
        validators=[Optional()],
    )
    current_rank = StringField("Current Rank", validators=[DataRequired()])
    registered_number = StringField("Registered Number", validators=[Optional()])
    ntc_number = StringField("NTC Number", validators=[Optional()])
    ssnit_number = StringField("SSNIT Number", validators=[Optional()])
    phone_number = TelField("Phone Number", validators=[DataRequired()])
    email = EmailField("Email", validators=[Optional(), Email()])
    religion = SelectField(
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
    status = SelectField(
        "Status",
        choices=[
            ("", "Not Specified"),
            ("Active", "Active"),
            ("Transferred", "Transferred"),
            ("Retired", "Retired"),
            ("Deceased", "Deceased"),
        ],
        validators=[Optional()],
    )
    hometown_region = SelectField(
        "hometown_region",
        choices=[
            ("", "Not Specified"),
            ("Ahafo Region", "Ahafo Region"),
            ("Ashanti Region", "Ashanti Region"),
            ("Bono Region", "Bono Region"),
            ("Bono East Region", "Bono East Region"),
            ("Central Region", "Central Region"),
            ("Eastern Region", "Eastern Region"),
            ("Greater Accra Region", "Greater Accra Region"),
            ("North-East Region", "North-East Region"),
            ("Northern Region", "Northern Region"),
            ("Oti Region", "Oti Region"),
            ("Savannah Region", "Savannah Region"),
            ("Upper-East Region", "Upper-East Region"),
            ("Volta Region", "Volta Region"),
            ("Western Region", "Western Region"),
            ("Western-North Region", "Western-North Region"),
        ],
        validators=[Optional()],
    )
    marital_status = SelectField(
        "Marital Status",
        choices=[
            ("", "Not Specified"),
            ("Single", "Single"),
            ("Married", "Married"),
            ("Divorced", "Divorced"),
            ("Widowed", "Widowed"),
        ],
        validators=[Optional()],
    )
    staff_role = SelectField(
        "Role",
        choices=[
            ("Headteacher", "Headteacher"),
            ("Ass. Headteacher", "Ass. Headteacher"),
            ("Staff", "Staff"),
        ],
        validators=[Optional()],
    )
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
            (s.id, s.name) for s in Subject.query.order_by(Subject.name).all()  # type: ignore
        ]
        self.assigned_classes.choices = [
            (c.id, c.name) for c in Class.get_active_classes()
        ]
