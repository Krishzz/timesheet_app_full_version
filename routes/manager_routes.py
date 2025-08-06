from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from extensions import db
from models import Timesheet
from utils import role_required

manager_bp = Blueprint('manager', __name__, template_folder='templates/manager')

@manager_bp.route('/dashboard')
@login_required
@role_required('manager')
def manager_dashboard():
    # Show dashboard with count and list of pending timesheets
    pending_timesheets = Timesheet.query.filter_by(status='submitted').order_by(Timesheet.week_start.desc()).all()
    pending_count = len(pending_timesheets)
    return render_template('manager/manager_dashboard.html', 
                           pending_count=pending_count, 
                           pending_timesheets=pending_timesheets)

@manager_bp.route('/timesheets/view/<int:timesheet_id>')
@login_required
@role_required('manager')
def view_timesheet(timesheet_id):
    timesheet = Timesheet.query.get_or_404(timesheet_id)
    if timesheet.status not in ['submitted', 'approved']:
        flash('Timesheet is not in a viewable state.', 'warning')
        return redirect(url_for('manager.manager_dashboard'))

    # For simplicity, just pass timesheet.entries directly, or group as needed
    entries = timesheet.entries  # Adjust if you want grouping in model
    return render_template('manager/view_timesheet.html', timesheet=timesheet, entries=entries)

@manager_bp.route('/timesheets/approve/<int:timesheet_id>', methods=['POST'])
@login_required
@role_required('manager')
def approve_timesheet(timesheet_id):
    timesheet = Timesheet.query.get_or_404(timesheet_id)
    if timesheet.status != 'submitted':
        flash('Cannot approve timesheet that is not submitted.', 'warning')
        return redirect(url_for('manager.manager_dashboard'))
    timesheet.status = 'approved'
    timesheet.manager_comments = request.form.get('manager_comments', '')
    db.session.commit()
    flash('Timesheet approved successfully.', 'success')
    return redirect(url_for('manager.manager_dashboard'))

@manager_bp.route('/timesheets/reject/<int:timesheet_id>', methods=['POST'])
@login_required
@role_required('manager')
def reject_timesheet(timesheet_id):
    timesheet = Timesheet.query.get_or_404(timesheet_id)
    if timesheet.status != 'submitted':
        flash('Cannot reject timesheet that is not submitted.', 'warning')
        return redirect(url_for('manager.manager_dashboard'))
    timesheet.status = 'rejected'
    timesheet.manager_comments = request.form.get('manager_comments', '')
    db.session.commit()
    flash('Timesheet rejected.', 'success')
    return redirect(url_for('manager.manager_dashboard'))
