import sqlite3
import os

DATABASE = os.path.join("database", "college.db")


def get_connection():
    return sqlite3.connect(DATABASE)


def create_tables():

    os.makedirs("database", exist_ok=True)

    conn = get_connection()
    cursor = conn.cursor()

    # Students Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            student_id TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            department TEXT NOT NULL,
            year TEXT NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Faculty Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faculty (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            department TEXT NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Admin Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Attendance Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            attendance_date TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)

    # Examinations Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            exam_date TEXT NOT NULL,
            exam_time TEXT NOT NULL,
            department TEXT NOT NULL,
            year TEXT NOT NULL
        )
    """)

    # Results Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            marks INTEGER NOT NULL,
            total_marks INTEGER NOT NULL,
            grade TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)

    # Study Materials Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS study_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            description TEXT,
            filename TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # College Announcements Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

    print("CampusConnect database created successfully!")


if __name__ == "__main__":
    create_tables()