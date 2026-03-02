from flask import Flask, render_template, request, redirect, url_for, Response, session, flash
import mysql.connector
from datetime import datetime
import csv
import io
import logging
import os
from logging.handlers import RotatingFileHandler
from functools import wraps

app = Flask(__name__)

# --- Logging configuration ---
LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), "app.log")

_log_handler = RotatingFileHandler(LOG_FILE_PATH, maxBytes=1_000_000, backupCount=3)
_log_handler.setLevel(logging.INFO)
_log_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
)

app.logger.setLevel(logging.INFO)
app.logger.addHandler(_log_handler)

# Role hierarchy: super_admin > admin > end_user
ROLES = ("super_admin", "admin", "end_user")


def _is_active(val):
    """Treat is_active from DB (may be VARCHAR '0'/'1' or int) as boolean."""
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, int):
        return val != 0
    return str(val).strip().lower() in ("1", "true", "yes")


def log_event(action: str, **extra):
    """
    Write a structured audit log entry that includes basic user and request info.
    Never pass sensitive values like raw passwords in **extra.
    """
    try:
        user_id = session.get("user_id")
        user_email = session.get("user_email")
        user_role = session.get("user_role")
        ip = request.remote_addr
        ua = request.headers.get("User-Agent", "")
        payload = {
            "user_id": user_id,
            "email": user_email,
            "role": user_role,
            "ip": ip,
            "ua": ua,
        }
        payload.update(extra or {})
        app.logger.info("%s | %s", action, payload)
    except Exception:
        # Logging must never break the main request.
        pass


def login_required(f):
    """Require an authenticated session."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to access this page.", "info")
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return wrapped


def role_required(*allowed_roles):
    """Require one of the given roles (use after @login_required)."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            role = session.get("user_role")
            if role not in allowed_roles:
                flash("You do not have permission to access this page.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return wrapped
    return decorator

# NOTE: For production, load this from an environment variable instead.
app.config["SECRET_KEY"] = "dev-secret-change-me"

# Function to get a fresh DB connection
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="ticketing_db"
    )


def get_entries_pk_column(db):
    """Determine the primary key column for the entries table."""
    cursor = db.cursor()
    try:
        cursor.execute("SHOW COLUMNS FROM entries")
        cols = [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()

    if "ticket_no" in cols:
        pk_col = "ticket_no"
    elif "id" in cols:
        pk_col = "id"
    else:
        pk_col = None

    return pk_col, set(cols)


def compute_next_job_order(cursor, jo_col: str) -> str:
    """
    Compute the next JO in the format `jo-0001` based on the max existing value
    in the given column (`job_order` or legacy `remedy`).
    """
    if jo_col not in {"job_order", "remedy"}:
        raise ValueError("Unsupported JO column")

    cursor.execute(
        f"""
        SELECT
            MAX(CAST(SUBSTRING(LOWER(TRIM({jo_col})), 4) AS UNSIGNED)) AS max_num
        FROM entries
        WHERE {jo_col} IS NOT NULL
          AND LOWER(TRIM({jo_col})) REGEXP '^jo-[0-9]+$'
        """
    )
    row = cursor.fetchone()
    max_num = row["max_num"] if isinstance(row, dict) else (row[0] if row else None)
    next_num = (int(max_num) if max_num is not None else 0) + 1
    return f"jo-{next_num:04d}"


@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    db = get_db_connection()  # new connection per request
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM entries")
    entries = cursor.fetchall()
    cursor.close()
    db.close()  # close connection after use
    return render_template(
        "index.html",
        entries=entries,
        active_page="home",
    )


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM entries")
    entries = cursor.fetchall()
    cursor.close()
    db.close()
    status_counts = {"Pending": 0, "Ongoing": 0, "Complete": 0}
    tickets_by_date = {}
    tickets_by_store = {}

    for entry in entries:
        # Normalize status into three buckets
        status_raw = (entry.get("status") or entry.get("Status") or "pending").lower()
        if status_raw in ("complete", "completed"):
            status_label = "Complete"
        elif status_raw in ("ongoing", "in progress", "in_progress"):
            status_label = "Ongoing"
        else:
            status_label = "Pending"
        status_counts[status_label] = status_counts.get(status_label, 0) + 1

        # Group tickets by calendar day (using either `date` or `created_at`)
        date_val = entry.get("date") or entry.get("created_at")
        if date_val:
            if isinstance(date_val, datetime):
                day_key = date_val.date().isoformat()
            else:
                # Fall back to string representation, trimming to YYYY-MM-DD when possible
                day_str = str(date_val)
                day_key = day_str[:10] if len(day_str) >= 10 else day_str
            tickets_by_date[day_key] = tickets_by_date.get(day_key, 0) + 1

        # Group tickets by store
        store_name = entry.get("store_name") or entry.get("Name") or "Unknown store"
        tickets_by_store[store_name] = tickets_by_store.get(store_name, 0) + 1

    # Sort dates chronologically for the time-series chart
    tickets_by_date_sorted = dict(sorted(tickets_by_date.items(), key=lambda kv: kv[0]))

    return render_template(
        "dashboard.html",
        active_page="dashboard",
        entries=entries,
        status_counts=status_counts,
        tickets_by_date=tickets_by_date_sorted,
        tickets_by_store=tickets_by_store,
    )


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/backups")
@login_required
def backups():
    selected_date_str = request.args.get("date", "")
    download = request.args.get("download") == "1"
    export_all = request.args.get("all") == "1"

    entries = []
    filter_error = None
    cols = set()

    # When a specific date is chosen, filter tickets for that day
    if selected_date_str:
        try:
            # Validate date from the date picker
            selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()

            db = get_db_connection()
            cursor = db.cursor(dictionary=True)
            try:
                # Work with either `date` or `created_at` column, if present
                cursor.execute("SHOW COLUMNS FROM entries")
                field_rows = cursor.fetchall()
                cols = {row["Field"] for row in field_rows}

                date_col = None
                if "date" in cols:
                    date_col = "date"
                elif "created_at" in cols:
                    date_col = "created_at"

                if not date_col:
                    filter_error = "No date column found on the entries table."
                else:
                    cursor.execute(
                        f"SELECT * FROM entries WHERE DATE({date_col}) = %s ORDER BY {date_col} ASC",
                        (selected_date_str,),
                    )
                    entries = cursor.fetchall()
            finally:
                cursor.close()
                db.close()
        except ValueError:
            filter_error = "Invalid date format. Please use the date picker."

    # If user requested a CSV download for all tickets (no date filter)
    if export_all and download and not filter_error:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        try:
            cursor.execute("SHOW COLUMNS FROM entries")
            field_rows = cursor.fetchall()
            cols = {row["Field"] for row in field_rows}

            cursor.execute("SELECT * FROM entries ORDER BY id ASC" if "id" in cols else "SELECT * FROM entries")
            entries = cursor.fetchall()
        finally:
            cursor.close()
            db.close()

        output = io.StringIO()
        fieldnames = list(entries[0].keys()) if entries else list(cols)

        if fieldnames:
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for row in entries:
                writer.writerow(row)

        csv_data = output.getvalue()
        output.close()

        filename = "tickets-all.csv"
        log_event("tickets_export_all_csv")
        response = Response(csv_data, mimetype="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        return response

    # If user requested a CSV download for a specific date and we have a valid date, return CSV instead of HTML
    if selected_date_str and download and not filter_error:
        output = io.StringIO()

        fieldnames = []
        if entries:
            fieldnames = list(entries[0].keys())
        elif cols:
            fieldnames = list(cols)

        if fieldnames:
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for row in entries:
                writer.writerow(row)

        csv_data = output.getvalue()
        output.close()

        filename = f"tickets-{selected_date_str}.csv"
        log_event("tickets_export_date_csv", selected_date=selected_date_str)
        response = Response(csv_data, mimetype="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        return response

    return render_template(
        "backup.html",
        active_page="backups",
        entries=entries,
        selected_date=selected_date_str,
        filter_error=filter_error,
    )


@app.route("/logs")
@login_required
@role_required("super_admin", "admin")
def logs():
    import ast
    import re
    from datetime import datetime

    # Get filter parameters
    search_query = request.args.get("search", "").strip().lower()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    log_entries = []
    total_lines = 0
    filtered_entries = []
    log_pattern = re.compile(
        r"^(?P<timestamp>[^[]+)\s+\[(?P<level>[^\]]+)\]\s+(?P<event>\S+)\s*\|\s*(?P<payload>.*)$"
    )

    try:
        if os.path.exists(LOG_FILE_PATH):
            with open(LOG_FILE_PATH, "r", encoding="utf-8", errors="ignore") as f:
                raw_lines = f.readlines()
            total_lines = len(raw_lines)
            # Show the most recent 1000 lines for filtering, newest first
            for raw in reversed(raw_lines[-1000:]):
                line = raw.rstrip("\n")
                entry = {"raw": line}
                match = log_pattern.match(line)
                if match:
                    entry["timestamp"] = match.group("timestamp").strip()
                    entry["level"] = match.group("level").strip()
                    entry["event"] = match.group("event").strip()
                    payload = match.group("payload").strip()
                    if payload:
                        try:
                            # Our logs usually end with a Python dict literal
                            meta = ast.literal_eval(payload)
                            if isinstance(meta, dict):
                                entry["meta"] = meta
                        except Exception:
                            pass
                log_entries.append(entry)
    except Exception:
        log_entries = []

    # Apply filters
    for entry in log_entries:
        # Search filter - check if search query exists in any field
        if search_query:
            searchable_text = ""
            if entry.get("event"):
                searchable_text += entry["event"].lower() + " "
            if entry.get("level"):
                searchable_text += entry["level"].lower() + " "
            if entry.get("raw"):
                searchable_text += entry["raw"].lower() + " "
            if entry.get("meta"):
                for key, value in entry["meta"].items():
                    if value:
                        searchable_text += str(value).lower() + " "
            
            if search_query not in searchable_text:
                continue

        # Date filters
        if date_from or date_to:
            try:
                # Parse timestamp from log entry
                timestamp_str = entry.get("timestamp", "")
                if timestamp_str:
                    # Handle different timestamp formats
                    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S,%f"]:
                        try:
                            entry_date = datetime.strptime(timestamp_str.split()[0] + " " + timestamp_str.split()[1], fmt)
                            break
                        except (ValueError, IndexError):
                            continue
                    else:
                        # If parsing fails, skip date filtering for this entry
                        entry_date = None
                    
                    if entry_date:
                        if date_from:
                            try:
                                from_date = datetime.strptime(date_from, "%Y-%m-%d")
                                if entry_date.date() < from_date.date():
                                    continue
                            except ValueError:
                                pass
                        
                        if date_to:
                            try:
                                to_date = datetime.strptime(date_to, "%Y-%m-%d")
                                if entry_date.date() > to_date.date():
                                    continue
                            except ValueError:
                                pass
            except Exception:
                pass

        filtered_entries.append(entry)

    # Limit displayed results to 500 after filtering
    filtered_entries = filtered_entries[:500]

    return render_template(
        "logs.html",
        active_page="logs",
        log_entries=filtered_entries,
        total_log_lines=total_lines,
        filters={
            "search": search_query,
            "date_from": date_from,
            "date_to": date_to
        }
    )


def _can_manage_user(target_role):
    """True if the current session user can manage a user with target_role."""
    current = session.get("user_role")
    if current == "super_admin":
        return True
    if current == "admin":
        return target_role == "end_user"
    return False


def _can_set_role(new_role):
    """True if the current session user can assign new_role to someone."""
    current = session.get("user_role")
    if current == "super_admin":
        return new_role in ROLES
    if current == "admin":
        return new_role == "end_user"
    return False


@app.route("/users")
@login_required
@role_required("super_admin", "admin")
def users():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT idusers AS id, email, first_name, last_name, role, is_active
            FROM users
            ORDER BY role <> 'super_admin', role <> 'admin', last_name, first_name
            """
        )
        all_users = cursor.fetchall()
    finally:
        cursor.close()
        db.close()

    for u in all_users:
        u["is_active"] = _is_active(u.get("is_active"))

    current_role = session.get("user_role")
    if current_role == "admin":
        all_users = [u for u in all_users if u.get("role") == "end_user"]

    return render_template(
        "user.html",
        active_page="users",
        users=all_users,
        roles=ROLES,
    )


@app.route("/users/add", methods=["GET", "POST"])
@login_required
@role_required("super_admin", "admin")
def add_user():
    error = None
    if request.method == "POST":
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""
        role = (request.form.get("role") or "end_user").strip().lower()
        if role not in ROLES:
            role = "end_user"

        if not _can_set_role(role):
            error = "You cannot assign that role."
        elif not first_name or not last_name or not email or not password or not confirm_password:
            error = "Please fill in all required fields."
        elif password != confirm_password:
            error = "Passwords do not match."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            db = get_db_connection()
            cursor = db.cursor()
            try:
                cursor.execute("SELECT idusers FROM users WHERE email = %s LIMIT 1", (email,))
                if cursor.fetchone():
                    error = "An account with that email already exists."
                else:
                    from werkzeug.security import generate_password_hash
                    password_hash = generate_password_hash(password)
                    cursor.execute(
                        """
                        INSERT INTO users (email, password_hash, first_name, last_name, role, is_active)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (email, password_hash, first_name, last_name, role, 1),
                    )
                    db.commit()
                    log_event(
                        "user_created",
                        created_email=email,
                        created_role=role,
                    )
                    flash("User created successfully.", "success")
                    return redirect(url_for("users"))
            finally:
                cursor.close()
                db.close()

    allowed_roles = [r for r in ROLES if _can_set_role(r)]
    return render_template(
        "add_user.html",
        active_page="users",
        error=error,
        roles=allowed_roles,
    )


@app.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("super_admin", "admin")
def edit_user(user_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT idusers AS id, email, first_name, last_name, role, is_active FROM users WHERE idusers = %s LIMIT 1",
            (user_id,),
        )
        user = cursor.fetchone()
    finally:
        cursor.close()
        db.close()

    if not user or not _can_manage_user(user.get("role")):
        flash("User not found or you cannot edit this user.", "danger")
        return redirect(url_for("users"))

    user["is_active"] = _is_active(user.get("is_active"))

    error = None
    if request.method == "POST":
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        role = (request.form.get("role") or user.get("role") or "end_user").strip().lower()
        if role not in ROLES:
            role = user.get("role") or "end_user"
        is_active = request.form.get("is_active") == "1"
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not _can_set_role(role):
            error = "You cannot assign that role."
        elif not first_name or not last_name:
            error = "First name and last name are required."
        elif new_password and new_password != confirm_password:
            error = "New passwords do not match."
        elif new_password and len(new_password) < 6:
            error = "Password must be at least 6 characters."
        elif new_password and session.get("user_role") == "admin" and user.get("role") in ("admin", "super_admin"):
            error = "Admins cannot change passwords of other admins or super admins."
        else:
            from werkzeug.security import generate_password_hash
            db = get_db_connection()
            cursor = db.cursor()
            try:
                if new_password:
                    password_hash = generate_password_hash(new_password)
                    cursor.execute(
                        """
                        UPDATE users SET first_name = %s, last_name = %s, role = %s, is_active = %s, password_hash = %s
                        WHERE idusers = %s
                        """,
                        (first_name, last_name, role, 1 if is_active else 0, password_hash, user_id),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE users SET first_name = %s, last_name = %s, role = %s, is_active = %s
                        WHERE idusers = %s
                        """,
                        (first_name, last_name, role, 1 if is_active else 0, user_id),
                    )
                db.commit()
                log_event(
                    "user_updated",
                    target_user_id=user_id,
                    new_role=role,
                    is_active=is_active,
                )
                flash("User updated successfully.", "success")
                return redirect(url_for("users"))
            finally:
                cursor.close()
                db.close()

    allowed_roles = [r for r in ROLES if _can_set_role(r)]
    return render_template(
        "edit_user.html",
        active_page="users",
        user=user,
        error=error,
        roles=allowed_roles,
    )


@app.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@role_required("super_admin", "admin")
def delete_user(user_id):
    if user_id == session.get("user_id"):
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for("users"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT idusers AS id, role FROM users WHERE idusers = %s LIMIT 1",
            (user_id,),
        )
        user = cursor.fetchone()
    finally:
        cursor.close()
        db.close()

    if not user or not _can_manage_user(user.get("role")):
        flash("User not found or you cannot delete this user.", "danger")
        return redirect(url_for("users"))

    # Prevent removing the last super_admin
    if user.get("role") == "super_admin":
        db = get_db_connection()
        cursor = db.cursor()
        try:
            cursor.execute("SELECT COUNT(*) AS n FROM users WHERE role = 'super_admin'")
            row = cursor.fetchone()
            n = row[0] if row else 0
            if n <= 1:
                flash("Cannot delete the last super admin.", "danger")
                return redirect(url_for("users"))
        finally:
            cursor.close()
            db.close()

    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE idusers = %s", (user_id,))
        db.commit()
    finally:
        cursor.close()
        db.close()
    log_event(
        "user_deleted",
        target_user_id=user_id,
        target_role=user.get("role") if user else None,
    )
    flash("User deleted.", "success")
    return redirect(url_for("users"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT idusers AS id, email, first_name, last_name, role, is_active FROM users WHERE idusers = %s LIMIT 1",
            (session.get("user_id"),),
        )
        user = cursor.fetchone()
    finally:
        cursor.close()
        db.close()

    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("dashboard"))

    user["is_active"] = _is_active(user.get("is_active"))

    error = None
    if request.method == "POST":
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        current_password = request.form.get("current_password") or ""
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not first_name or not last_name:
            error = "First name and last name are required."
        elif new_password and not current_password:
            error = "Current password is required to set a new password."
        elif new_password and new_password != confirm_password:
            error = "New passwords do not match."
        elif new_password and len(new_password) < 6:
            error = "Password must be at least 6 characters."
        else:
            from werkzeug.security import generate_password_hash, check_password_hash
            db = get_db_connection()
            cursor = db.cursor()
            try:
                # Verify current password if trying to change password
                if new_password:
                    cursor.execute("SELECT password_hash FROM users WHERE idusers = %s", (session.get("user_id"),))
                    result = cursor.fetchone()
                    if not result or not check_password_hash(result[0], current_password):
                        error = "Current password is incorrect."
                    else:
                        password_hash = generate_password_hash(new_password)
                        cursor.execute(
                            """
                            UPDATE users SET first_name = %s, last_name = %s, password_hash = %s
                            WHERE idusers = %s
                            """,
                            (first_name, last_name, password_hash, session.get("user_id")),
                        )
                else:
                    # Only update name fields
                    cursor.execute(
                        """
                        UPDATE users SET first_name = %s, last_name = %s
                        WHERE idusers = %s
                        """,
                        (first_name, last_name, session.get("user_id")),
                    )
                db.commit()
                log_event(
                    "profile_updated",
                    updated_fields=["names"] if not new_password else ["names", "password"],
                )
                flash("Profile updated successfully.", "success")
                return redirect(url_for("profile"))
            finally:
                cursor.close()
                db.close()

    return render_template(
        "profile.html",
        active_page="profile",
        user=user,
        error=error,
    )


@app.route("/settings")
@login_required
def settings():
    return render_template("settings.html", active_page="settings")


@app.route("/add-ticket", methods=["GET", "POST"])
@login_required
def add_ticket():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        contact_number = request.form.get("contact_number", "").strip()
        email = request.form.get("email", "").strip()
        subject = request.form.get("subject", "").strip()
        reported_concern = request.form.get("reported_concern", "").strip()
        assigned_to = request.form.get("assigned_to", "").strip()
        job_order = request.form.get("job_order", "").strip()
        status = (request.form.get("status", "pending") or "pending").strip().lower()

        if status not in {"pending", "ongoing", "completed", "complete", "in progress", "in_progress"}:
            status = "pending"

        # Require the core fields that map to your schema
        # Name, subject, and concern are always required; for contact, allow either
        # a phone number or an email address (at least one must be provided).
        if name and subject and reported_concern and (contact_number or email):
            db = get_db_connection()
            cursor = db.cursor()
            try:
                cursor.execute("SHOW COLUMNS FROM entries")
                cols = {row[0] for row in cursor.fetchall()}

                jo_col = "job_order" if "job_order" in cols else ("remedy" if "remedy" in cols else None)
                if jo_col:
                    # Always auto-generate JO per new ticket (can still be edited later).
                    job_order = compute_next_job_order(cursor, jo_col)

                insert_cols = []
                insert_sql_values = []
                insert_params = []

                def add_param_col(col_name, value):
                    insert_cols.append(col_name)
                    insert_sql_values.append("%s")
                    insert_params.append(value)

                def add_sql_col(col_name, sql_expr):
                    insert_cols.append(col_name)
                    insert_sql_values.append(sql_expr)

                if "store_name" in cols:
                    add_param_col("store_name", name)
                if "contact_number" in cols:
                    add_param_col("contact_number", contact_number or None)
                if "email" in cols:
                    add_param_col("email", email or None)
                if "Email" in cols:
                    add_param_col("Email", email or None)
                if "subject" in cols:
                    add_param_col("subject", subject)
                # Prefer the new job_order column; fall back to legacy remedy if present
                if "job_order" in cols:
                    add_param_col("job_order", job_order or None)
                elif "remedy" in cols:
                    add_param_col("remedy", job_order or None)

                concern_col = next(
                    (c for c in ("reported_concern", "reportedConcern", "concern", "details", "description") if c in cols),
                    None,
                )
                if concern_col:
                    add_param_col(concern_col, reported_concern)

                if "assigned_it" in cols:
                    # Keep legacy schema working: if there's no separate concern column,
                    # store a structured multi-line value that the UI can parse.
                    if not concern_col:
                        lines = []
                        if email:
                            lines.append(f"Email: {email}")
                        if contact_number:
                            lines.append(f"Contact: {contact_number}")
                        lines.append(f"Reported concern: {reported_concern}")
                        if assigned_to:
                            lines.append(f"Assigned to: {assigned_to}")
                        add_param_col("assigned_it", "\n".join(lines))
                    else:
                        add_param_col("assigned_it", assigned_to or None)

                if "status" in cols:
                    normalized_status = "completed" if status in {"complete", "completed"} else status
                    add_param_col("status", normalized_status)

                if "date" in cols:
                    add_sql_col("date", "NOW()")
                elif "created_at" in cols:
                    add_sql_col("created_at", "NOW()")

                if not insert_cols:
                    raise RuntimeError("No matching columns found for insert into entries.")

                sql = f"INSERT INTO entries ({', '.join(insert_cols)}) VALUES ({', '.join(insert_sql_values)})"
                cursor.execute(sql, insert_params)
                db.commit()
                ticket_pk = cursor.lastrowid
                log_event(
                    "ticket_created",
                    ticket_pk=ticket_pk,
                    store_name=name,
                    subject=subject,
                    job_order=job_order,
                    assigned_to=assigned_to,
                    status=status,
                    contact_number=contact_number,
                    email=email,
                )
            finally:
                cursor.close()
                db.close()
            return redirect(url_for("home", _anchor="tickets"))
    # GET (or invalid POST): pre-fill the next JO for the form.
    next_jo = None
    try:
        db = get_db_connection()
        cursor = db.cursor()
        try:
            cursor.execute("SHOW COLUMNS FROM entries")
            cols = {row[0] for row in cursor.fetchall()}
            jo_col = "job_order" if "job_order" in cols else ("remedy" if "remedy" in cols else None)
            if jo_col:
                next_jo = compute_next_job_order(cursor, jo_col)
        finally:
            cursor.close()
            db.close()
    except Exception:
        next_jo = None

    return render_template("add_ticket.html", active_page="add_ticket", next_jo=next_jo)


@app.route("/tickets/<int:ticket_id>/edit", methods=["GET", "POST"])
@login_required
def edit_ticket(ticket_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        pk_col, cols = get_entries_pk_column(db)
        if not pk_col:
            raise RuntimeError("No known primary key column on entries table.")

        if request.method == "POST":
            cursor.execute(f"SELECT * FROM entries WHERE {pk_col} = %s", (ticket_id,))
            existing = cursor.fetchone() or {}
            name = request.form.get("name", "").strip()
            contact_number = request.form.get("contact_number", "").strip()
            email = request.form.get("email", "").strip()
            subject = request.form.get("subject", "").strip()
            reported_concern = request.form.get("reported_concern", "").strip()
            assigned_to = request.form.get("assigned_to", "").strip()
            job_order = request.form.get("job_order", "").strip()
            status = (request.form.get("status", "pending") or "pending").strip().lower()

            if status not in {"pending", "ongoing", "completed", "complete", "in progress", "in_progress"}:
                status = "pending"

            set_clauses = []
            params = []

            def add_update_param(col_name, value):
                set_clauses.append(f"{col_name} = %s")
                params.append(value)

            concern_col = next(
                (c for c in ("reported_concern", "reportedConcern", "concern", "details", "description") if c in cols),
                None,
            )

            # Store / update core fields
            if "store_name" in cols:
                add_update_param("store_name", name or None)
            if "Name" in cols:
                add_update_param("Name", name or None)
            if "contact_number" in cols:
                add_update_param("contact_number", contact_number or None)
            if "email" in cols:
                add_update_param("email", email or None)
            if "Email" in cols:
                add_update_param("Email", email or None)
            if "subject" in cols:
                add_update_param("subject", subject or None)
            # Prefer the new job_order column; fall back to legacy remedy if present
            if "job_order" in cols:
                add_update_param("job_order", job_order or None)
            elif "remedy" in cols:
                add_update_param("remedy", job_order or None)
            if "Concern" in cols and not concern_col:
                add_update_param("Concern", reported_concern or None)

            if concern_col:
                add_update_param(concern_col, reported_concern or None)

            if "assigned_it" in cols:
                if not concern_col:
                    # Legacy schema: pack contact/concern/assignee into a single text field
                    lines = []
                    if contact_number:
                        lines.append(f"Contact: {contact_number}")
                    lines.append(f"Reported concern: {reported_concern}")
                    if assigned_to:
                        lines.append(f"Assigned to: {assigned_to}")
                    add_update_param("assigned_it", "\n".join(lines))
                else:
                    add_update_param("assigned_it", assigned_to or None)

            if "status" in cols:
                normalized_status = "completed" if status in {"complete", "completed"} else status
                add_update_param("status", normalized_status)

            if not set_clauses:
                raise RuntimeError("No matching columns found for update on entries.")

            sql = f"UPDATE entries SET {', '.join(set_clauses)} WHERE {pk_col} = %s"
            params.append(ticket_id)
            cursor.execute(sql, params)
            db.commit()

            old_name = (existing.get("store_name") or existing.get("Name")) if existing else None
            old_subject = (existing.get("subject") or existing.get("Concern") or existing.get("concern")) if existing else None
            old_job_order = (existing.get("job_order") or existing.get("remedy")) if existing else None
            old_contact = existing.get("contact_number") if existing else None
            old_email = (existing.get("email") or existing.get("Email")) if existing else None
            old_status_raw = (existing.get("status") or existing.get("Status") or "pending").lower() if existing else "pending"
            if old_status_raw in ("complete", "completed"):
                old_status_val = "completed"
            elif old_status_raw in ("ongoing", "in progress", "in_progress"):
                old_status_val = "ongoing"
            else:
                old_status_val = "pending"

            log_event(
                "ticket_updated",
                ticket_id=ticket_id,
                old_store_name=old_name,
                new_store_name=name or None,
                old_subject=old_subject,
                new_subject=subject or None,
                old_job_order=old_job_order,
                new_job_order=job_order or None,
                old_status=old_status_val,
                new_status=status,
                old_contact_number=old_contact,
                new_contact_number=contact_number or None,
                old_email=old_email,
                new_email=email or None,
                old_assigned_it=existing.get("assigned_it") if existing else None,
                new_assigned_to=assigned_to or None,
            )
            return redirect(url_for("home", _anchor="tickets"))

        # GET: load existing ticket and show form
        cursor.execute(f"SELECT * FROM entries WHERE {pk_col} = %s", (ticket_id,))
        entry = cursor.fetchone()
        if not entry:
            return redirect(url_for("home", _anchor="tickets"))

        store_name = entry.get("store_name") or entry.get("Name") or ""
        contact_number = entry.get("contact_number") or ""
        email = entry.get("email") or entry.get("Email") or ""
        subject = entry.get("subject") or entry.get("Concern") or entry.get("concern") or ""
        job_order = entry.get("job_order") or entry.get("remedy") or ""

        status_raw = (entry.get("status") or entry.get("Status") or "pending").lower()
        if status_raw in ("complete", "completed"):
            status_val = "completed"
        elif status_raw in ("ongoing", "in progress", "in_progress"):
            status_val = "ongoing"
        else:
            status_val = "pending"

        # Derive reported concern
        reported_concern = ""
        for c in ("reported_concern", "reportedConcern", "concern", "details", "description"):
            if entry.get(c):
                reported_concern = entry[c]
                break
        if not reported_concern:
            raw_assigned_it = entry.get("assigned_it") or ""
            for line in raw_assigned_it.split("\n"):
                l = line.strip()
                if l.lower().startswith("reported concern:"):
                    reported_concern = l.split(":", 1)[1].strip()
                    break

        # Derive assigned_to
        assigned_to = ""
        raw_assigned_it = entry.get("assigned_it") or ""
        if raw_assigned_it:
            parsed_assignee = None
            for line in raw_assigned_it.split("\n"):
                l = line.strip()
                if l.lower().startswith("assigned to:"):
                    parsed_assignee = l.split(":", 1)[1].strip()
                    break
            assigned_to = parsed_assignee or raw_assigned_it

        return render_template(
            "edit_ticket.html",
            active_page="edit_ticket",
            ticket_id=ticket_id,
            store_name=store_name,
            contact_number=contact_number,
            email=email,
            subject=subject,
            job_order=job_order,
            assigned_to=assigned_to,
            reported_concern=reported_concern,
            status=status_val,
        )
    finally:
        cursor.close()
        db.close()


@app.route("/tickets/<int:ticket_id>/delete", methods=["POST"])
@login_required
def delete_ticket(ticket_id):
    db = get_db_connection()
    cursor = db.cursor()
    entry = None
    try:
        pk_col, _ = get_entries_pk_column(db)
        if not pk_col:
            raise RuntimeError("No known primary key column on entries table.")

        cursor.execute(f"SELECT * FROM entries WHERE {pk_col} = %s", (ticket_id,))
        entry = cursor.fetchone()
        cursor.execute(f"DELETE FROM entries WHERE {pk_col} = %s", (ticket_id,))
        db.commit()
    finally:
        cursor.close()
        db.close()
    if entry:
        del_name = entry.get("store_name") or entry.get("Name")
        del_subject = entry.get("subject") or entry.get("Concern") or entry.get("concern")
        del_job_order = entry.get("job_order") or entry.get("remedy")
        del_status = entry.get("status") or entry.get("Status")
        del_contact = entry.get("contact_number")
        del_email = entry.get("email") or entry.get("Email")
    else:
        del_name = del_subject = del_job_order = del_status = del_contact = del_email = None

    log_event(
        "ticket_deleted",
        ticket_id=ticket_id,
        store_name=del_name,
        subject=del_subject,
        job_order=del_job_order,
        status=del_status,
        contact_number=del_contact,
        email=del_email,
    )
    return redirect(url_for("home", _anchor="tickets"))


@app.route("/tickets/<int:ticket_id>/job-order")
@login_required
def job_order_print(ticket_id):
    """Serve a print-ready job order page for the given ticket."""
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        pk_col, cols = get_entries_pk_column(db)
        if not pk_col:
            raise RuntimeError("No known primary key column on entries table.")
        cursor.execute(f"SELECT * FROM entries WHERE {pk_col} = %s", (ticket_id,))
        entry = cursor.fetchone()
        if not entry:
            return redirect(url_for("home", _anchor="tickets"))

        store_name = entry.get("store_name") or entry.get("Name") or ""
        contact_number = entry.get("contact_number") or ""
        email = entry.get("email") or entry.get("Email") or ""
        subject = entry.get("subject") or entry.get("Concern") or entry.get("concern") or ""
        job_order = entry.get("job_order") or entry.get("remedy") or ""
        ticket_no = entry.get("ticket_no") or entry.get("id") or ticket_id
        date_val = entry.get("date") or entry.get("created_at") or ""

        status_raw = (entry.get("status") or entry.get("Status") or "pending").lower()
        if status_raw in ("complete", "completed"):
            status_label = "Complete"
        elif status_raw in ("ongoing", "in progress", "in_progress"):
            status_label = "Ongoing"
        else:
            status_label = "Pending"

        reported_concern = ""
        for c in ("reported_concern", "reportedConcern", "concern", "details", "description"):
            if entry.get(c):
                reported_concern = entry[c]
                break
        if not reported_concern:
            raw_assigned_it = entry.get("assigned_it") or ""
            for line in raw_assigned_it.split("\n"):
                l = line.strip()
                if l.lower().startswith("reported concern:"):
                    reported_concern = l.split(":", 1)[1].strip()
                    break

        assigned_to = ""
        raw_assigned_it = entry.get("assigned_it") or ""
        if raw_assigned_it:
            for line in raw_assigned_it.split("\n"):
                l = line.strip()
                if l.lower().startswith("assigned to:"):
                    assigned_to = l.split(":", 1)[1].strip()
                    break
            if not assigned_to:
                assigned_to = raw_assigned_it
        if not assigned_to:
            assigned_to = email or "—"

        vertical = request.args.get("vertical", "").lower() in ("1", "true", "yes")

        return render_template(
            "job_order_print.html",
            ticket_id=ticket_no,
            vertical=vertical,
            store_name=store_name,
            contact_number=contact_number,
            email=email,
            subject=subject,
            job_order=job_order,
            assigned_to=assigned_to,
            reported_concern=reported_concern,
            status_label=status_label,
            date_val=date_val,
        )
    finally:
        cursor.close()
        db.close()


@app.route("/placeholder1")
@login_required
def placeholder1():
    return render_template("placeholder1.html", active_page="placeholder1")


@app.route("/placeholder2")
@login_required
def placeholder2():
    return render_template("placeholder2.html", active_page="placeholder2")


@app.route("/placeholder3")
@login_required
def placeholder3():
    return render_template("placeholder3.html", active_page="placeholder3")


@app.context_processor
def ticket_counts():
    """Provide ticket status counts for sidebar on all pages."""
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Work with either `status` or `Status` column, if present
        cursor.execute("SHOW COLUMNS FROM entries")
        cols = {row["Field"] for row in cursor.fetchall()}

        status_col = None
        if "status" in cols:
            status_col = "status"
        elif "Status" in cols:
            status_col = "Status"

        if status_col:
            cursor.execute(f"SELECT {status_col} AS status FROM entries")
            rows = cursor.fetchall()

            cursor.close()
            db.close()

            complete = pending = ongoing = 0
            for r in rows:
                s = (r.get("status") or "pending").lower()
                if s in ("complete", "completed"):
                    complete += 1
                elif s in ("ongoing", "in progress", "in_progress"):
                    ongoing += 1
                else:
                    pending += 1
            return dict(ticket_complete=complete, ticket_pending=pending, ticket_ongoing=ongoing, ticket_total=complete + pending + ongoing)
        else:
            # Fallback: no explicit status column; treat all tickets as pending
            cursor.execute("SELECT COUNT(*) AS total FROM entries")
            row = cursor.fetchone() or {}
            cursor.close()
            db.close()
            total = row.get("total", 0)
            return dict(ticket_complete=0, ticket_pending=total, ticket_ongoing=0, ticket_total=total)
    except Exception:
        return dict(ticket_complete=0, ticket_pending=0, ticket_ongoing=0, ticket_total=0)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not email or not password:
            error = "Please enter both email and password."
        else:
            db = get_db_connection()
            cursor = db.cursor(dictionary=True)
            try:
                cursor.execute(
                    """
                    SELECT idusers AS id, email, password_hash, first_name, last_name, role, is_active
                    FROM users
                    WHERE email = %s
                    LIMIT 1
                    """,
                    (email,),
                )
                user = cursor.fetchone()
            finally:
                cursor.close()
                db.close()

            from werkzeug.security import check_password_hash  # local import to avoid circulars if any

            if not user or not _is_active(user.get("is_active")):
                error = "Invalid email or password."
                log_event("login_failed", email=email)
            elif not check_password_hash(user["password_hash"], password):
                error = "Invalid email or password."
                log_event("login_failed", email=email)
            else:
                session.clear()
                session["user_id"] = user["id"]
                session["user_email"] = user["email"]
                full_name_parts = [
                    part
                    for part in [
                        user.get("first_name") or "",
                        user.get("last_name") or "",
                    ]
                    if part
                ]
                session["user_name"] = " ".join(full_name_parts) or user["email"]
                session["user_role"] = user.get("role")

                log_event("login_success")
                flash("Signed in successfully.", "success")
                next_url = request.args.get("next") or url_for("dashboard")
                return redirect(next_url)

    return render_template("login.html", error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None

    if request.method == "POST":
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not first_name or not last_name or not email or not password or not confirm_password:
            error = "Please fill in all fields."
        elif password != confirm_password:
            error = "Passwords do not match."
        else:
            db = get_db_connection()
            cursor = db.cursor()
            try:
                cursor.execute("SELECT idusers FROM users WHERE email = %s LIMIT 1", (email,))
                existing = cursor.fetchone()

                if existing:
                    error = "An account with that email already exists."
                else:
                    from werkzeug.security import generate_password_hash  # local import to avoid circulars if any

                    password_hash = generate_password_hash(password)
                    cursor.execute(
                        """
                        INSERT INTO users (email, password_hash, first_name, last_name, role, is_active)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (email, password_hash, first_name, last_name, "end_user", 1),
                    )
                    db.commit()
            finally:
                cursor.close()
                db.close()

            if not error:
                flash("Your account has been created. You can now sign in.", "success")
                return redirect(url_for("login"))

    return render_template("register.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    log_event("logout")
    flash("You have been signed out.", "info")
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)