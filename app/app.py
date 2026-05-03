from flask import Flask, render_template, request
import pandas as pd
import mysql.connector
from flask import request
from flask import redirect, url_for, flash
app = Flask(__name__)
app.secret_key = "secret123"

from flask import request

@app.route('/')
def home():
    conn = get_db_connection()
    cursor = conn.cursor()

    grade = request.args.get('grade')
    year = request.args.get('year')

    base_query = """
        FROM students s
        JOIN student_records r ON s.lrn = r.lrn
        WHERE 1=1
    """

    params = []

    if grade:
        base_query += " AND r.grade_level = %s"
        params.append(grade)

    if year:
        base_query += " AND r.school_year = %s"
        params.append(year)

    # GET STUDENTS
    cursor.execute("SELECT s.lrn, s.name, r.gender " + base_query, params)
    students = cursor.fetchall()

    # METRICS
    cursor.execute("""
        SELECT 
            COUNT(*),
            SUM(CASE WHEN UPPER(r.gender) LIKE 'M%' THEN 1 ELSE 0 END),
            SUM(CASE WHEN UPPER(r.gender) LIKE 'F%' THEN 1 ELSE 0 END)
    """ + base_query, params)

    result = cursor.fetchone()

    total = result[0]
    male = result[1] or 0
    female = result[2] or 0

    male_pct = round((male / total) * 100, 2) if total > 0 else 0
    female_pct = round((female / total) * 100, 2) if total > 0 else 0

    cursor.close()
    conn.close()

    try:
        retention = compute_retention("2024-2025", "2025-2026")
    except:
        retention = {"rate": 0, "retained": 0, "dropped": 0}

    return render_template(
        "index.html",
        students=students,
        total=total,
        male=male,
        female=female,
        male_pct=male_pct,
        female_pct=female_pct,
        retention=retention
    )

def get_metrics():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM students")
    total = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return total

def compute_retention(year1, year2):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Retained (intersection)
    cursor.execute("""
        SELECT COUNT(*) 
        FROM student_records r1
        JOIN student_records r2 
        ON r1.lrn = r2.lrn
        WHERE r1.school_year = %s
        AND r2.school_year = %s
    """, (year1, year2))

    retained = cursor.fetchone()[0]

    # Total in year1
    cursor.execute("""
        SELECT COUNT(DISTINCT lrn)
        FROM student_records
        WHERE school_year = %s
    """, (year1,))

    total_year1 = cursor.fetchone()[0]

    dropped = total_year1 - retained

    retention_rate = (retained / total_year1 * 100) if total_year1 > 0 else 0

    cursor.close()
    conn.close()

    return {
        "retained": retained,
        "dropped": dropped,
        "rate": round(retention_rate, 2)
    }

@app.route('/upload', methods=['POST'])
def upload():
    try:
        file = request.files['file']

        school_year = request.form.get('school_year')
        grade_level = request.form.get('grade_level')

        if not file:
            return "No file uploaded"

        df = pd.read_excel(file, header=None)

        # Skip header rows
        df = df.iloc[6:]

        # Drop empty columns
        df = df.dropna(axis=1, how='all')

        # Reset column index
        df.columns = range(df.shape[1])

        print("\n===== DATA SAMPLE =====")
        print(df.head())

        # 🧠 Detect columns dynamically
        lrn_col = None
        name_col = None
        sex_col = None

        for col in df.columns:
            col_data = df[col].astype(str)

            if col_data.str.match(r'^\d{10,}$').any():
                lrn_col = col

            if col_data.str.contains(',').any():
                name_col = col

            if col_data.str.upper().isin(['M', 'F']).any():
                sex_col = col

        print("LRN COL:", lrn_col)
        print("NAME COL:", name_col)
        print("SEX COL:", sex_col)

        # ❌ Stop if detection failed
        if lrn_col is None or name_col is None or sex_col is None:
            return "Column detection failed. Check Excel format."

        # ✅ Rename columns
        df = df.rename(columns={
            lrn_col: 'LRN',
            name_col: 'NAME',
            sex_col: 'SEX'
        })

        # Keep only needed columns
        df = df[['LRN', 'NAME', 'SEX']]

        # Clean data
        df = df.dropna(subset=['LRN'])
        df = df[df['LRN'].astype(str).str.isnumeric()]
        df = df[df['NAME'].notna()]

        print("\n===== CLEAN DATA =====")
        print(df.head(10))

        conn = get_db_connection()
        cursor = conn.cursor()

        inserted = 0

        for _, row in df.iterrows():
            lrn = str(row['LRN']).strip()
            name = str(row['NAME']).strip()
            gender = str(row['SEX']).strip().upper()

            # Normalize gender
            if gender.startswith('M'):
                gender = 'MALE'
            elif gender.startswith('F'):
                gender = 'FEMALE'
            else:
                gender = 'UNKNOWN'

            print("INSERTING:", lrn, name, gender)

            cursor.execute("""
                INSERT IGNORE INTO students (lrn, name)
                VALUES (%s, %s)
            """, (lrn, name))

            cursor.execute("""
            INSERT INTO student_records (lrn, school_year, grade_level, gender, status)
            VALUES (%s, %s, %s, %s, %s)
            """, (lrn, school_year, grade_level, gender, "ENROLLED"))

        conn.commit()
        cursor.close()
        conn.close()

        flash(f"{inserted} students imported successfully!")
        return redirect(url_for('home'))

    except Exception as e:
        print("\nERROR:", str(e))
        return f"Error occurred: {str(e)}"

def get_db_connection():
    return mysql.connector.connect(
        host="db",   
        user="root",
        password="root",
        database="mydb"
    )