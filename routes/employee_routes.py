from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import Timesheet, TimesheetEntry
from datetime import datetime, timedelta

employee_bp = Blueprint('employee', __name__, url_prefix='/employee')

def get_monday(date_obj):
    return date_obj - timedelta(days=date_obj.weekday())

@employee_bp.route('/timesheets')
@login_required
def timesheet_view():
    timesheets = Timesheet.query.filter_by(user_id=current_user.id).order_by(Timesheet.week_start.desc()).all()
    return render_template('employee/timesheet_list.html', timesheets=timesheets)

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

        # Remove existing entries to replace
        TimesheetEntry.query.filter_by(timesheet_id=timesheet.id).delete()

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
                entry = TimesheetEntry(
                    timesheet_id=timesheet.id,
                    date=day_date,
                    clock_in=clock_in,
                    clock_out=clock_out,
                    project=proj.strip(),
                    description=desc.strip(),
                    hours=float(hrs)
                )
                db.session.add(entry)

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
