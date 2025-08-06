from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'employee', 'manager', 'admin'
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    manager = db.relationship('User', remote_side=[id], backref='employees', uselist=False)
    timesheets = db.relationship('Timesheet', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Timesheet(db.Model):
    __tablename__ = "timesheets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    week_start = db.Column(db.Date, nullable=False)  # Monday date of the week
    status = db.Column(db.String(20), nullable=False, default='draft')  # draft, submitted, approved, rejected
    submitted_at = db.Column(db.DateTime, nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    manager_comments = db.Column(db.Text, nullable=True)

    entries = db.relationship('TimesheetEntry', backref='timesheet', lazy=True, cascade='all, delete-orphan')

class TimesheetEntry(db.Model):
    __tablename__ = "timesheet_entries"

    id = db.Column(db.Integer, primary_key=True)
    timesheet_id = db.Column(db.Integer, db.ForeignKey('timesheets.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    clock_in = db.Column(db.Time, nullable=True)
    clock_out = db.Column(db.Time, nullable=True)
    project = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    hours = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"<Entry {self.project} on {self.date} - {self.hours}h>"
