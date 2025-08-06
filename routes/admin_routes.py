from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import Timesheet, User

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    from functools import wraps
    from flask import abort
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/timesheets')
@login_required
@admin_required
def all_timesheets():
    # Show all timesheets from all users
    timesheets = Timesheet.query.order_by(Timesheet.date.desc()).all()
    return render_template('admin/admin_timesheets.html', timesheets=timesheets)

@admin_bp.route('/timesheets/edit/<int:ts_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_timesheet(ts_id):
    timesheet = Timesheet.query.get_or_404(ts_id)

    if request.method == 'POST':
        timesheet.user_id = int(request.form.get('user_id'))
        timesheet.date = request.form.get('date')
        timesheet.project = request.form.get('project')
        timesheet.description = request.form.get('description')
        timesheet.hours = float(request.form.get('hours'))
        timesheet.status = request.form.get('status')
        timesheet.manager_comment = request.form.get('manager_comment')
        db.session.commit()
        flash('Timesheet updated successfully.', 'success')
        return redirect(url_for('admin.all_timesheets'))

    users = User.query.all()
    return render_template('admin/edit_timesheet.html', timesheet=timesheet, users=users)
