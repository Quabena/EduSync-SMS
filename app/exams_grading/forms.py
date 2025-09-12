# forms.py (or wherever you keep your form classes)
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, FileField
from wtforms.validators import DataRequired, Optional


class SchoolInfoForm(FlaskForm):
    name = StringField("School Name", validators=[DataRequired()])
    motto = StringField("School Motto", validators=[Optional()])
    address = TextAreaField("Address", validators=[Optional()])
    phone = StringField("Phone Number", validators=[Optional()])
    email = StringField("Email Address", validators=[Optional()])
    website = StringField("Website", validators=[Optional()])
    logo = FileField("School Logo", validators=[Optional()])


class TermDatesForm(FlaskForm):
    academic_year = StringField("Academic Year", validators=[DataRequired()])
    term = SelectField(
        "Term",
        choices=[
            ("", "Select Term"),
            ("Term 1", "Term 1"),
            ("Term 2", "Term 2"),
            ("Term 3", "Term 3"),
        ],
        validators=[DataRequired()],
    )
    start_date = DateField("Start Date", format="%Y-%m-%d", validators=[DataRequired()])
    end_date = DateField("End Date", format="%Y-%m-%d", validators=[DataRequired()])
    vacation_date = DateField(
        "Vacation Date", format="%Y-%m-%d", validators=[DataRequired()]
    )
    reopening_date = DateField(
        "Reopening Date", format="%Y-%m-%d", validators=[DataRequired()]
    )


class StudentRemarksForm(FlaskForm):
    conduct = TextAreaField("Conduct", validators=[Optional()])
    attitude = TextAreaField("Attitude", validators=[Optional()])
    interests = TextAreaField("Interests", validators=[Optional()])
    remarks = TextAreaField("General Remarks", validators=[Optional()])
