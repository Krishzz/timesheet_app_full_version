from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from extensions import db
from models import Timesheet, TimesheetEntry
from datetime import datetime, timedelta

employee_bp = Blueprint('employee', __name__, url_prefix='/employee')

def get_monday(date_obj):
    return date_obj - timedelta(days=date_obj.weekday())

def get_month_start_end(today=None):
    if not today:
        today = datetime.utcnow().date()
    start = today.replace(day=1)
    # Calculate last day of month
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end = start.replace(month=start.month + 1, day=1) - timedelta(days=1)
    return start, end

@employee_bp.route('/timesheets')
@login_required
def timesheet_view():
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

    query = Timesheet.query.filter_by(user_id=current_user.id)

    if status_filter:
        query = query.filter(Timesheet.status == status_filter)

    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        query = query.filter(Timesheet.week_start >= start)
    except ValueError:
        start = None

    try:
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        query = query.filter(Timesheet.week_start <= end)
    except ValueError:
        end = None

    timesheets = query.order_by(Timesheet.week_start.desc()).all()

    max_date = datetime.utcnow().date().strftime('%Y-%m-%d')

    return render_template(
        'employee/timesheet_list.html',
        timesheets=timesheets,
        status_filter=status_filter,
        start_date=start_date,
        end_date=end_date,
        # max_date=max_date
    )

@employee_bp.route('/timesheets/new', methods=['GET', 'POST'])
@login_required
def new_timesheet():
    if request.method == 'POST':
        week_start_str = request.form.get('week_start')
        if not week_start_str:
            flash('Please select a week start date.', 'warning')
            return redirect(url_for('employee.new_timesheet'))
        try:
            week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
            week_start = get_monday(week_start)
        except ValueError:
            flash('Invalid date format.', 'warning')
            return redirect(url_for('employee.new_timesheet'))

        existing = Timesheet.query.filter_by(user_id=current_user.id, week_start=week_start).first()
        if existing:
            flash('Timesheet for this week already exists. You can edit it.', 'info')
            return redirect(url_for('employee.edit_timesheet', ts_id=existing.id))

        new_ts = Timesheet(user_id=current_user.id, week_start=week_start, status='draft')
        db.session.add(new_ts)
        db.session.commit()
        return redirect(url_for('employee.edit_timesheet', ts_id=new_ts.id))

    default_monday = get_monday(datetime.utcnow().date())
    return render_template('employee/new_timesheet.html', default_week_start=default_monday)

@employee_bp.route('/timesheets/edit/<int:ts_id>', methods=['GET', 'POST'])
@login_required
def edit_timesheet(ts_id):
    timesheet = Timesheet.query.get_or_404(ts_id)
    if timesheet.user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('employee.timesheet_view'))

    if timesheet.status == 'approved':
        flash('Approved timesheets cannot be edited.', 'warning')
        return redirect(url_for('employee.timesheet_view'))

    week_dates = [timesheet.week_start + timedelta(days=i) for i in range(5)]

    if request.method == 'POST':
        action = request.form.get('action')  # 'save' or 'submit'

        # Block submit if week_start is in future
        if action == 'submit':
            today = datetime.utcnow().date()
            if timesheet.week_start > today:
                flash("Cannot submit timesheet for a future week.", "warning")
                return redirect(url_for('employee.edit_timesheet', ts_id=timesheet.id))

        # Remove existing entries to replace
        TimesheetEntry.query.filter_by(timesheet_id=timesheet.id).delete()

        total_hours = 0.0  # track total hours

        for i, day_date in enumerate(week_dates):
            clock_in_str = request.form.get(f'clock_in_{i}')
            clock_out_str = request.form.get(f'clock_out_{i}')

            clock_in = datetime.strptime(clock_in_str, '%H:%M').time() if clock_in_str else None
            clock_out = datetime.strptime(clock_out_str, '%H:%M').time() if clock_out_str else None

            projects = request.form.getlist(f'project_{i}[]')
            descriptions = request.form.getlist(f'description_{i}[]')
            hours_list = request.form.getlist(f'hours_{i}[]')

            for proj, desc, hrs in zip(projects, descriptions, hours_list):
                if not proj.strip() or not hrs.strip():
                    continue
                try:
                    hrs_float = float(hrs)
                except ValueError:
                    hrs_float = 0.0

                total_hours += hrs_float

                entry = TimesheetEntry(
                    timesheet_id=timesheet.id,
                    date=day_date,
                    clock_in=clock_in,
                    clock_out=clock_out,
                    project=proj.strip(),
                    description=desc.strip(),
                    hours=hrs_float
                )
                db.session.add(entry)

        # Prevent submit if total hours is zero
        if action == 'submit' and total_hours == 0:
            flash("Cannot submit empty timesheets.", "warning")
            db.session.rollback()  # Undo added entries
            return redirect(url_for('employee.edit_timesheet', ts_id=timesheet.id))

        timesheet.status = 'submitted' if action == 'submit' else 'draft'
        timesheet.submitted_at = datetime.utcnow() if action == 'submit' else None
        db.session.commit()

        flash(f'Timesheet {"submitted for approval" if action == "submit" else "saved as draft"}.', 'success')
        return redirect(url_for('employee.timesheet_view'))

    # GET: show entries by date
    entries_by_date = []
    for day_date in week_dates:
        day_entries = TimesheetEntry.query.filter_by(timesheet_id=timesheet.id, date=day_date).all()
        entries_by_date.append({'date': day_date, 'entries': day_entries})

    return render_template('employee/edit_weekly_timesheet.html', timesheet=timesheet, entries=entries_by_date)


    # GET: show entries by date
    entries_by_date = []
    for day_date in week_dates:
        day_entries = TimesheetEntry.query.filter_by(timesheet_id=timesheet.id, date=day_date).all()
        entries_by_date.append({'date': day_date, 'entries': day_entries})

    return render_template('employee/edit_weekly_timesheet.html', timesheet=timesheet, entries=entries_by_date)

@employee_bp.route('/timesheets/delete/<int:ts_id>', methods=['POST'])
@login_required
def delete_timesheet(ts_id):
    timesheet = Timesheet.query.get_or_404(ts_id)
    if timesheet.user_id != current_user.id:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('employee.timesheet_view'))

    if timesheet.status != 'draft':
        flash('Only draft timesheets can be deleted.', 'warning')
        return redirect(url_for('employee.timesheet_view'))

    db.session.delete(timesheet)
    db.session.commit()
    flash('Draft timesheet deleted.', 'success')
    return redirect(url_for('employee.timesheet_view'))

@employee_bp.route('/timesheets/view/<int:ts_id>')
@login_required
def view_timesheet(ts_id):
    timesheet = Timesheet.query.get_or_404(ts_id)
    if timesheet.user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('employee.timesheet_view'))

    week_dates = [timesheet.week_start + timedelta(days=i) for i in range(7)]
    entries_by_date = []
    total_hours = 0
    for day_date in week_dates:
        day_entries = TimesheetEntry.query.filter_by(timesheet_id=timesheet.id, date=day_date).all()
        entries_by_date.append({'date': day_date, 'entries': day_entries})
        for e in day_entries:
            total_hours += e.hours if e.hours else 0

    return render_template('employee/view_timesheet.html', timesheet=timesheet, entries=entries_by_date, total_hours=total_hours)

@employee_bp.route('/timesheets/export')
@login_required
def export_timesheets():
    status = request.args.get('status')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = Timesheet.query.filter_by(user_id=current_user.id)

    if status:
        query = query.filter(Timesheet.status == status)

    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Timesheet.week_start >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Timesheet.week_start <= end)
        except ValueError:
            pass

    timesheets = query.order_by(Timesheet.week_start.desc()).all()

    import csv
    from io import StringIO
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Week Start', 'Status', 'Submitted At', 'Total Hours', 'Manager Comments'])
    for ts in timesheets:
        total_hours = sum(e.hours for e in ts.entries)
        cw.writerow([
            ts.id,
            ts.week_start.strftime('%Y-%m-%d'),
            ts.status,
            ts.submitted_at.strftime('%Y-%m-%d %H:%M') if ts.submitted_at else '',
            total_hours,
            ts.manager_comments or ''
        ])

    output = si.getvalue()
    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=timesheets_export.csv'}
    )
