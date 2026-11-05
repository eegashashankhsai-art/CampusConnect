import sqlite3
from getpass import getpass

from werkzeug.security import generate_password_hash


DATABASE = "database/college.db"


def main():
    print("================================")
    print(" CampusConnect - Faculty Account")
    print("================================")

    full_name = input("Enter faculty name: ").strip()
    email = input("Enter faculty email: ").strip().lower()
    department = input("Enter department: ").strip()
    password = getpass("Create password: ")
    confirm_password = getpass("Confirm password: ")

    if not full_name or not email or not department:
        print("Please fill in all details.")
        return

    if len(password) < 8:
        print("Password must contain at least 8 characters.")
        return

    if password != confirm_password:
        print("Passwords do not match.")
        return

    conn = sqlite3.connect(DATABASE)
    try:
        hashed_password = generate_password_hash(password)
        conn.execute("""
            INSERT INTO faculty
            (full_name, email, department, password)
            VALUES (?, ?, ?, ?)
        """, (full_name, email, department, hashed_password))
        conn.commit()
        print("Faculty account created successfully!")
    except sqlite3.IntegrityError:
        print("A faculty account with this email already exists.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
