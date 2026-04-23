import os
import io
import time
import json
import random
import smtplib
import threading

from flask import Flask, request, jsonify, render_template, redirect, session, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import pandas as pd
import requests
import webview

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

from data_access import (read_data, save_data as save_excel, FILE_PATH,
                         init_db, insert_student, update_fee,
                         remove_student as db_remove, search_student,
                         get_pending_students, get_dashboard_stats)

load_dotenv()

app = Flask(__name__, template_folder='template')
app.secret_key = os.getenv("SECRET_KEY", "nist2024")

init_db()

window = webview.create_window(
    'Noble Institute of Science and Technology (NIST)',
    app, width=1920, height=1080, resizable=True, fullscreen=False
)

ADMIN_FILE = "admin.json"

# ---- admin helpers ----------------------------------------------------------------------------------------------------------------------

def load_admin():
    if not os.path.exists(ADMIN_FILE):
        return {}
    with open(ADMIN_FILE, "r") as f:
        return json.load(f)

def save_admin(data):
    with open(ADMIN_FILE, "w") as f:
        json.dump(data, f)

def safe_get(row, col):
    return row[col] if col in row and pd.notnull(row[col]) else ""

def safe_fee(x):
    try:
        val = str(x).replace(',', '').strip()
        return 0.0 if val in ['', 'nan', 'None'] else float(val)
    except:
        return 0.0

# ---- email OTP --------------------------------------------------------------------------------------------------------------

def send_otp_email(to_email, otp):
    try:
        sender = os.getenv("SENDER_EMAIL")
        password = os.getenv("SENDER_PASSWORD")

        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = to_email
        msg['Subject'] = "SmartStudent Manager - OTP Verification"
        msg.attach(MIMEText(f"""
Dear Admin,

Your login OTP is: {otp}

Valid for 5 minutes. Do not share this with anyone.

- NIST
        """, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

# ---- login --------------------------------------------------------------------------------------------------------------

@app.route('/login', methods=['GET'])
def login_page():
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        email = data.get("email").strip()
        password = data.get("password").strip()

        if not email or not password:
            return jsonify({"success": False, "error": "All fields required"}), 400

        if load_admin():
            return jsonify({"success": False, "error": "Account already exists. Contact admin."}), 400

        save_admin({"email": email, "password": generate_password_hash(password)})
        return jsonify({"success": True, "message": "Account created. Please login."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        email = data.get("email").strip()
        password = data.get("password").strip()

        admin = load_admin()
        if not admin:
            return jsonify({"success": False, "error": "No account registered yet"}), 400

        if email != admin["email"] or not check_password_hash(admin["password"], password):
            return jsonify({"success": False, "error": "Invalid email or password"}), 401
        otp = str(random.randint(100000, 999999))
        session['otp'] = otp
        session['otp_email'] = email

        if send_otp_email(email, otp):
            return jsonify({"success": True, "message": "OTP sent to your email"})
        return jsonify({"success": False, "error": "Failed to send OTP"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    try:
        data = request.get_json()
        entered_otp = data.get("otp").strip()

        if 'otp' not in session:
            return jsonify({"success": False, "error": "OTP expired. Please login again"}), 400

        if entered_otp != session['otp']:
            return jsonify({"success": False, "error": "Invalid OTP"}), 401

        session.pop('otp', None)
        session.pop('otp_email', None)
        session['logged_in'] = True
        return jsonify({"success": True, "message": "Login successful"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ---- dashboard -------------------------------------------------------------------------------------------------

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect('/login')

    stats = get_dashboard_stats()
    return render_template('main.html',
        total_students=stats["total"],
        paid_count=stats["paid"],
        unpaid_count=stats["unpaid"],
        total_collected=stats["collected"],
        sem_totals=stats["sem_totals"],
        course_labels=stats["course_labels"],
        course_data=stats["course_data"]
    )

# ---- page routes ------------------------------------------------------------------------------------------------------------

@app.route('/student-entry')
def student_entry():
    return render_template('entry.html')

@app.route('/student-search')
def student_search():
    return render_template('index.html')

@app.route('/update-sem-data', methods=['GET'])
def semester_data():
    return render_template('sem.html')

@app.route('/send-fee-alert')
def fee_alert():
    return render_template('fee_alert.html')

# ---- student entry -------------------------------------------------------------------------------

@app.route('/save-data', methods=['POST'])
def save_student_data():
    try:
        data = request.get_json(force=True)
        print("Received data:", data)

        fields = ["rollNo", "admissionNo", "fullName", "gender", "fatherName",
                  "motherName", "address", "email", "phone", "aadhaarNo",
                  "dob", "courseName", "admissionDate"]

        if not all(data.get(f) for f in fields):
            return jsonify({"error": "All fields are required"}), 400

        new_row = {
            "Roll No": data["rollNo"],
            "Admission No": data["admissionNo"],
            "Full Name": data["fullName"],
            "Gender": data["gender"],
            "Father Name": data["fatherName"],
            "Mother Name": data["motherName"],
            "Address": data["address"],
            "Email": data["email"],
            "Phone": data["phone"],
            "Aadhaar No": data["aadhaarNo"],
            "Date of Birth": data["dob"],
            "Course Name": data["courseName"],
            "Date of Admission": data["admissionDate"]
        }

        insert_student(new_row)
        return jsonify({"message": "Data saved successfully!"})
    except Exception as e:
        print(f"Error in save_student_data: {e}")
        return jsonify({"error": f"Error saving data. {str(e)}"}), 500

# ---- student search ------------------------------------------------------------------------------------------

@app.route('/', methods=['POST'])
def getvalue():
    name = request.form['name']
    try:
        df = read_data()

        match = (
            (df['Roll No'].astype(str).str.strip() == str(name).strip()) |
            (df['Admission No'].astype(str).str.strip() == str(name).strip()) |
            (df['Full Name'].str.strip().str.lower() == name.strip().lower())
        )

        student_details = df[match]

        if student_details.empty:
            return render_template('passno.html', z="Student not found")

        student = student_details.iloc[0]
        return render_template('pass.html',
            n="Student Found",
            na=safe_get(student, "Full Name"),
            roll=safe_get(student, "Roll No"),
            admission_no=safe_get(student, "Admission No"),
            gender=safe_get(student, "Gender"),
            father_name=safe_get(student, "Father Name"),
            mother_name=safe_get(student, "Mother Name"),
            address=safe_get(student, "Address"),
            email=safe_get(student, "Email"),
            phone=safe_get(student, "Phone"),
            aadhaar_no=safe_get(student, "Aadhaar No"),
            dob=safe_get(student, "Date of Birth"),
            course_name=safe_get(student, "Course Name"),
            admission_date=safe_get(student, "Date of Admission"),
            sem1_fee=safe_get(student, "Sem 1 Fee"),
            sem1_result=safe_get(student, "Sem 1 Result"),
            sem2_fee=safe_get(student, "Sem 2 Fee"),
            sem2_result=safe_get(student, "Sem 2 Result"),
            sem3_fee=safe_get(student, "Sem 3 Fee"),
            sem3_result=safe_get(student, "Sem 3 Result"),
            sem4_fee=safe_get(student, "Sem 4 Fee"),
            sem4_result=safe_get(student, "Sem 4 Result")
        )
    except Exception as e:
        return render_template('passno.html', n="Error Occurred", z=name)

@app.route('/get-details', methods=['POST'])
def get_details():
    try:
        data = request.get_json()
        roll_no = str(data.get("rollNo")).strip()

        df = read_data()
        student_row = df[df["Roll No"].astype(str).str.strip() == roll_no]

        if student_row.empty:
            return "Student Not Found", 404

        s = student_row.iloc[0]
        return render_template('student.html',
            n="Student Found!",
            na=s["Full Name"], roll=s["Roll No"],
            admission_no=s["Admission No"], gender=s["Gender"],
            father_name=s["Father Name"], mother_name=s["Mother Name"],
            address=s["Address"], email=s["Email"], phone=s["Phone"],
            aadhaar_no=s["Aadhaar No"], dob=s["Date of Birth"],
            course_name=s["Course Name"], admission_date=s["Date of Admission"],
            sem1_fee=s.get("Sem 1 Fee", ""), sem1_result=s.get("Sem 1 Result", ""),
            sem2_fee=s.get("Sem 2 Fee", ""), sem2_result=s.get("Sem 2 Result", ""),
            sem3_fee=s.get("Sem 3 Fee", ""), sem3_result=s.get("Sem 3 Result", ""),
            sem4_fee=s.get("Sem 4 Fee", ""), sem4_result=s.get("Sem 4 Result", "")
        )
    except Exception as e:
        return str(e), 500

@app.route('/remove-student', methods=['POST'])
def remove_student():
    try:
        data = request.get_json()
        roll_no = str(data.get("rollNo")).strip()

        if not roll_no:
            return jsonify({"success": False, "error": "Roll No is required"}), 400

        db_remove(roll_no)
        return jsonify({"success": True, "message": f"Student {roll_no} removed successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ---- semester update -------------------------------------------------------------------------------------------------

@app.route('/update-sem-data', methods=['POST'])
def update_semester_data():
    try:
        data = request.get_json(force=True)
        print("Sem update received:", data)

        roll_no = str(data.get("rollNo", "")).strip()
        semester = data.get("semester", "")
        fee = data.get("fee", "")
        result = data.get("result", "")

        if not all([roll_no, semester, fee, result]):
            return jsonify({"error": "All fields are required"}), 400

        semester = int(semester)
        fee = float(fee)

        if semester < 1 or semester > 4:
            return jsonify({"error": "Semester must be between 1 and 4"}), 400

        success = update_fee(roll_no, semester, fee, result)
        if not success:
            return jsonify({"error": "Roll No not found"}), 404

        return jsonify({"message": f"Semester {semester} data updated successfully!"})
    except ValueError as e:
        return jsonify({"error": f"Invalid number format: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---- download -------------------------------------------------------------------------------------------------

@app.route('/download-student/<roll_no>')
def download_student(roll_no):
    df = read_data()
    student = df[df["Roll No"].astype(str) == str(roll_no)]

    if student.empty:
        return "Student not found", 404

    student = student.iloc[0]
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()

    content = [Paragraph("Student Details", styles['Title']), Spacer(1, 10)]
    for col in df.columns:
        content.append(Paragraph(f"<b>{col}:</b> {student.get(col, '')}", styles['Normal']))
        content.append(Spacer(1, 5))

    doc.build(content)
    buffer.seek(0)

    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={roll_no}.pdf'
    return response

@app.route('/download-all')
def download_all_students():
    df = read_data().fillna("")
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()

    elements = [Paragraph("All Students Data", styles['Title']), Spacer(1, 10)]

    columns = ["Roll No", "Full Name", "Course Name", "Phone",
               "Sem 1 Fee", "Sem 2 Fee", "Sem 3 Fee", "Sem 4 Fee"]
    columns = [col for col in columns if col in df.columns]

    table_data = [columns]
    for _, row in df.iterrows():
        table_data.append([str(row.get(col, "")) for col in columns])

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)

    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=all_students.pdf'
    return response

# ---- fee alert --------------------------------------------------------------------------------------

def send_sms(number, message):
    try:
        payload = {
            "apiKey": os.getenv("SMS_API_KEY"),
            "recipients": [str(number)],
            "message": message
        }
        url = "https://bulkblaster-india-sms-lc-290441563653.asia-south1.run.app/send-bulk-sms"
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
        print(f"SMS Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"SMS error: {e}")
        return False

@app.route('/send-fee-alert', methods=['POST'])
def send_fee_alert():
    try:
        semester = int(request.form.get('semester').strip())
        fee_amount = float(request.form.get('fee').strip())
        due_date = request.form.get('due_date')
    except ValueError:
        return "Invalid input.", 400

    if semester < 1 or semester > 4:
        return "Semester must be between 1 and 4.", 400

    pending = get_pending_students(semester, fee_amount)

    if not pending:
        return "All students have paid. No alerts needed.", 200

    sent = 0
    failed = 0
    for s in pending:
        msg = (
            f"Dear {s['full_name']}, Sem-{semester} fee due. "
            f"Paid:Rs.{s['paid']} Balance:Rs.{round(fee_amount - s['paid'], 2)}. "
            f"Pay before {due_date}. -NIST"
        )
        if send_sms(s["phone"], msg):
            sent += 1
        else:
            failed += 1
        time.sleep(2)

    return f"Alerts sent: {sent}. Failed: {failed}."
# ---- run ------------------------------------------------------------------------------------------------

def start_flask():
    app.run(debug=True, use_reloader=False)

if __name__ == '__main__':
    t = threading.Thread(target=start_flask)
    t.daemon = True
    t.start()
    webview.start()