from flask import Flask, render_template, request, redirect, session, url_for
import mysql.connector
import os

# CHANGED: Added paths for templates and static so Vercel can find them from the /api folder
app = Flask(__name__, 
            template_folder='../templates', 
            static_folder='../static')

app.secret_key = "excuse_letter_system_2026"

# DATABASE CONFIGURATION (AIVEN)

base_dir = os.path.dirname(os.path.abspath(__file__))
ca_path = os.path.join(base_dir, '../ca.pem')

db_config = {
    'host': 'mysql-2c6e793b-marycatherinemanalo2006-daba.h.aivencloud.com',
    'user': 'avnadmin',
    'password': 'AVNS_ER_dWiJsxf0SgQOJax4',
    'port': 12484,
    'database': 'student_attendance_db',
    'ssl_ca': ca_path
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

def seed_data():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        print("Connecting to database for seeding...")

        programs = ["BPA", "BSCS", "BSCRIM", "BSMA"]
        for p in programs:
            cursor.execute("INSERT IGNORE INTO programs (program_name) VALUES (%s)", (p,))

        years = ['1st', '2nd', '3rd', '4th']
        for y in years:
            cursor.execute("INSERT IGNORE INTO year_levels (year_level) VALUES (%s)", (y,))

        cursor.execute("SELECT COUNT(*) FROM sections")
        if cursor.fetchone()[0] == 0:
            for program_name in programs:
                for year in years:
                    year_num = year[0]
                    for letter in ['A', 'B', 'C', 'D', 'E', 'F']:
                        full_section_name = f"{year_num}{letter}"
                        cursor.execute("""
                            INSERT IGNORE INTO sections (section_name, year_level, program_name)
                            VALUES (%s, %s, %s)
                        """, (full_section_name, year, program_name))

        cursor.execute("INSERT IGNORE INTO users (username, password, role) VALUES (%s, %s, %s)", ("admin", "123", "admin"))
        conn.commit()
        print("Database seeded successfully!")
    except Exception as e:
        print(f"Error during seeding: {e}")
    finally:
        cursor.close()
        conn.close()

# ROUTES

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('admin' if session.get('user') == 'admin' else 'dashboard'))
     
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE username=%s AND password=%s", (username, password))
        user = cursor.fetchone()
        cursor.close(); conn.close()
        if user:
            session['username'] = username
            session['user'] = user[0]
            return redirect(url_for('admin' if user[0] == "admin" else 'dashboard'))
        return render_template('login.html', error="Invalid credentials!")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        program_name = request.form['program']
        year_level = request.form['year_level']
        section_name = request.form['section']
        
        # ADDED: Profile Picture Handling
        profile_pic = "default_user.png"
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file.filename != '':
                upload_folder = os.path.join(base_dir, '../static/uploads')
                os.makedirs(upload_folder, exist_ok=True)
                filename = f"user_{username}_{file.filename}"
                file.save(os.path.join(upload_folder, filename))
                profile_pic = filename

        year_map = {"1": "1st", "2": "2nd", "3": "3rd", "4": "4th"}
        year_text = year_map.get(year_level, year_level)

        cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
        if cursor.fetchone():
            return "User already exists!"

        # UPDATED: Insert profile_pic
        cursor.execute("""
            INSERT INTO users (username, password, role, program_name, year_level, section_name, profile_pic)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (username, password, "student", program_name, year_text, section_name, profile_pic))
        conn.commit()
        cursor.close(); conn.close()
        return redirect(url_for('login'))

    cursor.execute("SELECT * FROM programs")
    progs = cursor.fetchall()
    cursor.execute("SELECT * FROM year_levels")
    yrs = cursor.fetchall()
    cursor.execute("SELECT * FROM sections") 
    sects = cursor.fetchall()
    
    cursor.close(); conn.close()
    return render_template('register.html', programs=progs, year_levels=yrs, sections=sects)

@app.route('/dashboard')
def dashboard():
    if session.get('user') != "student": return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # UPDATED: Select profile_pic
    cursor.execute("SELECT program_name, section_name, profile_pic FROM users WHERE username=%s", (session['username'],))
    student = cursor.fetchone()
    cursor.close(); conn.close()
    return render_template('dashboard.html', 
                           program=student['program_name'], 
                           section=student['section_name'], 
                           profile_pic=student.get('profile_pic', 'default_user.png'))

@app.route('/submit_excuse', methods=['GET', 'POST'])
def submit_excuse():
    if session.get('user') != "student": return redirect(url_for('login'))
    student_name = session.get('username')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        absence_date = request.form['absence_date']
        reason = request.form['reason']
        file = request.files['proof']
        filename = file.filename
        if filename != "":
            upload_folder = os.path.join(base_dir, '../static/uploads')
            os.makedirs(upload_folder, exist_ok=True)
            file.save(os.path.join(upload_folder, filename))

        cursor.execute("SELECT section_name FROM users WHERE username=%s", (student_name,))
        sec = cursor.fetchone()['section_name']
        cursor.execute("""
            INSERT INTO excuse_letters (student_name, section, absence_date, reason, proof_file)
            VALUES (%s, %s, %s, %s, %s)
        """, (student_name, sec, absence_date, reason, filename))
        conn.commit()
        cursor.close(); conn.close()
        return redirect(url_for('dashboard'))

    cursor.execute("SELECT program_name, section_name FROM users WHERE username=%s", (student_name,))
    student_data = cursor.fetchone()
    cursor.close(); conn.close()
    return render_template('submit_excuse.html', **student_data)

@app.route('/admin')
def admin():
    if session.get('user') != "admin": return redirect(url_for('login'))
    p_filter = request.args.get('program', '')
    s_filter = request.args.get('section', '')
    conn = get_db_connection()
    cursor = conn.cursor() 

    cursor.execute("SELECT program_name FROM programs ORDER BY program_name")
    programs = cursor.fetchall()

    # UPDATED: Join with users to get u.profile_pic
    query = """
        SELECT e.id, e.student_name, u.program_name, e.section, e.status, u.profile_pic 
        FROM excuse_letters e 
        LEFT JOIN users u ON e.student_name = u.username 
        WHERE 1=1
    """
    params = []
    if p_filter: query += " AND u.program_name=%s"; params.append(p_filter)
    if s_filter: query += " AND e.section=%s"; params.append(s_filter)
    cursor.execute(query, params)
    letters = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM excuse_letters WHERE status='Pending'")
    p = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM excuse_letters WHERE status='Approved'")
    a = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM excuse_letters WHERE status='Rejected'")
    r = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM excuse_letters")
    t = cursor.fetchone()[0]
    cursor.close(); conn.close()
    return render_template('admin.html', letters=letters, programs=programs, 
                           selected_program=p_filter, selected_section=s_filter,
                           pending=p, approved=a, rejected=r, total=t)

@app.route('/view_excuse/<int:id>', methods=['GET', 'POST'])
def view_excuse(id):
    if session.get('user') != "admin": return redirect(url_for('login'))
    conn = get_db_connection(); cursor = conn.cursor()
    # UPDATED: Join with users to get profile_pic
    cursor.execute("""
        SELECT e.*, u.profile_pic 
        FROM excuse_letters e 
        JOIN users u ON e.student_name = u.username 
        WHERE e.id=%s
    """, (id,))
    letter = cursor.fetchone()
    cursor.close(); conn.close()
    return render_template('view_excuse.html', letter=letter)

@app.route('/approve/<int:id>', methods=['POST'])
def approve(id):
    if session.get('user') != "admin": return redirect(url_for('login'))
    com = request.form.get("admin_comment")
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("UPDATE excuse_letters SET status='Approved', admin_comment=%s WHERE id=%s", (com, id))
    conn.commit(); cursor.close(); conn.close()
    return redirect(url_for('admin'))

@app.route('/reject/<int:id>', methods=['POST'])
def reject(id):
    if session.get('user') != "admin": return redirect(url_for('login'))
    com = request.form.get("admin_comment")
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("UPDATE excuse_letters SET status='Rejected', admin_comment=%s WHERE id=%s", (com, id))
    conn.commit(); cursor.close(); conn.close()
    return redirect(url_for('admin'))

@app.route('/delete_excuse/<int:id>')
def delete_excuse(id):
    if session.get('user') != "admin": return redirect(url_for('login'))
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("DELETE FROM excuse_letters WHERE id=%s", (id,))
    conn.commit(); cursor.close(); conn.close()
    return redirect(url_for('admin'))

@app.route('/my_excuses')
def my_excuses():
    if session.get('user') != "student": return redirect(url_for('login'))
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("UPDATE excuse_letters SET is_read=1 WHERE student_name=%s AND status != 'Pending'", (session['username'],))
    conn.commit()
    cursor.execute("SELECT * FROM excuse_letters WHERE student_name=%s", (session['username'],))
    letters = cursor.fetchall()
    cursor.close(); conn.close()
    return render_template('my_excuses.html', letters=letters)

@app.route('/student_excuse/<int:id>')
def student_excuse(id):
    if session.get('user') != "student": return redirect(url_for('login'))
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM excuse_letters WHERE id=%s", (id,))
    letter = cursor.fetchone()
    cursor.close(); conn.close()
    return render_template('student_excuse.html', letter=letter)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.context_processor
def inject_notifications():
    if session.get('user') == 'student':
        try:
            conn = get_db_connection(); cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM excuse_letters WHERE student_name=%s AND status != 'Pending' AND is_read=0", (session['username'],))
            c = cursor.fetchone()[0]
            cursor.close(); conn.close()
            return dict(notify_count=c)
        except: return dict(notify_count=0)
    return dict(notify_count=0)

if __name__ == '__main__':
    app.run(debug=True)
