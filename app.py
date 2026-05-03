from flask import Flask, render_template, request, jsonify, session
import os
import mysql.connector
from mysql.connector import pooling, Error
from flask_cors import CORS

app = Flask(__name__)
# Use environment variable for secret in production
app.secret_key = os.environ.get("SECRET_KEY", "payrollpro_dev_secret")

# ── DB CONFIG & POOL ──
db_config = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "Gowtham#2103"),
    "database": os.environ.get("DB_NAME", "sal_management"),
}

# Create a small connection pool to reuse connections across requests
try:
    pool = pooling.MySQLConnectionPool(
        pool_name="mypool",
        pool_size=int(os.environ.get("DB_POOL_SIZE", 5)),
        **db_config
    )
except Error:
    pool = None


def get_db():
    """Return a DB connection from the pool if available, else a new connection."""
    if pool:
        return pool.get_connection()
    return mysql.connector.connect(**db_config)

# Enable CORS for frontend access (adjust origin in production)
CORS(app)

# ── LOGIN ──
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    if data.get("username") == "admin" and data.get("password") == "Admin@123":
        session["logged_in"] = True
        return jsonify({"status": "ok"})
    return jsonify({"status": "fail"}), 401

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "ok"})

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# ── GET ALL / SEARCH ──
@app.route("/api/employees", methods=["GET"])
@login_required
def get_employees():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "All").strip()

    query  = "SELECT * FROM employees WHERE 1=1"
    params = []

    if status != "All":
        query += " AND status = %s"
        params.append(status)

    if search:
        like = f"%{search}%"
        query += """ AND (
            CONCAT(fname,' ',lname) LIKE %s OR
            empid       LIKE %s OR
            dept        LIKE %s OR
            designation LIKE %s OR
            email       LIKE %s
        )"""
        params.extend([like, like, like, like, like])

    conn   = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params)
    rows = cursor.fetchall()

    # convert date/datetime to string for JSON
    for row in rows:
        for key, val in row.items():
            if hasattr(val, 'isoformat'):
                row[key] = val.isoformat()

    cursor.close()
    conn.close()
    return jsonify(rows)

# ── STATS ──
@app.route("/api/stats", methods=["GET"])
@login_required
def get_stats():
    conn   = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT status, salary FROM employees")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    total    = len(rows)
    active   = sum(1 for r in rows if r["status"] == "Active")
    on_leave = sum(1 for r in rows if r["status"] == "On Leave")
    payroll  = sum(float(r["salary"] or 0) for r in rows)
    avg      = round(payroll / total) if total else 0

    return jsonify({
        "total": total, "active": active,
        "on_leave": on_leave, "payroll": payroll, "avg": avg
    })

# ── ADD EMPLOYEE ──
@app.route("/api/employees", methods=["POST"])
@login_required
def add_employee():
    d = request.json
    try:
        conn   = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO employees
            (empid, fname, lname, email, phone, gender, dept, designation, emptype, status, joindate, salary)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            d["empid"], d["fname"], d["lname"],
            d.get("email") or None,
            d.get("phone") or None,
            d.get("gender") or None,
            d["dept"], d["designation"],
            d.get("emptype") or None,
            d["status"],
            d.get("joindate") or None,
            d["salary"]
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "added"})
    except mysql.connector.IntegrityError:
        return jsonify({"error": "Employee ID already exists"}), 409

# ── UPDATE EMPLOYEE ──
@app.route("/api/employees/<int:emp_id>", methods=["PUT"])
@login_required
def update_employee(emp_id):
    d = request.json
    try:
        conn   = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE employees SET
            empid=%s, fname=%s, lname=%s, email=%s, phone=%s, gender=%s,
            dept=%s, designation=%s, emptype=%s, status=%s, joindate=%s, salary=%s
            WHERE id=%s
        """, (
            d["empid"], d["fname"], d["lname"],
            d.get("email") or None,
            d.get("phone") or None,
            d.get("gender") or None,
            d["dept"], d["designation"],
            d.get("emptype") or None,
            d["status"],
            d.get("joindate") or None,
            d["salary"],
            emp_id
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "updated"})
    except mysql.connector.IntegrityError:
        return jsonify({"error": "Duplicate Employee ID"}), 409

# ── DELETE EMPLOYEE ──
@app.route("/api/employees/<int:emp_id>", methods=["DELETE"])
@login_required
def delete_employee(emp_id):
    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM employees WHERE id = %s", (emp_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"status": "deleted"})

# ── SERVE HTML ──
@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)