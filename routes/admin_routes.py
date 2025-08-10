from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file
from flask_login import login_required, current_user
from models import User, Timesheet, TimesheetEntry
from extensions import db
from datetime import datetime, timedelta
from calendar import monthrange
from functools import wraps
import io
import csv

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash("Access denied.", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    return render_template("admin/admin_dashboard.html",
                           user_count=User.query.count(),
                           employee_count=User.query.filter_by(role='employee').count(),
                           manager_count=User.query.filter_by(role='manager').count(),
                           admin_count=User.query.filter_by(role='admin').count(),
                           timesheet_count=Timesheet.query.count())


@admin_bp.route("/users")
@login_required
@admin_required
def view_users():
    role_filter = request.args.get('role')
    query = User.query
    if role_filter:
        query = query.filter_by(role=role_filter)
    users = query.order_by(User.role, User.username).all()
    return render_template("admin/admin_users.html", users=users, role_filter=role_filter)


@admin_bp.route("/user/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_user():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]
        manager_id = request.form.get("manager_id") or None

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or email already exists.", "danger")
            return redirect(url_for("admin.create_user"))

        user = User(username=username, email=email, role=role, manager_id=manager_id)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("User created successfully.", "success")
        return redirect(url_for("admin.view_users"))

    managers = User.query.filter_by(role="manager").all()
    return render_template("admin/admin_user_form.html", action="create", managers=managers)


@admin_bp.route("/user/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        user.username = request.form["username"]
        user.email = request.form["email"]
        user.role = request.form["role"]
        user.manager_id = request.form.get("manager_id") or None

        new_password = request.form.get("password")
        if new_password:
            user.set_password(new_password)

        db.session.commit()
        flash("User updated successfully.", "success")
        return redirect(url_for("admin.view_users"))

    managers = User.query.filter_by(role="manager").all()
    return render_template("admin/admin_user_form.html", action="edit", user=user, managers=managers)


@admin_bp.route("/user/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("User deleted.", "warning")
    return redirect(url_for("admin.view_users"))


@admin_bp.route("/timesheets")
@login_required
@admin_required
def view_timesheets():
    status_filter = request.args.get("status")
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    today = datetime.today().date()
    max_allowed_date = today.replace(day=monthrange(today.year, today.month)[1])
    default_start = today.replace(day=1)
    default_end = max_allowed_date

    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            if start_date > max_allowed_date:
                start_date = max_allowed_date
        else:
            start_date = default_start

        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            if end_date > max_allowed_date:
                end_date = max_allowed_date
        else:
            end_date = default_end
    except ValueError:
        flash("Invalid date format. Use YYYY-MM-DD.", "warning")
        start_date = default_start
        end_date = default_end

    query = Timesheet.query.order_by(Timesheet.week_start.desc())

    if status_filter:
        query = query.filter_by(status=status_filter)

    query = query.filter(Timesheet.week_start >= start_date, Timesheet.week_start <= end_date)

    timesheets = query.all()

    return render_template(
        "admin/admin_timesheets.html",
        timesheets=timesheets,
        status_filter=status_filter,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        max_date=max_allowed_date.strftime("%Y-%m-%d")
    )


@admin_bp.route("/timesheet/<int:timesheet_id>")
@login_required
@admin_required
def view_timesheet_detail(timesheet_id):
    timesheet = Timesheet.query.get_or_404(timesheet_id)
    return render_template("admin/admin_timesheet_detail.html", timesheet=timesheet)


@admin_bp.route('/timesheet/edit/<int:ts_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_timesheet(ts_id):
    timesheet = Timesheet.query.get_or_404(ts_id)
    week_dates = [timesheet.week_start + timedelta(days=i) for i in range(5)]

    def parse_time(tstr):
        if not tstr:
            return None
        try:
            return datetime.strptime(tstr, '%H:%M').time()
        except ValueError:
            return datetime.strptime(tstr, '%H:%M:%S').time()

    if request.method == 'POST':
        # Clear existing entries for the timesheet
        TimesheetEntry.query.filter_by(timesheet_id=timesheet.id).delete()

        for i, day_date in enumerate(week_dates):
            clock_in_str = request.form.get(f'clock_in_{i}')
            clock_out_str = request.form.get(f'clock_out_{i}')

            clock_in = parse_time(clock_in_str)
            clock_out = parse_time(clock_out_str)

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

        new_status = request.form.get('status')
        timesheet.status = new_status
        if new_status == 'submitted':
            timesheet.submitted_at = datetime.utcnow()
            timesheet.approved_at = None
        elif new_status == 'approved':
            timesheet.approved_at = datetime.utcnow()
        else:
            timesheet.submitted_at = None
            timesheet.approved_at = None

        db.session.commit()
        flash(f'Timesheet updated and status changed to {new_status}.', 'success')
        return redirect(url_for('admin.view_timesheets'))

    # GET: fetch entries grouped by day for form display
    entries_by_date = []
    for day_date in week_dates:
        day_entries = TimesheetEntry.query.filter_by(timesheet_id=timesheet.id, date=day_date).all()
        entries_by_date.append({'date': day_date, 'entries': day_entries})

    return render_template('admin/admin_timesheet_form.html', timesheet=timesheet, entries=entries_by_date)


@admin_bp.route("/timesheets/export")
@login_required
@admin_required
def export_timesheets():
    status_filter = request.args.get("status")
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    today = datetime.today().date()
    max_allowed_date = today.replace(day=monthrange(today.year, today.month)[1])
    default_start = today.replace(day=1)
    default_end = max_allowed_date

    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            if start_date > max_allowed_date:
                start_date = max_allowed_date
        else:
            start_date = default_start

        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            if end_date > max_allowed_date:
                end_date = max_allowed_date
        else:
            end_date = default_end
    except ValueError:
        flash("Invalid date format. Use YYYY-MM-DD.", "warning")
        return redirect(url_for("admin.view_timesheets"))

    query = Timesheet.query.order_by(Timesheet.week_start.desc())

    if status_filter:
        query = query.filter_by(status=status_filter)

    query = query.filter(Timesheet.week_start >= start_date, Timesheet.week_start <= end_date)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Timesheet ID", "User", "Week Start", "Status", "Submitted At", "Approved At",
        "Entry Date", "Clock In", "Clock Out", "Project", "Description", "Hours"
    ])

    timesheets = query.all()
    for ts in timesheets:
        for entry in ts.entries:
            writer.writerow([
                ts.id, ts.user.username, ts.week_start, ts.status,
                ts.submitted_at, ts.approved_at,
                entry.date, entry.clock_in, entry.clock_out,
                entry.project, entry.description, entry.hours
            ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name='timesheets_export.csv'
    )
