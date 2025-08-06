from functools import wraps
from flask import abort
from flask_login import current_user
import datetime

def role_required(role):
    """
    Decorator to restrict access to users with a specific role.
    Usage:
    @role_required('manager')
    def view_func():
        pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)  # Unauthorized
            if current_user.role != role:
                abort(403)  # Forbidden
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def roles_required(*roles):
    """
    Decorator to restrict access to users with any of the specified roles.
    Usage:
    @roles_required('admin', 'manager')
    def view_func():
        pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)  # Unauthorized
            if current_user.role not in roles:
                abort(403)  # Forbidden
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_week_start_end(date=None):
    """
    Return the start and end date of the week for the given date.
    Week is Monday to Sunday.
    If date is None, uses today's date.
    Returns (start_date, end_date) as datetime.date objects.
    """
    if date is None:
        date = datetime.date.today()
    start = date - datetime.timedelta(days=date.weekday())  # Monday
    end = start + datetime.timedelta(days=6)                # Sunday
    return start, end

def send_email(subject, recipient, body):
    """
    Placeholder function for sending emails.
    You can integrate Flask-Mail or any email service here.
    For now, it just prints email contents to console for testing.
    """
    print(f"Sending email to: {recipient}")
    print(f"Subject: {subject}")
    print(f"Body:\n{body}")
