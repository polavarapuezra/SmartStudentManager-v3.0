import sqlite3
import pandas as pd
import os

DB_PATH = "students.db"
FILE_PATH = "studentdata.xlsx"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_no TEXT UNIQUE NOT NULL,
            admission_no TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            gender TEXT,
            father_name TEXT,
            mother_name TEXT,
            address TEXT,
            email TEXT,
            phone TEXT,
            aadhaar_no TEXT,
            dob TEXT,
            course_name TEXT,
            admission_date TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            semester INTEGER NOT NULL,
            amount_paid REAL DEFAULT 0,
            result TEXT DEFAULT '',
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(student_id, semester)
        )
    ''')

    conn.commit()
    conn.close()


def insert_student(row):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO students (
            roll_no, admission_no, full_name, gender,
            father_name, mother_name, address, email,
            phone, aadhaar_no, dob, course_name, admission_date
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', (
        str(row.get("Roll No", "")),
        str(row.get("Admission No", "")),
        str(row.get("Full Name", "")),
        str(row.get("Gender", "")),
        str(row.get("Father Name", "")),
        str(row.get("Mother Name", "")),
        str(row.get("Address", "")),
        str(row.get("Email", "")),
        str(row.get("Phone", "")),
        str(row.get("Aadhaar No", "")),
        str(row.get("Date of Birth", "")),
        str(row.get("Course Name", "")),
        str(row.get("Date of Admission", ""))
    ))
    conn.commit()
    conn.close()


def update_fee(roll_no, semester, amount_paid, result):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM students WHERE roll_no = ?", (str(roll_no),))
    student = cursor.fetchone()

    print(f"update_fee: roll={roll_no}, sem={semester}, fee={amount_paid}, student={dict(student) if student else None}")

    if not student:
        conn.close()
        return False

    cursor.execute('''
        INSERT INTO fees (student_id, semester, amount_paid, result)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(student_id, semester)
        DO UPDATE SET amount_paid = excluded.amount_paid,
                      result = excluded.result
    ''', (student["id"], int(semester), float(amount_paid), str(result)))

    conn.commit()
    conn.close()
    return True


def remove_student(roll_no):
    conn = get_connection()
    cursor = conn.cursor()
    # fees deleted automatically via foreign key cascade
    cursor.execute("DELETE FROM fees WHERE student_id = (SELECT id FROM students WHERE roll_no = ?)", (str(roll_no),))
    cursor.execute("DELETE FROM students WHERE roll_no = ?", (str(roll_no),))
    conn.commit()
    conn.close()


def search_student(query):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.*,
               COALESCE(f1.amount_paid, 0) as sem1_fee, COALESCE(f1.result, '') as sem1_result,
               COALESCE(f2.amount_paid, 0) as sem2_fee, COALESCE(f2.result, '') as sem2_result,
               COALESCE(f3.amount_paid, 0) as sem3_fee, COALESCE(f3.result, '') as sem3_result,
               COALESCE(f4.amount_paid, 0) as sem4_fee, COALESCE(f4.result, '') as sem4_result
        FROM students s
        LEFT JOIN fees f1 ON s.id = f1.student_id AND f1.semester = 1
        LEFT JOIN fees f2 ON s.id = f2.student_id AND f2.semester = 2
        LEFT JOIN fees f3 ON s.id = f3.student_id AND f3.semester = 3
        LEFT JOIN fees f4 ON s.id = f4.student_id AND f4.semester = 4
        WHERE s.roll_no = ? OR s.admission_no = ? OR LOWER(s.full_name) = LOWER(?)
    ''', (query, query, query))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_pending_students(semester, fee_amount):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.full_name, s.phone,
               COALESCE(f.amount_paid, 0) as paid
        FROM students s
        LEFT JOIN fees f ON s.id = f.student_id AND f.semester = ?
        WHERE COALESCE(f.amount_paid, 0) < ?
    ''', (semester, fee_amount))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_dashboard_stats():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM students")
    total = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(DISTINCT student_id) as paid FROM fees WHERE amount_paid > 0")
    paid = cursor.fetchone()["paid"]

    cursor.execute("SELECT COALESCE(SUM(amount_paid), 0) as collected FROM fees")
    collected = cursor.fetchone()["collected"]

    cursor.execute('''
        SELECT semester, COALESCE(SUM(amount_paid), 0) as total
        FROM fees GROUP BY semester ORDER BY semester
    ''')
    sem_totals = [0, 0, 0, 0]
    for r in cursor.fetchall():
        sem = r["semester"]
        if 1 <= sem <= 4:
            sem_totals[sem - 1] = round(r["total"], 2)

    cursor.execute("SELECT course_name, COUNT(*) as count FROM students GROUP BY course_name")
    course_rows = cursor.fetchall()

    conn.close()
    return {
        "total": total,
        "paid": paid,
        "unpaid": total - paid,
        "collected": round(collected, 2),
        "sem_totals": sem_totals,
        "course_labels": [r["course_name"] for r in course_rows],
        "course_data": [r["count"] for r in course_rows]
    }


def read_data():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.*,
               COALESCE(f1.amount_paid, '') as sem1_fee,
               COALESCE(f1.result, '') as sem1_result,
               COALESCE(f2.amount_paid, '') as sem2_fee,
               COALESCE(f2.result, '') as sem2_result,
               COALESCE(f3.amount_paid, '') as sem3_fee,
               COALESCE(f3.result, '') as sem3_result,
               COALESCE(f4.amount_paid, '') as sem4_fee,
               COALESCE(f4.result, '') as sem4_result
        FROM students s
        LEFT JOIN fees f1 ON s.id = f1.student_id AND f1.semester = 1
        LEFT JOIN fees f2 ON s.id = f2.student_id AND f2.semester = 2
        LEFT JOIN fees f3 ON s.id = f3.student_id AND f3.semester = 3
        LEFT JOIN fees f4 ON s.id = f4.student_id AND f4.semester = 4
    ''')
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame([dict(r) for r in rows])
    df = df.rename(columns={
        'roll_no': 'Roll No',
        'admission_no': 'Admission No',
        'full_name': 'Full Name',
        'gender': 'Gender',
        'father_name': 'Father Name',
        'mother_name': 'Mother Name',
        'address': 'Address',
        'email': 'Email',
        'phone': 'Phone',
        'aadhaar_no': 'Aadhaar No',
        'dob': 'Date of Birth',
        'course_name': 'Course Name',
        'admission_date': 'Date of Admission',
        'sem1_fee': 'Sem 1 Fee',
        'sem1_result': 'Sem 1 Result',
        'sem2_fee': 'Sem 2 Fee',
        'sem2_result': 'Sem 2 Result',
        'sem3_fee': 'Sem 3 Fee',
        'sem3_result': 'Sem 3 Result',
        'sem4_fee': 'Sem 4 Fee',
        'sem4_result': 'Sem 4 Result'
    })
    return df.drop(columns=['id'], errors='ignore')


def save_data(df):
    for _, row in df.iterrows():
        insert_student(row)


def migrate_from_excel():
    if not os.path.exists(FILE_PATH):
        return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as c FROM students")
    count = cursor.fetchone()["c"]
    conn.close()
    if count > 0:
        return

    print("Migrating Excel to SQLite...")
    df = pd.read_excel(FILE_PATH)
    for _, row in df.iterrows():
        insert_student(row)
        for sem in range(1, 5):
            fee_col = f"Sem {sem} Fee"
            res_col = f"Sem {sem} Result"
            if fee_col in df.columns:
                try:
                    fee = float(str(row.get(fee_col, 0)).replace(',', '').strip() or 0)
                    result = str(row.get(res_col, ""))
                    if fee > 0:
                        update_fee(str(row.get("Roll No")), sem, fee, result)
                except:
                    pass
    print("Migration complete.")


init_db()
migrate_from_excel()