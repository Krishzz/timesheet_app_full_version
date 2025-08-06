from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import Timesheet, TimesheetEntry
from datetime import datetime, timedelta

employee_bp = Blueprint('employee', __name__, url_prefix='/employee')

def get_monday(date_obj):
    return date_obj - timedelta(days=date_obj.weekday())

@employee_bp.route('/timesheets', methods=['GET'])
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
            flash('Week start date is required.', 'warning')
            return redirect(url_for('employee.new_timesheet'))
        try:
            week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
            week_start = get_monday(week_start)
        except:
            flash('Invalid date format.', 'warning')
            return redirect(url_for('employee.new_timesheet'))

        existing = Timesheet.query.filter_by(user_id=current_user.id, week_start=week_start).first()
        if existing:
            flash('Timesheet for this week already exists. You can edit it.', 'info')
            return redirect(url_for('employee.edit_timesheet', ts_id=existing.id))

        timesheet = Timesheet(user_id=current_user.id, week_start=week_start, status='draft')
        db.session.add(timesheet)
        db.session.commit()
        return redirect(url_for('employee.edit_timesheet', ts_id=timesheet.id))

    today = datetime.today().date()
    monday = get_monday(today)
    return render_template('employee/new_timesheet.html', default_week_start=monday)

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

    week_dates = [timesheet.week_start + timedelta(days=i) for i in range(7)]

    if request.method == 'POST':
        action = request.form.get('action')  # 'save' or 'submit'

        # Delete all existing entries for this timesheet before saving fresh data
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
                    continue  # skip blank rows

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

        if action == 'submit':
            timesheet.status = 'submitted'
            timesheet.submitted_at = datetime.utcnow()
        else:
            timesheet.status = 'draft'
            timesheet.submitted_at = None

        db.session.commit()
        flash(f'Timesheet {"submitted for approval" if action == "submit" else "saved as draft"}.', 'success')
        return redirect(url_for('employee.timesheet_view'))

    entries_by_date = []
    for day_date in week_dates:
        day_entries = TimesheetEntry.query.filter_by(timesheet_id=timesheet.id, date=day_date).all()
        entries_by_date.append({
            'date': day_date,
            'entries': day_entries
        })

    return render_template('employee/edit_weekly_timesheet.html', timesheet=timesheet, entries=entries_by_date)

@employee_bp.route('/timesheets/submit/<int:ts_id>', methods=['POST'])
@login_required
def submit_timesheet(ts_id):
    timesheet = Timesheet.query.get_or_404(ts_id)
    if timesheet.user_id != current_user.id:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('employee.timesheet_view'))
    if timesheet.status != 'draft':
        flash('Only drafts can be submitted.', 'warning')
        return redirect(url_for('employee.timesheet_view'))

    timesheet.status = 'submitted'
    timesheet.submitted_at = datetime.utcnow()
    db.session.commit()
    flash('Timesheet submitted for approval.', 'success')
    return redirect(url_for('employee.timesheet_view'))
