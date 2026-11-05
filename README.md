# CampusConnect

A Flask-based college portal for students, faculty, and administrators.

## Run locally

1. Create and activate a Python virtual environment.
2. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Optionally set a persistent Flask session key for this terminal:

   ```powershell
   $env:CAMPUSCONNECT_SECRET_KEY = "replace-with-a-random-secret"
   ```

   If unset, the app generates a temporary key at startup. Existing sessions
   will be invalidated when the app restarts.

4. Start the app:

   ```powershell
   python app.py
   ```

The SQLite database and uploaded files are local runtime data and are excluded
from Git.
