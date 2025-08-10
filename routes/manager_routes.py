from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required
from extensions import db
from models import Timesheet
from datetime import datetime, timedelta
from utils import role_required
from collections import defaultdict
from sqlalchemy.exc import SQLAlchemyError
import logging
import csv
from io import StringIO

manager_bp = Blueprint('manager', __name__, template_folder='templates/manager')

def get_month_start_end(today=None):
    if not today:
        today = datetime.utcnow().date()
    start = today.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end = start.replace(month=start.month + 1, day=1) - timedelta(days=1)
    return start, end

def get_clockin_clockout_summary(timesheet):
    day_times = defaultdict(lambda: {'clock_in': None, 'clock_out': None})

    for e in timesheet.entries:
        d = e.date.strftime('%Y-%m-%d')
        ci = e.clock_in.strftime('%H:%M') if e.clock_in else None
        co = e.clock_out.strftime('%H:%M') if e.clock_out else None

        if ci:
            if (day_times[d]['clock_in'] is None) or (ci < day_times[d]['clock_in']):
                day_times[d]['clock_in'] = ci
        if co:
            if (day_times[d]['clock_out'] is None) or (co > day_times[d]['clock_out']):
                day_times[d]['clock_out'] = co

    parts = []
    for day, times in sorted(day_times.items()):
        ci = times['clock_in'] or '-'
        co = times['clock_out'] or '-'
        parts.append(f"{day}: {ci} - {co}")

    return "; ".join(parts)

@manager_bp.route('/dashboard')
@login_required
@role_required('manager')
def manager_dashboard():
    try:
        # Pending timesheets (status = submitted)
        pending_timesheets = Timesheet.query.filter_by(status='submitted').order_by(Timesheet.week_start.desc()).all()
        pending_count = len(pending_timesheets)
    except SQLAlchemyError as e:
        logging.error(f"DB error fetching pending timesheets: {e}")
        flash("Error loading pending timesheets. Please try again later.", "danger")
        pending_timesheets = []
        pending_count = 0

    # History filters
    status_filter = request.args.get('status', default='')
    start_date = request.args.get('start_date', default='')
    end_date = request.args.get('end_date', default='')

    # Default start/end date to current month if not provided
    if not start_date or not end_date:
        month_start, month_end = get_month_start_end()
        if not start_date:
            start_date = month_start.strftime('%Y-%m-%d')
        if not end_date:
            end_date = month_end.strftime('%Y-%m-%d')

    history_query = Timesheet.query.filter(Timesheet.status.in_(['approved', 'rejected']))

    if status_filter in ['approved', 'rejected']:
        history_query = history_query.filter(Timesheet.status == status_filter)

    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        history_query = history_query.filter(Timesheet.week_start >= start)
    except ValueError:
        start = None

    try:
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        history_query = history_query.filter(Timesheet.week_start <= end)
    except ValueError:
        end = None

    history_timesheets = history_query.order_by(Timesheet.week_start.desc()).all()

    # Add clock-in/out summaries to each history timesheet
    for ts in history_timesheets:
        ts.clockin_clockout_summary = get_clockin_clockout_summary(ts)

    max_date = datetime.utcnow().date().strftime('%Y-%m-%d')

    return render_template('manager/manager_dashboard.html', 
                           pending_count=pending_count, 
                           pending_timesheets=pending_timesheets,
                           history_timesheets=history_timesheets,
                           status_filter=status_filter,
                           start_date=start_date,
                           end_date=end_date,
                           max_date=max_date)


@manager_bp.route('/timesheets/view/<int:timesheet_id>')
@login_required
@role_required('manager')
def view_timesheet(timesheet_id):
    timesheet = Timesheet.query.get_or_404(timesheet_id)
    if timesheet.status not in ['submitted', 'approved']:
        flash('Timesheet is not in a viewable state.', 'warning')
        return redirect(url_for('manager.manager_dashboard'))

    grouped_entries = defaultdict(list)
    daily_totals = defaultdict(float)
    daily_clock_times = {}  # store single clock_in/out per day
    grand_total = 0.0

    for e in timesheet.entries:
        date_key = e.date.strftime('%Y-%m-%d')
        hours = float(e.hours) if e.hours else 0.0

        # Collect project entries
        grouped_entries[date_key].append({
            'project': e.project or "",
            'description': e.description or "",
            'hours': hours,
        })

        daily_totals[date_key] += hours
        grand_total += hours

        # Find earliest clock_in and latest clock_out for the day
        ci = e.clock_in
        co = e.clock_out
        if date_key not in daily_clock_times:
            daily_clock_times[date_key] = {'clock_in': ci, 'clock_out': co}
        else:
            # Update earliest clock_in
            if ci and (daily_clock_times[date_key]['clock_in'] is None or ci < daily_clock_times[date_key]['clock_in']):
                daily_clock_times[date_key]['clock_in'] = ci
            # Update latest clock_out
            if co and (daily_clock_times[date_key]['clock_out'] is None or co > daily_clock_times[date_key]['clock_out']):
                daily_clock_times[date_key]['clock_out'] = co

    sorted_dates = sorted(grouped_entries.keys())

    return render_template(
        'manager/view_timesheet.html',
        timesheet=timesheet,
        grouped_entries=grouped_entries,
        daily_totals=daily_totals,
        daily_clock_times=daily_clock_times,
        grand_total=grand_total,
        sorted_dates=sorted_dates
    )




@manager_bp.route('/timesheets/approve/<int:timesheet_id>', methods=['POST'])
@login_required
@role_required('manager')
def approve_timesheet(timesheet_id):
    try:
        timesheet = Timesheet.query.get_or_404(timesheet_id)
    except SQLAlchemyError as e:
        logging.error(f"DB error fetching timesheet {timesheet_id} for approval: {e}")
        flash("Error fetching timesheet. Please try again later.", "danger")
        return redirect(url_for('manager.manager_dashboard'))

    if timesheet.status != 'submitted':
        flash('Cannot approve timesheet that is not submitted.', 'warning')
        return redirect(url_for('manager.manager_dashboard'))

    timesheet.status = 'approved'
    timesheet.manager_comments = request.form.get('manager_comments', '')
    timesheet.approved_at = datetime.utcnow()

    try:
        db.session.commit()
        flash('Timesheet approved successfully.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"DB error approving timesheet {timesheet_id}: {e}")
        flash("Error approving timesheet. Please try again later.", "danger")

    return redirect(url_for('manager.manager_dashboard'))


@manager_bp.route('/timesheets/reject/<int:timesheet_id>', methods=['POST'])
@login_required
@role_required('manager')
def reject_timesheet(timesheet_id):
    try:
        timesheet = Timesheet.query.get_or_404(timesheet_id)
    except SQLAlchemyError as e:
        logging.error(f"DB error fetching timesheet {timesheet_id} for rejection: {e}")
        flash("Error fetching timesheet. Please try again later.", "danger")
        return redirect(url_for('manager.manager_dashboard'))

    if timesheet.status != 'submitted':
        flash('Cannot reject timesheet that is not submitted.', 'warning')
        return redirect(url_for('manager.manager_dashboard'))

    timesheet.status = 'rejected'
    timesheet.manager_comments = request.form.get('manager_comments', '')

    try:
        db.session.commit()
        flash('Timesheet rejected.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"DB error rejecting timesheet {timesheet_id}: {e}")
        flash("Error rejecting timesheet. Please try again later.", "danger")

    return redirect(url_for('manager.manager_dashboard'))


@manager_bp.route('/timesheets/export-history')
@login_required
@role_required('manager')
def export_manager_history():
    status_filter = request.args.get('status', default='')
    start_date = request.args.get('start_date', default='')
    end_date = request.args.get('end_date', default='')

    history_query = Timesheet.query.filter(Timesheet.status.in_(['approved', 'rejected']))

    if status_filter in ['approved', 'rejected']:
        history_query = history_query.filter(Timesheet.status == status_filter)

    try:
        if start_date:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            history_query = history_query.filter(Timesheet.week_start >= start)
        if end_date:
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            history_query = history_query.filter(Timesheet.week_start <= end)
    except ValueError:
        pass

    timesheets = history_query.order_by(Timesheet.week_start.desc()).all()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow([
        'ID', 'Employee', 'Week Start', 'Status', 'Submitted At', 'Entry Date',
        'Project', 'Description', 'Hours', 'Clock In', 'Clock Out', 'Manager Comments'
    ])

    for ts in timesheets:
        for e in ts.entries:
            cw.writerow([
                ts.id,
                ts.user.username if ts.user else 'Unknown',
                ts.week_start.strftime('%Y-%m-%d'),
                ts.status,
                ts.submitted_at.strftime('%Y-%m-%d %H:%M') if ts.submitted_at else '',
                e.date.strftime('%Y-%m-%d'),
                e.project or '',
                e.description or '',
                e.hours or 0,
                e.clock_in.strftime('%H:%M') if e.clock_in else '',
                e.clock_out.strftime('%H:%M') if e.clock_out else '',
                ts.manager_comments or ''
            ])

    output = si.getvalue()
    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=manager_timesheets_history.csv'}
    )
