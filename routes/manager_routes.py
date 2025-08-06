from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import Timesheet, User

manager_bp = Blueprint('manager', __name__)

def manager_required(f):
    from functools import wraps
    from flask import abort
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_manager():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@manager_bp.route('/timesheets/pending')
@login_required
@manager_required
def pending_timesheets():
    # Show all submitted timesheets pending approval
    timesheets = Timesheet.query.filter_by(status='submitted').order_by(Timesheet.date.desc()).all()
    return render_template('manager/manager_timesheets.html', timesheets=timesheets)

@manager_bp.route('/timesheets/approve/<int:ts_id>', methods=['POST'])
@login_required
@manager_required
def approve_timesheet(ts_id):
    timesheet = Timesheet.query.get_or_404(ts_id)
    if timesheet.status != 'submitted':
        flash('Timesheet is not pending approval.', 'warning')
        return redirect(url_for('manager.pending_timesheets'))

    timesheet.status = 'approved'
    db.session.commit()
    flash('Timesheet approved.', 'success')
    # TODO: Send notification email here
    return redirect(url_for('manager.pending_timesheets'))

@manager_bp.route('/timesheets/reject/<int:ts_id>', methods=['POST'])
@login_required
@manager_required
def reject_timesheet(ts_id):
    timesheet = Timesheet.query.get_or_404(ts_id)
    if timesheet.status != 'submitted':
        flash('Timesheet is not pending approval.', 'warning')
        return redirect(url_for('manager.pending_timesheets'))

    comment = request.form.get('manager_comment')
    timesheet.status = 'rejected'
    timesheet.manager_comment = comment
    db.session.commit()
    flash('Timesheet rejected.', 'info')
    # TODO: Send notification email here
    return redirect(url_for('manager.pending_timesheets'))
