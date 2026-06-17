import os
import sqlite3
import secrets
import csv
import io
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, abort, Response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_urlsafe(32)
app.config[
    "UPLOAD_FOLDER"
] = UPLOAD_FOLDER
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["OFFERING_UPI_ID"] = os.environ.get("OFFERING_UPI_ID", "samkanagaraj777@okhdfcbank")

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    if os.path.exists(DB_PATH):
        return
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            full_name TEXT NOT NULL,
            location TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            bill_number TEXT NOT NULL,
            created_at TEXT NOT NULL,
            department TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            file_name TEXT,
            status TEXT NOT NULL,
            remarks TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.execute("""
        CREATE TABLE offerings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            offering_date TEXT NOT NULL,
            amount REAL NOT NULL,
            fund_type TEXT NOT NULL DEFAULT 'Church Building Fund',
            description TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.execute(
        "INSERT INTO users (username, password, role, full_name, location) VALUES (?, ?, ?, ?, ?)",
        ("admin", generate_password_hash("admin123"), "ADMIN", "Church Administrator", "Head Office"),
    )
    conn.execute(
        "INSERT INTO users (username, password, role, full_name, location) VALUES (?, ?, ?, ?, ?)",
        ("user", generate_password_hash("user123"), "USER", "Grace Member", "Main Branch"),
    )
    conn.commit()
    conn.close()


init_db()


def ensure_user_location_column():
    conn = get_db_connection()
    columns = [row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "location" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN location TEXT DEFAULT ''")
        conn.commit()
    conn.close()


ensure_user_location_column()


def hash_password(password):
    return generate_password_hash(password)


def verify_password(stored_password, provided_password):
    if ":" in stored_password:
        try:
            return check_password_hash(stored_password, provided_password)
        except ValueError:
            pass
    return stored_password == provided_password


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(view):
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    wrapped.__name__ = view.__name__
    return wrapped


def admin_required(view):
    def wrapped(*args, **kwargs):
        if session.get("role") != "ADMIN":
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    wrapped.__name__ = view.__name__
    return wrapped


@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if user and verify_password(user["password"], password):
            if ":" not in user["password"]:
                conn.execute(
                    "UPDATE users SET password = ? WHERE id = ?",
                    (generate_password_hash(password), user["id"]),
                )
                conn.commit()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]
            conn.close()
            return redirect(url_for("admin_dashboard" if user["role"] == "ADMIN" else "dashboard"))
        conn.close()
        flash("Invalid credentials. Please try again.", "error")
    return render_template("index.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    if session.get("role") == "ADMIN":
        return redirect(url_for("admin_dashboard"))
    return render_template("user.html")


@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_pending = conn.execute("SELECT COUNT(*) FROM bills WHERE status = 'Pending'").fetchone()[0]
    total_approved = conn.execute("SELECT COUNT(*) FROM bills WHERE status = 'Approved'").fetchone()[0]
    total_rejected = conn.execute("SELECT COUNT(*) FROM bills WHERE status = 'Rejected'").fetchone()[0]
    total_offerings_val = conn.execute("SELECT SUM(amount) FROM offerings").fetchone()[0]
    total_offerings = total_offerings_val if total_offerings_val else 0
    # Sunday entries summary
    try:
        total_sunday_entries = conn.execute("SELECT COUNT(*) FROM sunday_entries").fetchone()[0]
    except Exception:
        total_sunday_entries = 0
    latest_sunday = None
    try:
        latest_sunday = conn.execute("SELECT * FROM sunday_entries ORDER BY created_at DESC LIMIT 1").fetchone()
    except Exception:
        latest_sunday = None
    conn.close()
    return render_template(
        "admin.html",
        total_users=total_users,
        total_pending=total_pending,
        total_approved=total_approved,
        total_rejected=total_rejected,
        total_offerings=total_offerings,
        total_sunday_entries=total_sunday_entries,
        latest_sunday=latest_sunday,
    )


@app.route("/admin/pending")
@login_required
@admin_required
def admin_pending():
    conn = get_db_connection()
    pending = conn.execute("SELECT bills.*, COALESCE(users.full_name, 'Deleted User') AS full_name FROM bills LEFT JOIN users ON bills.user_id = users.id WHERE status = 'Pending' ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("admin_pending.html", pending=pending)


@app.route("/admin/approved")
@login_required
@admin_required
def admin_approved():
    conn = get_db_connection()
    approved = conn.execute("SELECT bills.*, COALESCE(users.full_name, 'Deleted User') AS full_name FROM bills LEFT JOIN users ON bills.user_id = users.id WHERE status = 'Approved' ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("admin_approved.html", approved=approved)


@app.route("/admin/rejected")
@login_required
@admin_required
def admin_rejected():
    conn = get_db_connection()
    rejected = conn.execute("SELECT bills.*, COALESCE(users.full_name, 'Deleted User') AS full_name FROM bills LEFT JOIN users ON bills.user_id = users.id WHERE status = 'Rejected' ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("admin_rejected.html", rejected=rejected)


@app.route("/admin/offerings")
@login_required
@admin_required
def admin_offerings():
    conn = get_db_connection()
    offerings = conn.execute("SELECT offerings.*, COALESCE(users.full_name, 'Deleted User') AS full_name FROM offerings LEFT JOIN users ON offerings.user_id = users.id ORDER BY offering_date DESC").fetchall()
    conn.close()
    return render_template("admin_offerings.html", offerings=offerings)


@app.route("/bill-entry", methods=["GET", "POST"])
@login_required
def bill_entry():
    conn = get_db_connection()
    if request.method == "POST":
        bill_number = request.form["bill_number"].strip()
        bill_date = request.form["bill_date"].strip()
        department = request.form["department"].strip()
        amount = float(request.form["amount"] or 0)
        description = request.form["description"].strip()
        file_name = None
        file = request.files.get("bill_copy")
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            file_name = filename
        conn.execute(
            "INSERT INTO bills (user_id, bill_number, created_at, department, amount, description, file_name, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session["user_id"],
                bill_number,
                bill_date,
                department,
                amount,
                description,
                file_name,
                "Pending",
            ),
        )
        conn.commit()
        flash("Bill entry submitted successfully. Status is Pending Approval.", "success")
        return redirect(url_for("bill_entry"))
    bills = conn.execute("SELECT * FROM bills WHERE user_id = ? ORDER BY created_at DESC", (session["user_id"],)).fetchall()
    conn.close()
    return render_template("bill_entry.html", bills=bills)


@app.route("/offering-entry", methods=["GET", "POST"])
@login_required
def offering_entry():
    conn = get_db_connection()
    if request.method == "POST":
        offering_date = request.form["offering_date"].strip()
        amount = float(request.form["offering_amount"] or 0)
        fund_type = request.form["fund_type"].strip()
        description = request.form["offering_description"].strip()
        conn.execute(
            "INSERT INTO offerings (user_id, offering_date, amount, fund_type, description) VALUES (?, ?, ?, ?, ?)",
            (session["user_id"], offering_date, amount, fund_type, description),
        )
        conn.commit()
        flash("Offering entry submitted successfully.", "success")
        return redirect(url_for("offering_entry"))
        
    offerings = conn.execute("SELECT * FROM offerings WHERE user_id = ? ORDER BY offering_date DESC", (session["user_id"],)).fetchall()
    conn.close()

    # UPI QR image and UPI ID configuration (place a file at static/upi_qr.png to show QR)
    upi_qr_path = os.path.join(BASE_DIR, "static", "upi_qr.png")
    qr_exists = os.path.exists(upi_qr_path)
    upi_id = app.config.get("OFFERING_UPI_ID", "")

    return render_template("user_offering_entry.html", offerings=offerings, qr_exists=qr_exists, upi_id=upi_id)


@app.route("/admin/bill-action/<int:bill_id>", methods=["POST"])
@login_required
@admin_required
def bill_action(bill_id):
    action = request.form.get("action")
    remarks = request.form.get("remarks", "").strip()
    status = "Approved" if action == "approve" else "Rejected"
    conn = get_db_connection()
    conn.execute(
        "UPDATE bills SET status = ?, remarks = ? WHERE id = ?",
        (status, remarks, bill_id),
    )
    conn.commit()
    conn.close()
    flash(f"Bill {status} successfully.", "success")
    return redirect(url_for("admin_pending"))


@app.route("/manage-users", methods=["GET", "POST"])
@login_required
@admin_required
def manage_users():
    conn = get_db_connection()
    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        role = request.form["role"]
        location = request.form.get("location", "").strip()
        
        existing_user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if existing_user:
            flash("Username already exists. Please choose a different username.", "error")
        else:
            conn.execute(
                "INSERT INTO users (username, password, role, full_name, location) VALUES (?, ?, ?, ?, ?)",
                (username, hash_password(password), role, full_name, location),
            )
            conn.commit()
            flash("User created successfully.", "success")
        return redirect(url_for("manage_users"))
    users = conn.execute("SELECT * FROM users ORDER BY id ASC").fetchall()
    conn.close()
    return render_template("manage_users.html", users=users)


@app.route("/admin/delete-user/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    if user_id == session.get("user_id"):
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("manage_users"))
        
    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash("User removed successfully.", "success")
    return redirect(url_for("manage_users"))


@app.route("/delete-bill/<int:bill_id>", methods=["POST"])
@login_required
def delete_bill(bill_id):
    conn = get_db_connection()
    bill = conn.execute("SELECT * FROM bills WHERE id = ?", (bill_id,)).fetchone()
    if bill:
        if session.get("role") == "ADMIN" or bill["user_id"] == session.get("user_id"):
            conn.execute("DELETE FROM bills WHERE id = ?", (bill_id,))
            conn.commit()
            flash("Bill deleted successfully.", "success")
        else:
            flash("Unauthorized action.", "error")
    conn.close()
    return redirect(request.referrer or url_for('dashboard'))


@app.route("/delete-offering/<int:offering_id>", methods=["POST"])
@login_required
def delete_offering(offering_id):
    conn = get_db_connection()
    offering = conn.execute("SELECT * FROM offerings WHERE id = ?", (offering_id,)).fetchone()
    if offering:
        if session.get("role") == "ADMIN" or offering["user_id"] == session.get("user_id"):
            conn.execute("DELETE FROM offerings WHERE id = ?", (offering_id,))
            conn.commit()
            flash("Offering deleted successfully.", "success")
        else:
            flash("Unauthorized action.", "error")
    conn.close()
    return redirect(request.referrer or url_for('dashboard'))


@app.route("/delete-sunday-entry/<int:entry_id>", methods=["POST"])
@login_required
def delete_sunday_entry(entry_id):
    conn = get_db_connection()
    entry = conn.execute("SELECT * FROM sunday_entries WHERE id = ?", (entry_id,)).fetchone()
    if entry:
        if session.get("role") == "ADMIN" or entry["user_id"] == session.get("user_id"):
            conn.execute("DELETE FROM sunday_entries WHERE id = ?", (entry_id,))
            conn.commit()
            flash("Sunday class entry deleted successfully.", "success")
        else:
            flash("Unauthorized action.", "error")
    conn.close()
    return redirect(request.referrer or url_for('dashboard'))


@app.route("/admin/edit-user/<int:user_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    if not user:
        conn.close()
        flash("User not found.", "error")
        return redirect(url_for("manage_users"))

    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        username = request.form["username"].strip()
        password = request.form.get("password", "").strip()
        role = request.form["role"]
        location = request.form.get("location", "").strip()

        # Check if new username is taken by another user
        existing_user = conn.execute("SELECT * FROM users WHERE username = ? AND id != ?", (username, user_id)).fetchone()
        if existing_user:
            flash("Username already exists. Please choose a different username.", "error")
        else:
            if password:
                conn.execute(
                    "UPDATE users SET username = ?, password = ?, role = ?, full_name = ?, location = ? WHERE id = ?",
                    (username, hash_password(password), role, full_name, location, user_id),
                )
            else:
                conn.execute(
                    "UPDATE users SET username = ?, role = ?, full_name = ?, location = ? WHERE id = ?",
                    (username, role, full_name, location, user_id),
                )
            conn.commit()
            flash("User updated successfully.", "success")
            conn.close()
            return redirect(url_for("manage_users"))

    conn.close()
    return render_template("edit_user.html", user=user)


@app.before_request
def protect_against_csrf():
    if request.method == "POST":
        token = session.get("csrf_token")
        form_token = request.form.get("csrf_token")
        if not token or not form_token or not secrets.compare_digest(token, form_token):
            abort(400)


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers[
        "Content-Security-Policy"
    ] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self';"
    return response


@app.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    filename = secure_filename(filename)
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.context_processor
def inject_now():
    return {"now": datetime.now(), "csrf_token": lambda: session.setdefault("csrf_token", secrets.token_urlsafe(32))}


@app.route("/reports")
@login_required
def reports():
    conn = get_db_connection()
    sunday_entries = []
    offerings = []
    if session.get("role") == "ADMIN":
        bills = conn.execute("SELECT bills.*, COALESCE(users.full_name, 'Deleted User') AS full_name FROM bills LEFT JOIN users ON bills.user_id = users.id ORDER BY created_at DESC").fetchall()
    else:
        bills = conn.execute("SELECT * FROM bills WHERE user_id = ? ORDER BY created_at DESC", (session["user_id"],)).fetchall()
        sunday_entries = conn.execute(
            "SELECT * FROM sunday_entries WHERE user_id = ? ORDER BY created_at DESC",
            (session["user_id"],),
        ).fetchall()
        offerings = conn.execute(
            "SELECT * FROM offerings WHERE user_id = ? ORDER BY offering_date DESC",
            (session["user_id"],),
        ).fetchall()
    conn.close()
    # Compute counts for the summary
    try:
        bills_count = len(bills) if bills is not None else 0
    except Exception:
        bills_count = 0
    try:
        offerings_count = len(offerings) if offerings is not None else 0
    except Exception:
        offerings_count = 0
    try:
        sunday_count = len(sunday_entries) if sunday_entries is not None else 0
    except Exception:
        sunday_count = 0

    return render_template(
        "reports.html",
        bills=bills,
        sunday_entries=sunday_entries,
        offerings=offerings,
        bills_count=bills_count,
        offerings_count=offerings_count,
        sunday_count=sunday_count,
    )


@app.route("/sunday-class")
@login_required
def sunday_class():
    conn = get_db_connection()
    # Default: total students based on users table
    total_students = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'USER'").fetchone()[0]
    default_teacher = "Rev. Sam Kanagaraj"

    # Determine area_name from logged-in user's location
    area_name = ""
    user_id = session.get("user_id")
    if user_id:
        row = conn.execute("SELECT location FROM users WHERE id = ?", (user_id,)).fetchone()
        if row:
            try:
                area_name = row["location"]
            except Exception:
                area_name = row[0]

    # Try to fetch the latest sunday entry for this area (if area_name present), else latest overall
    entry = None
    if area_name:
        entry = conn.execute("SELECT * FROM sunday_entries WHERE area_name = ? ORDER BY created_at DESC LIMIT 1", (area_name,)).fetchone()
    if not entry:
        entry = conn.execute("SELECT * FROM sunday_entries ORDER BY created_at DESC LIMIT 1").fetchone()

    # If an entry exists, use its values to populate the cards
    teacher_name = default_teacher
    if entry:
        try:
            teacher_name = entry["teacher_name"] or default_teacher
            total_students = int(entry["student_count"]) if entry["student_count"] is not None else total_students
            area_name = entry["area_name"] or area_name
        except Exception:
            # fallback to index-based access
            try:
                teacher_name = entry[4] if len(entry) > 4 else default_teacher
            except Exception:
                teacher_name = default_teacher

    conn.close()
    return render_template("sunday_class.html", total_students=total_students, teacher_name=teacher_name, area_name=area_name)


@app.route("/sunday-class-entry", methods=["POST"])
@login_required
def sunday_class_entry():
    conn = get_db_connection()
    area_name = request.form.get("area_name", "").strip()
    teacher_name = request.form.get("teacher_name", "").strip()
    try:
        student_count = int(request.form.get("student_count") or 0)
    except ValueError:
        student_count = 0
    notes = request.form.get("notes", "").strip()
    file_name = None
    file = request.files.get("attachment")
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        file_name = filename

    conn.execute(
        "INSERT INTO sunday_entries (user_id, area_name, teacher_name, student_count, notes, file_name, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (session.get("user_id"), area_name, teacher_name, student_count, notes, file_name, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    flash("Sunday class entry submitted successfully.", "success")
    return redirect(url_for("sunday_class"))


@app.route("/admin/sunday-reports")
@login_required
@admin_required
def admin_sunday_reports():
    conn = get_db_connection()
    entries = conn.execute("SELECT sunday_entries.*, COALESCE(users.full_name, 'Deleted User') AS full_name FROM sunday_entries LEFT JOIN users ON sunday_entries.user_id = users.id ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("admin_sunday_reports.html", entries=entries)


@app.route("/reports/export")
@login_required
def export_reports():
    conn = get_db_connection()
    if session.get("role") == "ADMIN":
        bills = conn.execute("SELECT bills.*, COALESCE(users.full_name, 'Deleted User') AS full_name FROM bills LEFT JOIN users ON bills.user_id = users.id ORDER BY created_at DESC").fetchall()
        offerings = conn.execute("SELECT offerings.*, COALESCE(users.full_name, 'Deleted User') AS full_name FROM offerings LEFT JOIN users ON offerings.user_id = users.id ORDER BY offering_date DESC").fetchall()
        sunday_entries = conn.execute("SELECT sunday_entries.*, COALESCE(users.full_name, 'Deleted User') AS full_name FROM sunday_entries LEFT JOIN users ON sunday_entries.user_id = users.id ORDER BY created_at DESC").fetchall()
    else:
        user_id = session.get("user_id")
        bills = conn.execute("SELECT * FROM bills WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
        offerings = conn.execute("SELECT * FROM offerings WHERE user_id = ? ORDER BY offering_date DESC", (user_id,)).fetchall()
        sunday_entries = conn.execute("SELECT * FROM sunday_entries WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    # Header
    writer.writerow(["Type", "ID", "Bill/Area", "Teacher/Department", "Students/Amount", "Notes/Description", "Date", "Status", "User"])

    # Bills
    for b in bills:
        try:
            b_id = b["id"]
            b_user = b["full_name"] if "full_name" in b.keys() else ""
            writer.writerow(["Bill", b_id, b.get("bill_number", ""), b.get("department", ""), "%.2f" % (b.get("amount", 0) or 0), b.get("description", ""), b.get("created_at", ""), b.get("status", ""), b_user])
        except Exception:
            pass

    # Offerings
    for o in offerings:
        try:
            o_id = o["id"]
            o_user = o["full_name"] if "full_name" in o.keys() else ""
            writer.writerow(["Offering", o_id, "", o.get("fund_type", ""), "%.2f" % (o.get("amount", 0) or 0), o.get("description", ""), o.get("offering_date", ""), "", o_user])
        except Exception:
            pass

    # Sunday entries
    for s in sunday_entries:
        try:
            s_id = s["id"]
            s_user = s["full_name"] if "full_name" in s.keys() else ""
            writer.writerow(["Sunday", s_id, s.get("area_name", ""), s.get("teacher_name", ""), s.get("student_count", 0), s.get("notes", ""), s.get("created_at", ""), "", s_user])
        except Exception:
            pass

    csv_text = output.getvalue()
    output.close()
    b = csv_text.encode("utf-8-sig")
    filename = f"reports_{datetime.now().strftime('%Y%m%d')}.csv"
    return Response(b, mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})


if __name__ == "__main__":
    # Migration: Add fund_type to existing offerings table if needed
    with sqlite3.connect(DB_PATH) as conn:
        try:
            conn.execute("ALTER TABLE offerings ADD COLUMN fund_type TEXT DEFAULT 'Church Building Fund'")
        except sqlite3.OperationalError:
            pass
        # Ensure sunday_entries table exists
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sunday_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    area_name TEXT,
                    teacher_name TEXT,
                    student_count INTEGER,
                    notes TEXT,
                    file_name TEXT,
                    created_at TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """)
        except sqlite3.OperationalError:
            pass

    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
