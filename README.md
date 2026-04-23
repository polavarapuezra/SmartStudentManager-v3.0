# SmartStudentManager-v3.0

A desktop application built for institute front-office staff to manage student records and automate fee reminders.

Built as a final year project for Nobel Institute of Science and Technology (NIST).

---

## Features

- Admin login with email OTP verification
- Student entry — add, search, and remove students
- Semester data management — update fee and result per semester
- Dashboard with live charts — paid/unpaid count, semester wise fee, course wise students
- Automated fee reminder SMS to pending students
- PDF download — individual student report and all students summary
- SQLite database with proper schema — students and fees as separate tables

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| Frontend | HTML, CSS, Bootstrap, JavaScript |
| Database | SQLite |
| Desktop | PyWebView |
| Charts | Chart.js |
| PDF | ReportLab |
| Email | SMTP (Gmail) |
| SMS | BulkBlaster API |

---

## Project Structure

```
SmartStudent Manager/
├── app.py                  # Flask routes and application logic
├── data_access.py          # All database operations (SQLite)
├── .env                    # API keys and secrets (not pushed to GitHub)
├── admin.json              # Admin credentials (not pushed to GitHub)
├── students.db             # SQLite database (not pushed to GitHub)
├── studentdata.xlsx        # Old Excel file for migration (not pushed to GitHub)
├── README.md               # Project documentation
├── .gitignore              # Files excluded from GitHub
├── templates/              # HTML pages
│   ├── main.html           # Dashboard page
│   ├── entry.html          # Student entry form
│   ├── index.html          # Student search page
│   ├── sem.html            # Semester update form
│   ├── fee_alert.html      # Fee alert page
│   ├── login.html          # Admin login page
│   ├── pass.html           # Student found result
│   ├── passno.html         # Student not found page
│   └── student.html        # Student details page
└── static/                 # CSS and assets
    └── index.css           # Main stylesheet
```
