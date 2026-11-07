from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, send_from_directory, abort
)
import sqlite3
import os
import uuid
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from database import create_tables

app = Flask(__name__)

app.secret_key = os.environ.get("CAMPUSCONNECT_SECRET_KEY") or os.urandom(32)

# --------------------------------
# UPLOAD SETTINGS
# --------------------------------

UPLOAD_FOLDER = os.path.join("static", "uploads")
ALLOWED_EXTENSIONS = {'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Create database tables
create_tables()

# --------------------------------
# INITIAL ADMIN ACCOUNT SETUP
# --------------------------------
def create_initial_admin():
    username = os.environ.get("CAMPUSCONNECT_ADMIN_USERNAME")
    password = os.environ.get("CAMPUSCONNECT_ADMIN_PASSWORD")
    if not username or not password:
        return
    if len(password) < 8:
        print("Admin setup skipped: password must be at least 8 characters.")
        return
    conn = sqlite3.connect("database/college.db")
    try:
        existing_admin = conn.execute(
            "SELECT id FROM admins WHERE username = ?",
            (username,)
        ).fetchone()
        if existing_admin is None:
            hashed_password = generate_password_hash(password)
            conn.execute("""
                INSERT INTO admins (username, password)
                VALUES (?, ?)
            """, (username, hashed_password))
            conn.commit()
            print("Initial admin account created successfully!")
        else:
            print("Initial admin account already exists.")
    finally:
        conn.close()


create_initial_admin()


# --------------------------------
# CHECK ALLOWED FILE TYPE
# --------------------------------

def allowed_file(filename):
    return (
        '.' in filename and
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )


# --------------------------------
# DATABASE CONNECTION
# --------------------------------

def get_db_connection():
    conn = sqlite3.connect("database/college.db")
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------
# HOME PAGE
# --------------------------------

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/announcements')
def announcements():
    conn = get_db_connection()
    announcements = conn.execute("""
        SELECT id, title, description, category, created_at
        FROM announcements
        ORDER BY created_at DESC
    """).fetchall()
    conn.close()
    return render_template(
        'announcements.html',
        announcements=announcements
    )


# --------------------------------
# ADMIN LOGIN
# --------------------------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        conn = get_db_connection()
        admin = conn.execute("""
            SELECT * FROM admins
            WHERE username = ?
        """, (username,)).fetchone()
        conn.close()

        if admin and check_password_hash(admin['password'], password):
            session['admin_id'] = admin['id']
            session['admin_username'] = admin['username']
            flash("Admin login successful!")
            return redirect(url_for('admin_dashboard'))

        flash("Invalid admin username or password.")

    return render_template('admin_login.html')


# --------------------------------
# ADMIN DASHBOARD
# --------------------------------

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    announcements = conn.execute("""
        SELECT id, title, description, category, created_at
        FROM announcements
        ORDER BY created_at DESC
    """).fetchall()
    conn.close()
    return render_template(
        'admin_dashboard.html',
        announcements=announcements
    )


@app.route('/admin/doubts')
def admin_doubts():
    if 'admin_id' not in session:
        flash("Please login as admin first.")
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    doubts = conn.execute("""
        SELECT
            student_doubts.id,
            student_doubts.subject,
            student_doubts.title,
            student_doubts.description,
            student_doubts.status,
            student_doubts.created_at,
            students.full_name AS student_name,
            students.student_id AS student_code
        FROM student_doubts
        JOIN students
            ON student_doubts.student_id = students.id
        ORDER BY student_doubts.created_at DESC
    """).fetchall()
    doubts_with_replies = []
    for doubt in doubts:
        replies = conn.execute("""
            SELECT
                doubt_replies.answer,
                doubt_replies.created_at,
                faculty.full_name AS faculty_name
            FROM doubt_replies
            JOIN faculty
                ON doubt_replies.faculty_id = faculty.id
            WHERE doubt_replies.doubt_id = ?
            ORDER BY doubt_replies.created_at ASC
        """, (doubt['id'],)).fetchall()
        doubt_data = dict(doubt)
        doubt_data['replies'] = replies
        doubts_with_replies.append(doubt_data)

    conn.close()
    return render_template(
        'admin_doubts.html',
        doubts=doubts_with_replies
    )


@app.route('/admin/doubts/reply/<int:doubt_id>', methods=['POST'])
def admin_reply_doubt(doubt_id):
    if 'admin_id' not in session:
        flash("Please login as admin first.")
        return redirect(url_for('admin_login'))

    answer = request.form.get('answer', '').strip()
    if not answer:
        flash("Please enter your reply.")
        return redirect(url_for('admin_doubts'))

    conn = get_db_connection()
    doubt = conn.execute(
        "SELECT id FROM student_doubts WHERE id = ?",
        (doubt_id,)
    ).fetchone()
    if doubt is None:
        conn.close()
        flash("Doubt not found.")
        return redirect(url_for('admin_doubts'))

    conn.execute("""
        INSERT INTO admin_doubt_replies
        (doubt_id, admin_id, answer)
        VALUES (?, ?, ?)
    """, (
        doubt_id,
        session['admin_id'],
        answer
    ))
    conn.execute("""
        UPDATE student_doubts
        SET status = 'Answered'
        WHERE id = ?
    """, (doubt_id,))
    conn.commit()
    conn.close()
    flash("Your admin reply has been submitted successfully!")
    return redirect(url_for('admin_doubts'))


@app.route('/admin/faculty')
def manage_faculty():
    if 'admin_id' not in session:
        flash("Please login as admin first.")
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    faculty_list = conn.execute("""
        SELECT id, full_name, email, department
        FROM faculty
        ORDER BY id DESC
    """).fetchall()
    conn.close()
    return render_template(
        'manage_faculty.html',
        faculty_list=faculty_list
    )


@app.route('/admin/faculty/edit/<int:faculty_id>', methods=['GET', 'POST'])
def edit_faculty(faculty_id):
    if 'admin_id' not in session:
        flash("Please login as admin first.")
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    faculty = conn.execute(
        "SELECT * FROM faculty WHERE id = ?",
        (faculty_id,)
    ).fetchone()
    if not faculty:
        conn.close()
        flash("Faculty member not found.")
        return redirect(url_for('manage_faculty'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        department = request.form.get('department', '').strip()

        if not full_name or not email or not department:
            conn.close()
            flash("All fields are required.")
            return redirect(url_for('edit_faculty', faculty_id=faculty_id))

        existing_email = conn.execute("""
            SELECT id FROM faculty
            WHERE email = ? AND id != ?
        """, (email, faculty_id)).fetchone()
        if existing_email:
            conn.close()
            flash("This email is already registered.")
            return redirect(url_for('edit_faculty', faculty_id=faculty_id))

        conn.execute("""
            UPDATE faculty
            SET full_name = ?, email = ?, department = ?
            WHERE id = ?
        """, (full_name, email, department, faculty_id))
        conn.commit()
        conn.close()
        flash("Faculty details updated successfully!")
        return redirect(url_for('manage_faculty'))

    conn.close()
    return render_template(
        'edit_faculty.html',
        faculty=faculty
    )


@app.route('/admin/faculty/delete/<int:faculty_id>', methods=['POST'])
def delete_faculty(faculty_id):
    if 'admin_id' not in session:
        flash("Please login as admin first.")
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    faculty = conn.execute(
        "SELECT id FROM faculty WHERE id = ?",
        (faculty_id,)
    ).fetchone()
    if not faculty:
        conn.close()
        flash("Faculty member not found.")
        return redirect(url_for('manage_faculty'))

    conn.execute(
        "DELETE FROM faculty WHERE id = ?",
        (faculty_id,)
    )
    conn.commit()
    conn.close()
    flash("Faculty member deleted successfully!")
    return redirect(url_for('manage_faculty'))


@app.route('/admin/faculty/add', methods=['GET', 'POST'])
def add_faculty():
    if 'admin_id' not in session:
        flash("Please login as admin first.")
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        department = request.form.get('department', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not full_name or not email or not department or not password:
            flash("All fields are required.")
            return redirect(url_for('add_faculty'))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.")
            return redirect(url_for('add_faculty'))

        if password != confirm_password:
            flash("Passwords do not match.")
            return redirect(url_for('add_faculty'))

        hashed_password = generate_password_hash(password)
        conn = get_db_connection()
        try:
            conn.execute("""
                INSERT INTO faculty
                (full_name, email, department, password)
                VALUES (?, ?, ?, ?)
            """, (full_name, email, department, hashed_password))
            conn.commit()
        except sqlite3.IntegrityError:
            flash("A faculty account with this email already exists.")
            return redirect(url_for('add_faculty'))
        finally:
            conn.close()

        flash("Faculty account created successfully!")
        return redirect(url_for('manage_faculty'))

    return render_template('add_faculty.html')


@app.route('/admin/register', methods=['GET', 'POST'])
def admin_register():
    if 'admin_id' not in session:
        flash("Please login as admin first.")
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not username or not password:
            flash("All fields are required.")
            return redirect(url_for('admin_register'))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.")
            return redirect(url_for('admin_register'))

        if password != confirm_password:
            flash("Passwords do not match.")
            return redirect(url_for('admin_register'))

        conn = get_db_connection()
        existing_admin = conn.execute(
            "SELECT id FROM admins WHERE username = ?",
            (username,)
        ).fetchone()
        if existing_admin:
            conn.close()
            flash("This admin username already exists.")
            return redirect(url_for('admin_register'))

        hashed_password = generate_password_hash(password)
        conn.execute(
            "INSERT INTO admins (username, password) VALUES (?, ?)",
            (username, hashed_password)
        )
        conn.commit()
        conn.close()
        flash("New admin registered successfully!")
        return redirect(url_for('admin_dashboard'))

    return render_template('admin_register.html')


# --------------------------------
# PUBLISH ANNOUNCEMENT
# --------------------------------

@app.route('/admin/add_announcement', methods=['GET', 'POST'])
def admin_add_announcement():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    allowed_categories = [
        'General',
        'Academic',
        'Events',
        'Examinations',
        'Urgent',
    ]

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()

        if not title or not description:
            flash("Please enter an announcement title and description.")
            return redirect(url_for('admin_add_announcement'))

        if category not in allowed_categories:
            flash("Please select a valid category.")
            return redirect(url_for('admin_add_announcement'))

        conn = get_db_connection()
        try:
            conn.execute("""
                INSERT INTO announcements
                (title, description, category)
                VALUES (?, ?, ?)
            """, (title, description, category))
            conn.commit()
        finally:
            conn.close()

        flash("Announcement published successfully!")
        return redirect(url_for('admin_dashboard'))

    return render_template(
        'add_announcement.html',
        categories=allowed_categories
    )


# --------------------------------
# ADMIN EDIT ANNOUNCEMENT
# --------------------------------

@app.route(
    '/admin/edit_announcement/<int:announcement_id>',
    methods=['GET', 'POST']
)
def admin_edit_announcement(announcement_id):
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    announcement = conn.execute("""
        SELECT * FROM announcements
        WHERE id = ?
    """, (announcement_id,)).fetchone()

    if announcement is None:
        conn.close()
        abort(404)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()
        allowed_categories = [
            'General',
            'Academic',
            'Events',
            'Examinations',
            'Urgent',
        ]

        if not title or not description or category not in allowed_categories:
            conn.close()
            flash("Please enter valid announcement details.")
            return redirect(url_for(
                'admin_edit_announcement',
                announcement_id=announcement_id
            ))

        conn.execute("""
            UPDATE announcements
            SET title = ?, description = ?, category = ?
            WHERE id = ?
        """, (title, description, category, announcement_id))
        conn.commit()
        conn.close()
        flash("Announcement updated successfully!")
        return redirect(url_for('admin_dashboard'))

    conn.close()
    return render_template(
        'edit_announcement.html',
        announcement=announcement
    )


# --------------------------------
# ADMIN DELETE ANNOUNCEMENT
# --------------------------------

@app.route(
    '/admin/delete_announcement/<int:announcement_id>',
    methods=['POST']
)
def admin_delete_announcement(announcement_id):
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    announcement = conn.execute("""
        SELECT id FROM announcements
        WHERE id = ?
    """, (announcement_id,)).fetchone()

    if announcement is None:
        conn.close()
        abort(404)

    conn.execute("""
        DELETE FROM announcements
        WHERE id = ?
    """, (announcement_id,))
    conn.commit()
    conn.close()
    flash("Announcement deleted successfully!")
    return redirect(url_for('admin_dashboard'))


# --------------------------------
# ADMIN LOGOUT
# --------------------------------

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    flash("Admin logged out successfully!")
    return redirect(url_for('admin_login'))


# --------------------------------
# FACULTY LOGIN
# --------------------------------

@app.route('/faculty/login', methods=['GET', 'POST'])
def faculty_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        conn = get_db_connection()
        faculty = conn.execute("""
            SELECT * FROM faculty
            WHERE email = ?
        """, (email,)).fetchone()
        conn.close()

        if faculty and check_password_hash(faculty['password'], password):
            session.clear()
            session['faculty_id'] = faculty['id']
            session['faculty_name'] = faculty['full_name']
            flash("Faculty login successful!")
            return redirect(url_for('faculty_dashboard'))

        flash("Invalid faculty email or password.")

    return render_template('faculty_login.html')


# --------------------------------
# FACULTY DASHBOARD
# --------------------------------

@app.route('/faculty/dashboard')
def faculty_dashboard():
    if 'faculty_id' not in session:
        return redirect(url_for('faculty_login'))

    conn = get_db_connection()
    total_students = conn.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]
    total_exams = conn.execute(
        "SELECT COUNT(*) FROM exams"
    ).fetchone()[0]
    total_materials = conn.execute(
        "SELECT COUNT(*) FROM study_materials"
    ).fetchone()[0]
    total_attendance = conn.execute(
        "SELECT COUNT(*) FROM attendance"
    ).fetchone()[0]
    conn.close()
    return render_template(
        'faculty_dashboard.html',
        total_students=total_students,
        total_exams=total_exams,
        total_materials=total_materials,
        total_attendance=total_attendance
    )


# --------------------------------
# FACULTY LOGOUT
# --------------------------------

@app.route('/faculty/logout')
def faculty_logout():
    session.pop('faculty_id', None)
    session.pop('faculty_name', None)
    flash("Faculty logged out successfully!")
    return redirect(url_for('faculty_login'))


# --------------------------------
# STUDENT REGISTRATION
# --------------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        full_name = request.form['full_name']
        student_id = request.form['student_id']
        email = request.form['email']
        department = request.form['department']
        year = request.form['year']
        password = request.form['password']

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()

        try:
            conn.execute("""
                INSERT INTO students
                (full_name, student_id, email, department, year, password)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                full_name, student_id, email,
                department, year, hashed_password
            ))

            conn.commit()
            flash("Registration successful! You can now log in.")

        except sqlite3.IntegrityError:
            flash("Student ID or email already exists.")

        finally:
            conn.close()

        return redirect(url_for('register'))

    return render_template('register.html')


# --------------------------------
# STUDENT LOGIN
# --------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()

        student = conn.execute(
            "SELECT * FROM students WHERE email = ?",
            (email,)
        ).fetchone()

        conn.close()

        if student and check_password_hash(student['password'], password):

            session['student_id'] = student['id']
            session['student_name'] = student['full_name']

            flash("Login successful!")

            return redirect(url_for('student_dashboard'))

        else:
            flash("Invalid email or password. Please try again.")

    return render_template('login.html')


# --------------------------------
# STUDENT DASHBOARD
# --------------------------------

@app.route('/dashboard')
def student_dashboard():
    if 'student_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    student = conn.execute("""
        SELECT department, year
        FROM students
        WHERE id = ?
    """, (session['student_id'],)).fetchone()

    if student is None:
        conn.close()
        session.clear()
        return redirect(url_for('login'))

    total_attendance = conn.execute("""
        SELECT COUNT(*)
        FROM attendance
        WHERE student_id = ?
    """, (session['student_id'],)).fetchone()[0]
    present_attendance = conn.execute("""
        SELECT COUNT(*)
        FROM attendance
        WHERE student_id = ?
        AND LOWER(status) = 'present'
    """, (session['student_id'],)).fetchone()[0]
    attendance_percentage = (
        round((present_attendance / total_attendance) * 100, 2)
        if total_attendance else 0
    )

    upcoming_exams = conn.execute("""
        SELECT COUNT(*)
        FROM exams
        WHERE department = ? AND year = ? AND exam_date >= ?
    """, (
        student['department'],
        student['year'],
        date.today().isoformat()
    )).fetchone()[0]
    total_materials = conn.execute(
        "SELECT COUNT(*) FROM study_materials"
    ).fetchone()[0]
    total_announcements = conn.execute(
        "SELECT COUNT(*) FROM announcements"
    ).fetchone()[0]
    conn.close()

    return render_template(
        'dashboard.html',
        attendance_percentage=attendance_percentage,
        upcoming_exams=upcoming_exams,
        total_materials=total_materials,
        total_announcements=total_announcements
    )


# --------------------------------
# STUDENT ASK A DOUBT
# --------------------------------

@app.route('/ask_doubt', methods=['GET', 'POST'])
def ask_doubt():
    if 'student_id' not in session:
        flash("Please login as a student first.")
        return redirect(url_for('login'))

    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()

        if not subject or not title or not description:
            flash("Please fill in all doubt details.")
            return redirect(url_for('ask_doubt'))

        conn = get_db_connection()
        student = conn.execute(
            "SELECT id FROM students WHERE id = ?",
            (session['student_id'],)
        ).fetchone()
        if student is None:
            conn.close()
            session.clear()
            return redirect(url_for('login'))

        conn.execute("""
            INSERT INTO student_doubts
            (student_id, subject, title, description)
            VALUES (?, ?, ?, ?)
        """, (
            session['student_id'],
            subject,
            title,
            description
        ))
        conn.commit()
        conn.close()
        flash("Your doubt has been submitted successfully!")
        return redirect(url_for('ask_doubt'))

    return render_template('ask_doubt.html')


# --------------------------------
# STUDENT MY DOUBTS
# --------------------------------

@app.route('/my_doubts')
def my_doubts():
    if 'student_id' not in session:
        flash("Please login as a student first.")
        return redirect(url_for('login'))

    conn = get_db_connection()
    doubts = conn.execute("""
        SELECT id, subject, title, description, status, created_at
        FROM student_doubts
        WHERE student_id = ?
        ORDER BY created_at DESC
    """, (session['student_id'],)).fetchall()

    doubts_with_replies = []
    for doubt in doubts:
        faculty_replies = conn.execute("""
            SELECT
                doubt_replies.answer,
                doubt_replies.created_at,
                faculty.full_name AS responder_name
            FROM doubt_replies
            JOIN faculty
                ON doubt_replies.faculty_id = faculty.id
            WHERE doubt_replies.doubt_id = ?
            ORDER BY doubt_replies.created_at ASC
        """, (doubt['id'],)).fetchall()
        admin_replies = conn.execute("""
            SELECT
                admin_doubt_replies.answer,
                admin_doubt_replies.created_at,
                admins.username AS responder_name
            FROM admin_doubt_replies
            JOIN admins
                ON admin_doubt_replies.admin_id = admins.id
            WHERE admin_doubt_replies.doubt_id = ?
            ORDER BY admin_doubt_replies.created_at ASC
        """, (doubt['id'],)).fetchall()
        doubts_with_replies.append({
            'doubt': doubt,
            'faculty_replies': faculty_replies,
            'admin_replies': admin_replies
        })

    conn.close()
    return render_template(
        'my_doubts.html',
        doubts_with_replies=doubts_with_replies
    )


# --------------------------------
# STUDENT PROFILE
# --------------------------------

@app.route('/profile')
def student_profile():

    if 'student_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    student = conn.execute(
        "SELECT * FROM students WHERE id = ?",
        (session['student_id'],)
    ).fetchone()

    conn.close()

    if student is None:
        session.clear()
        return redirect(url_for('login'))

    return render_template('profile.html', student=student)


# --------------------------------
# STUDENT ATTENDANCE
# --------------------------------

@app.route('/attendance')
def attendance():

    if 'student_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    records = conn.execute("""
        SELECT subject, attendance_date, status
        FROM attendance
        WHERE student_id = ?
        ORDER BY attendance_date DESC
    """, (session['student_id'],)).fetchall()

    conn.close()

    return render_template('attendance.html', records=records)


# --------------------------------
# FACULTY ATTENDANCE PAGE
# --------------------------------

@app.route('/faculty/attendance')
def faculty_attendance():
    if 'faculty_id' not in session:
        return redirect(url_for('faculty_login'))

    conn = get_db_connection()

    students = conn.execute(
        "SELECT id, full_name, student_id FROM students"
    ).fetchall()

    conn.close()

    return render_template(
        'faculty_attendance.html',
        students=students
    )


# --------------------------------
# SAVE ATTENDANCE
# --------------------------------

@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    if 'faculty_id' not in session:
        return redirect(url_for('faculty_login'))

    student_id = request.form.get('student_id')
    subject = request.form.get('subject', '').strip()
    attendance_date = request.form.get('attendance_date')
    status = request.form.get('status')

    if not student_id or not subject or not attendance_date:
        flash("Please fill in all attendance details.")
        return redirect(url_for('faculty_attendance'))

    if status not in ['Present', 'Absent']:
        flash("Please select a valid attendance status.")
        return redirect(url_for('faculty_attendance'))

    try:
        date.fromisoformat(attendance_date)
        student_id = int(student_id)

    except ValueError:
        flash("Invalid student ID or attendance date.")
        return redirect(url_for('faculty_attendance'))

    conn = get_db_connection()

    student = conn.execute(
        "SELECT id FROM students WHERE id = ?",
        (student_id,)
    ).fetchone()

    if student is None:
        conn.close()
        flash("Student not found.")
        return redirect(url_for('faculty_attendance'))

    conn.execute("""
        INSERT INTO attendance
        (student_id, subject, attendance_date, status)
        VALUES (?, ?, ?, ?)
    """, (student_id, subject, attendance_date, status))

    conn.commit()
    conn.close()

    flash("Attendance saved successfully!")

    return redirect(url_for('faculty_attendance'))


# --------------------------------
# FACULTY ADD EXAMINATION
# --------------------------------

@app.route('/add_exam', methods=['GET', 'POST'])
def add_exam():
    if 'faculty_id' not in session:
        return redirect(url_for('faculty_login'))
 
    if request.method == 'POST':

        exam_name = request.form.get('exam_name', '').strip()
        subject = request.form.get('subject', '').strip()
        exam_date = request.form.get('exam_date', '')
        exam_time = request.form.get('exam_time', '')
        department = request.form.get('department', '').strip()
        year = request.form.get('year', '')

        if not all([
            exam_name, subject, exam_date,
            exam_time, department, year
        ]):

            flash("Please fill in all examination details.")
            return redirect(url_for('add_exam'))

        try:
            date.fromisoformat(exam_date)

        except ValueError:
            flash("Please enter a valid examination date.")
            return redirect(url_for('add_exam'))

        conn = get_db_connection()

        conn.execute("""
            INSERT INTO exams
            (exam_name, subject, exam_date, exam_time, department, year)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            exam_name,
            subject,
            exam_date,
            exam_time,
            department,
            year
        ))

        conn.commit()
        conn.close()

        flash("Examination added successfully!")

        return redirect(url_for('add_exam'))

    return render_template('add_exam.html')


# --------------------------------
# STUDENT VIEW EXAMINATION TIMETABLE
# --------------------------------

@app.route('/exams')
def view_exams():

    if 'student_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    student = conn.execute("""
        SELECT department, year
        FROM students
        WHERE id = ?
    """, (session['student_id'],)).fetchone()

    if student is None:
        conn.close()
        session.clear()
        return redirect(url_for('login'))

    exams = conn.execute("""
        SELECT exam_name, subject, exam_date,
               exam_time, department, year
        FROM exams
        WHERE department = ? AND year = ?
        ORDER BY exam_date ASC
    """, (
        student['department'],
        student['year']
    )).fetchall()

    conn.close()

    return render_template('exams.html', exams=exams)


# --------------------------------
# FACULTY ADD EXAMINATION RESULTS
# --------------------------------

@app.route('/add_result', methods=['GET', 'POST'])
def add_result():
    if 'faculty_id' not in session:
        return redirect(url_for('faculty_login'))
 
    conn = get_db_connection()

    if request.method == 'POST':

        student_id = request.form.get('student_id')
        subject = request.form.get('subject', '').strip()
        marks = request.form.get('marks')
        total_marks = request.form.get('total_marks')
        grade = request.form.get('grade')

        try:
            student_id = int(student_id)
            marks = int(marks)
            total_marks = int(total_marks)

            if not subject or not grade:
                raise ValueError

            if total_marks <= 0 or marks < 0 or marks > total_marks:
                conn.close()
                flash("Please enter valid marks.")
                return redirect(url_for('add_result'))

        except (ValueError, TypeError):
            conn.close()
            flash("Please enter valid result details.")
            return redirect(url_for('add_result'))

        student = conn.execute(
            "SELECT id FROM students WHERE id = ?",
            (student_id,)
        ).fetchone()

        if student is None:
            conn.close()
            flash("Student not found.")
            return redirect(url_for('add_result'))

        conn.execute("""
            INSERT INTO results
            (student_id, subject, marks, total_marks, grade)
            VALUES (?, ?, ?, ?, ?)
        """, (
            student_id, subject, marks, total_marks, grade
        ))

        conn.commit()
        conn.close()

        flash("Student results saved successfully!")

        return redirect(url_for('add_result'))

    students = conn.execute(
        "SELECT id, full_name, student_id FROM students"
    ).fetchall()

    conn.close()

    return render_template('add_result.html', students=students)


# --------------------------------
# STUDENT VIEW EXAMINATION RESULTS
# --------------------------------

@app.route('/results')
def view_results():

    if 'student_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    results = conn.execute("""
        SELECT subject, marks, total_marks, grade
        FROM results
        WHERE student_id = ?
    """, (session['student_id'],)).fetchall()

    conn.close()

    return render_template('results.html', results=results)


# --------------------------------
# FACULTY UPLOAD STUDY MATERIALS
# --------------------------------

@app.route('/upload_material', methods=['GET', 'POST'])
def upload_material():
    if 'faculty_id' not in session:
        return redirect(url_for('faculty_login'))
 
    if request.method == 'POST':

        title = request.form.get('title', '').strip()
        subject = request.form.get('subject', '').strip()
        description = request.form.get('description', '').strip()

        file = request.files.get('material')

        if not title or not subject or file is None:
            flash("Please fill in all required details.")
            return redirect(url_for('upload_material'))

        if file.filename == '':
            flash("Please select a PDF file.")
            return redirect(url_for('upload_material'))

        if not allowed_file(file.filename):
            flash("Only PDF files are allowed.")
            return redirect(url_for('upload_material'))

        original_filename = secure_filename(file.filename)

        if not original_filename:
            flash("Invalid file name.")
            return redirect(url_for('upload_material'))

        # Generate a unique filename
        unique_filename = str(uuid.uuid4()) + "_" + original_filename

        file_path = os.path.join(
            app.config['UPLOAD_FOLDER'],
            unique_filename
        )

        file.save(file_path)

        conn = get_db_connection()

        try:
            conn.execute("""
                INSERT INTO study_materials
                (title, subject, description, filename)
                VALUES (?, ?, ?, ?)
            """, (
                title,
                subject,
                description,
                unique_filename
            ))

            conn.commit()

        except sqlite3.Error:
            conn.rollback()

            if os.path.exists(file_path):
                os.remove(file_path)

            flash("Unable to save study material. Please try again.")

        else:
            flash("Study material uploaded successfully!")

        finally:
            conn.close()

        return redirect(url_for('upload_material'))

    return render_template('upload_material.html')


# --------------------------------
# FACULTY VIEW ALL STUDENT DOUBTS
# --------------------------------

@app.route('/faculty/doubts')
def faculty_doubts():
    if 'faculty_id' not in session:
        flash("Please login as faculty first.")
        return redirect(url_for('faculty_login'))

    conn = get_db_connection()
    doubts = conn.execute("""
        SELECT student_doubts.*,
               students.full_name AS student_name,
               students.student_id AS student_code
        FROM student_doubts
        JOIN students
            ON student_doubts.student_id = students.id
        ORDER BY student_doubts.created_at DESC
    """).fetchall()

    doubts_with_replies = []
    for doubt in doubts:
        faculty_replies = conn.execute("""
            SELECT doubt_replies.answer,
                   doubt_replies.created_at,
                   faculty.full_name AS responder_name
            FROM doubt_replies
            JOIN faculty
                ON doubt_replies.faculty_id = faculty.id
            WHERE doubt_replies.doubt_id = ?
            ORDER BY doubt_replies.created_at ASC
        """, (doubt['id'],)).fetchall()
        admin_replies = conn.execute("""
            SELECT admin_doubt_replies.answer,
                   admin_doubt_replies.created_at,
                   admins.username AS responder_name
            FROM admin_doubt_replies
            JOIN admins
                ON admin_doubt_replies.admin_id = admins.id
            WHERE admin_doubt_replies.doubt_id = ?
            ORDER BY admin_doubt_replies.created_at ASC
        """, (doubt['id'],)).fetchall()
        doubts_with_replies.append({
            'doubt': doubt,
            'faculty_replies': faculty_replies,
            'admin_replies': admin_replies
        })

    conn.close()
    return render_template(
        'faculty_doubts.html',
        doubts_with_replies=doubts_with_replies
    )


@app.route('/faculty/doubts/reply/<int:doubt_id>', methods=['POST'])
def faculty_reply_doubt(doubt_id):
    if 'faculty_id' not in session:
        flash("Please login as faculty first.")
        return redirect(url_for('faculty_login'))

    answer = request.form.get('answer', '').strip()
    if not answer:
        flash("Please enter your answer.")
        return redirect(url_for('faculty_doubts'))

    conn = get_db_connection()
    doubt = conn.execute(
        "SELECT id FROM student_doubts WHERE id = ?",
        (doubt_id,)
    ).fetchone()
    if doubt is None:
        conn.close()
        flash("Doubt not found.")
        return redirect(url_for('faculty_doubts'))

    conn.execute("""
        INSERT INTO doubt_replies
        (doubt_id, faculty_id, answer)
        VALUES (?, ?, ?)
    """, (
        doubt_id,
        session['faculty_id'],
        answer
    ))
    conn.execute("""
        UPDATE student_doubts
        SET status = 'Answered'
        WHERE id = ?
    """, (doubt_id,))
    conn.commit()
    conn.close()
    flash("Your reply has been submitted successfully!")
    return redirect(url_for('faculty_doubts'))


@app.route('/faculty/doubts/resolve/<int:doubt_id>', methods=['POST'])
def faculty_resolve_doubt(doubt_id):
    if 'faculty_id' not in session:
        flash("Please login as faculty first.")
        return redirect(url_for('faculty_login'))

    conn = get_db_connection()
    doubt = conn.execute(
        "SELECT id FROM student_doubts WHERE id = ?",
        (doubt_id,)
    ).fetchone()
    if doubt is None:
        conn.close()
        flash("Doubt not found.")
        return redirect(url_for('faculty_doubts'))

    conn.execute("""
        UPDATE student_doubts
        SET status = 'Resolved'
        WHERE id = ?
    """, (doubt_id,))
    conn.commit()
    conn.close()
    flash("Doubt marked as resolved successfully!")
    return redirect(url_for('faculty_doubts'))


# --------------------------------
# STUDENT VIEW STUDY MATERIALS
# --------------------------------

@app.route('/study_materials')
def view_study_materials():

    if 'student_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    materials = conn.execute("""
        SELECT id, title, subject, description, filename
        FROM study_materials
        ORDER BY uploaded_at DESC
    """).fetchall()

    conn.close()

    return render_template(
        'study_materials.html',
        materials=materials
    )


# --------------------------------
# STUDENT DOWNLOAD STUDY MATERIALS
# --------------------------------

@app.route('/download_material/<int:material_id>')
def download_material(material_id):

    if 'student_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    material = conn.execute(
        "SELECT filename FROM study_materials WHERE id = ?",
        (material_id,)
    ).fetchone()

    conn.close()

    if material is None:
        abort(404)

    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        material['filename'],
        as_attachment=True
    )


# --------------------------------
# STUDENT LOGOUT
# --------------------------------

@app.route('/logout')
def logout():

    session.clear()

    flash("You have logged out successfully.")

    return redirect(url_for('login'))


# --------------------------------
# FILE SIZE ERROR
# --------------------------------

@app.errorhandler(413)
def file_too_large(error):
    flash("File is too large. Maximu m allowed size is 10 MB.")
    return redirect(url_for('upload_material'))


# --------------------------------
# RUN APPLICATION
# --------------------------------

if __name__ == '__main__':
    app.run(debug=True)