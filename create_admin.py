import sqlite3
from getpass import getpass

from werkzeug.security import generate_password_hash


DATABASE = "database/college.db"


def main():
    print("CampusConnect - Create Admin Account")
    username = input("Enter admin username: ").strip()
    password = getpass("Enter admin password: ")
    confirm_password = getpass("Confirm admin password: ")

    if not username:
        print("Username cannot be empty.")
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
            INSERT INTO admins (username, password)
            VALUES (?, ?)
        """, (username, hashed_password))
        conn.commit()
        print("Admin account created successfully!")
    except sqlite3.IntegrityError:
        print("This admin username already exists.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
