import logging
import mysql.connector
from fastapi.responses import JSONResponse
from passlib.context import CryptContext
from fastapi import UploadFile, File, HTTPException
from datetime import datetime
import os
import hashlib
import secrets

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def sql_connect():
    try:
        connection = mysql.connector.connect(
            host="mysql",
            port=3306,
            user="root",
            password="root",
            database="chatbot",
        )
        if connection.is_connected():
            logging.info("Connected to MySQL database")
            return connection
        else:
            logging.error("Failed to connect to the database")
            return None
    except mysql.connector.Error as e:
        logging.error(f"Database connection error: {e}")
        return None


# Initialize database on first startup
def initialize_database():
    logging.info("Checking database initialization status...")
    try:
        connection = sql_connect()
        cursor = connection.cursor()

        # Check if the professors table exists - if not, we need to initialize
        cursor.execute("SHOW TABLES LIKE 'professors'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            logging.info("First-time startup detected. Setting up database...")
            reset_database()
            logging.info("Database initialization complete.")
        else:
            logging.info("Database already initialized. Skipping setup.")
            
        return True
    except Exception as e:
        logging.error(f"Error during database initialization check: {str(e)}")
        return False
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# Database setup function
def reset_database():
    try:
        connection = sql_connect()
        cursor = connection.cursor()
        
        # Drop tables in reverse order of dependencies
        cursor.execute("DROP TABLE IF EXISTS documents")
        cursor.execute("DROP TABLE IF EXISTS classes")
        cursor.execute("DROP TABLE IF EXISTS students")
        cursor.execute("DROP TABLE IF EXISTS courses")
        cursor.execute("DROP TABLE IF EXISTS professors")
        
        # Create proffessors table
        cursor.execute("""
        CREATE TABLE professors (
            username VARCHAR(50) PRIMARY KEY,
            password VARCHAR(255) NOT NULL,
            first_name VARCHAR(50),
            last_name VARCHAR(50),
            role VARCHAR(9) DEFAULT 'professor',
            session_token VARCHAR(64) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create admin user
        hashed_password = pwd_context.hash("aperol77")
        cursor.execute("""
        INSERT INTO professors (username, password, first_name, last_name, role)
        VALUES (%s, %s, %s, %s, %s)
        """, ('kirchberg', hashed_password, 'Paul', 'Kirchberg', 'admin'))

        # Now create courses table
        cursor.execute("""
        CREATE TABLE courses (
            id VARCHAR(15) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by VARCHAR(50) NOT NULL,
            FOREIGN KEY (created_by) REFERENCES professors(username)
        )
        """)
        
        # Create default course
        cursor.execute("""
        INSERT INTO courses (id, name, created_by)
        VALUES (%s, %s, %s)
        """, ('WWI-BE122', 'Wirtschaftsinformatik - Business Engineering', 'kirchberg'))
        
        # Create remaining tables
        cursor.execute("""
        CREATE TABLE students (
            username VARCHAR(50) PRIMARY KEY,
            password VARCHAR(255) NOT NULL,
            first_name VARCHAR(50),
            last_name VARCHAR(50),
            course VARCHAR(15),
            session_token VARCHAR(64),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course) REFERENCES courses(id)
        )
        """)
        
        cursor.execute("""
        CREATE TABLE classes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            course_id VARCHAR(15) NOT NULL,
            taught_by VARCHAR(50) NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses(id),
            FOREIGN KEY (taught_by) REFERENCES professors(username)
        )
        """)
        
        cursor.execute("""
        CREATE TABLE documents (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by VARCHAR(50) NOT NULL,
            class_id INT NOT NULL,
            file_path VARCHAR(255) NOT NULL,
            file_type VARCHAR(50) NOT NULL,
            content_extracted BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (class_id) REFERENCES classes(id),
            FOREIGN KEY (created_by) REFERENCES professors(username)
        )
        """)

        cursor.execute("""
        INSERT INTO classes (name, course_id, taught_by)
            VALUES (%s, %s, %s)
            """, ('Datenbanken', 'WWI-BE122', 'kirchberg'))

        connection.commit()
        logging.info("Database reset successfully.")
        return True
    
    except mysql.connector.Error as e:
        logging.error(f"Database reset error: {e}")
        return False
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# ================================
# Authentication
# ================================

# Function to login a student
def login_student(username, password):
    connection = sql_connect()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT * FROM students WHERE username = %s", (username,))
    user = cursor.fetchone()

    if user and pwd_context.verify(password, user["password"]):
        session_token = secrets.token_hex(32)
        cursor.execute("UPDATE students SET session_token = %s WHERE username = %s", (session_token, username))
        connection.commit()
        user["session_token"] = session_token
        user["role"] = "student"
        return user

    cursor.close()
    connection.close()
    return None

# Function to login a professor
def login_professor(username, password):
    connection = sql_connect()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT * FROM professors WHERE username = %s", (username,))
    user = cursor.fetchone()

    if user and pwd_context.verify(password, user["password"]):
        session_token = secrets.token_hex(32)
        cursor.execute("UPDATE professors SET session_token = %s WHERE username = %s", (session_token, username))
        connection.commit()
        user["session_token"] = session_token
        # No need to add a default role - use database role as is
        return user

    cursor.close()
    connection.close()
    return None

# Register a new student
def register_student(student_data):
    try:
        required_fields = ["username", "password", "first_name", "last_name"]
        for field in required_fields:
            if field not in student_data or not student_data[field]:
                raise HTTPException(status_code=400, detail=f"Pflichtfeld fehlt: {field}")
        
        username = student_data["username"]
        password = pwd_context.hash(student_data["password"])
        first_name = student_data["first_name"]
        last_name = student_data["last_name"]
        course_id = student_data["course_id"]
        created_at = datetime.now()

        connection = sql_connect()
        cursor = connection.cursor(dictionary=True)

        # Check for duplicate username
        cursor.execute("SELECT * FROM students WHERE username = %s", (username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Benutzername bereits vergeben.")

        # Insert new student
        query = """
            INSERT INTO students (username, password, first_name, last_name, course, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (username, password, first_name, last_name, course_id, created_at))
        connection.commit()

        return {
            "id": cursor.lastrowid,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "role": "student"
        }

    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

            
# Authentication function to get user by session token
def get_user_by_session(session_token):
    """Get user by session token"""
    if not session_token:
        return None
    
    connection = None
    cursor = None
    try:
        connection = sql_connect()
        if not connection:
            return None
        
        cursor = connection.cursor(dictionary=True)
        
        # Check for professor first - KEEP THE ORIGINAL ROLE FROM DATABASE
        cursor.execute("SELECT * FROM professors WHERE session_token = %s", (session_token,))
        user = cursor.fetchone()
        
        # If not found, check students
        if not user:
            cursor.execute("SELECT *, 'student' as role FROM students WHERE session_token = %s", (session_token,))
            user = cursor.fetchone()
        
        return user
    
    except Exception as e:
        logging.error(f"Error retrieving user by session: {str(e)}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# Function to check if a professor is assigned to a course
def is_professor_for_course(professor_username, course_id):
    """Check if a user is a professor for a specific course"""
    try:
        connection = sql_connect()
        if not connection:
            return False
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT 1 FROM classes 
            WHERE course_id = %s AND taught_by = %s
        """, (course_id, professor_username))
        
        result = cursor.fetchone() is not None
        
        cursor.close()
        connection.close()
        
        return result
    
    except Exception as e:
        logging.error(f"Error checking professor course assignment: {str(e)}")
        return False

# Get all courses
def get_courses():
    try:
        connection = sql_connect()
        if not connection:
            return {"courses": []}
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, name FROM courses")
        courses = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return {"courses": courses}
    
    except Exception as e:
        logging.error(f"Error fetching courses: {str(e)}")
        return {"courses": []}
    

# ================================
# Professors
# ================================

def get_all_professors_with_courses():
    """Get all professors with their assigned courses"""
    connection = None
    cursor = None
    professors_list = []
    
    try:
        connection = sql_connect()
        cursor = connection.cursor(dictionary=True)
        
        # Get all professors
        cursor.execute("""
            SELECT username, first_name, last_name, role 
            FROM professors
            ORDER BY last_name, first_name
        """)
        professors = cursor.fetchall()
        
        # For each professor, get their courses through the classes table
        for professor in professors:
            professor_username = professor['username']
            
            # Get courses for this professor using the classes table
            cursor.execute("""
                SELECT c.id, c.name 
                FROM courses c
                JOIN classes cls ON c.id = cls.course_id
                WHERE cls.taught_by = %s
                GROUP BY c.id, c.name
                ORDER BY c.name
            """, (professor_username,))
            courses = cursor.fetchall()
            
            # Add professor with their courses to the list
            professors_list.append({
                'username': professor['username'],
                'name': f"{professor['first_name']} {professor['last_name']}",
                'role': professor['role'],
                'courses': courses
            })
        
        return professors_list
    
    except Exception as e:
        logging.error(f"Error getting professors with courses: {str(e)}")
        return []
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def add_professor(professor_data):
    """Add a new professor or admin"""
    connection = None
    cursor = None
    try:
        connection = sql_connect()
        cursor = connection.cursor(dictionary=True)

        # Check if username already exists
        cursor.execute("SELECT * FROM professors WHERE username = %s", (professor_data['username'],))
        if cursor.fetchone():
            return False, "Benutzername existiert bereits"

        # Hash password
        password_hash = pwd_context.hash(professor_data['password'])

        # Insert professor/admin
        cursor.execute("""
            INSERT INTO professors (username, password, first_name, last_name, role)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            professor_data['username'],
            password_hash,
            professor_data['first_name'],
            professor_data['last_name'],
            professor_data['role']
        ))

        connection.commit()
        return True, "Professor erfolgreich hinzugefügt"
    except Exception as e:
        logging.error(f"Error adding professor: {str(e)}")
        return False, f"Fehler beim Hinzufügen: {str(e)}"
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def delete_professor(professor_username):
    """Delete a professor"""
    connection = None
    cursor = None
    
    try:
        connection = sql_connect()
        cursor = connection.cursor()
        
        # First check if the professor teaches any classes
        cursor.execute("SELECT COUNT(*) FROM classes WHERE taught_by = %s", (professor_username,))
        class_count = cursor.fetchone()[0]
        if class_count > 0:
            return False, "Professor kann nicht gelöscht werden, da noch Kurse zugeordnet sind"
        
        # Delete the professor (no professor_courses table in schema)
        cursor.execute("DELETE FROM professors WHERE username = %s", (professor_username,))
        
        if cursor.rowcount == 0:
            return False, "Professor nicht gefunden"
        
        connection.commit()
        return True, "Professor erfolgreich gelöscht"
    
    except Exception as e:
        logging.error(f"Error deleting professor: {str(e)}")
        return False, f"Fehler beim Löschen: {str(e)}"
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ===============================
# Courses
# ===============================

def get_course_by_id(course_id):
    connection = sql_connect()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM courses WHERE id = %s", (course_id,))
    course = cursor.fetchone()
    cursor.close()
    connection.close()
    return course

def get_class_by_course_and_professor(course_id, professor_username):
    connection = sql_connect()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        "SELECT id FROM classes WHERE course_id = %s AND taught_by = %s",
        (course_id, professor_username)
    )
    cls = cursor.fetchone()
    cursor.close()
    connection.close()
    return cls

def get_courses_for_user(user):
    """Return a list of courses/classes for the given user based on their role."""
    connection = sql_connect()
    cursor = connection.cursor(dictionary=True)
    courses = []

    try:
        if user.get("role") == "admin":
            cursor.execute("""
                SELECT c.id, c.name, c.id as code,
                    CONCAT(p.first_name, ' ', p.last_name) as professor_name
                FROM courses c
                LEFT JOIN classes cls ON c.id = cls.course_id
                LEFT JOIN professors p ON cls.taught_by = p.username
                GROUP BY c.id, c.name, p.first_name, p.last_name
            """)
            courses = cursor.fetchall()
        elif user.get("role") == "professor":
            cursor.execute("""
                SELECT c.id, c.name, c.id as code
                FROM courses c
                JOIN classes cls ON c.id = cls.course_id
                WHERE cls.taught_by = %s
                GROUP BY c.id, c.name
            """, (user["username"],))
            courses = cursor.fetchall()
        elif user.get("role") == "student":
            cursor.execute("""
                SELECT c.id, c.name, c.id as code
                FROM courses c
                JOIN students s ON s.course = c.id
                WHERE s.username = %s
            """, (user["username"],))
            courses = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()
    return courses


# ===============================
# Classes
# ===============================

# Class retrieval function
def get_all_classes():
    """Return all classes with course and professor info."""
    connection = sql_connect()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT 
                cls.id, 
                cls.name, 
                cls.created_at, 
                cls.course_id as code,
                c.name as course_name,
                CONCAT(p.first_name, ' ', p.last_name) as professor_name
            FROM classes cls
            LEFT JOIN courses c ON cls.course_id = c.id
            LEFT JOIN professors p ON cls.taught_by = p.username
            ORDER BY cls.name
        """)
        classes = cursor.fetchall()
        return classes
    finally:
        cursor.close()
        connection.close()

def get_class_by_id(class_id):
    """Retrieve a class by its ID."""
    connection = sql_connect()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            cls.id, 
            cls.name, 
            cls.created_at, 
            cls.course_id, 
            c.name as course_name,
            CONCAT(p.first_name, ' ', p.last_name) as professor_name
        FROM classes cls
        LEFT JOIN courses c ON cls.course_id = c.id
        LEFT JOIN professors p ON cls.taught_by = p.username
        WHERE cls.id = %s
    """, (class_id,))
    cls = cursor.fetchone()
    cursor.close()
    connection.close()
    return cls

def get_classes_for_student(student_username):
    """Return all classes for a given student (based on their course)"""
    connection = sql_connect()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT 
                cls.id, 
                cls.name, 
                cls.created_at, 
                cls.course_id as code,
                c.name as course_name,
                CONCAT(p.first_name, ' ', p.last_name) as professor_name
            FROM students s
            JOIN classes cls ON s.course = cls.course_id
            LEFT JOIN courses c ON cls.course_id = c.id
            LEFT JOIN professors p ON cls.taught_by = p.username
            WHERE s.username = %s
            ORDER BY cls.name
        """, (student_username,))
        classes = cursor.fetchall()
        return classes
    finally:
        cursor.close()
        connection.close()

def get_classes_for_professor(professor_username):
    """Return all classes taught by a given professor"""
    connection = sql_connect()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT 
                cls.id, 
                cls.name, 
                cls.created_at, 
                cls.course_id as code,
                c.name as course_name,
                CONCAT(p.first_name, ' ', p.last_name) as professor_name
            FROM classes cls
            LEFT JOIN courses c ON cls.course_id = c.id
            LEFT JOIN professors p ON cls.taught_by = p.username
            WHERE cls.taught_by = %s
            ORDER BY cls.name
        """, (professor_username,))
        classes = cursor.fetchall()
        return classes
    finally:
        cursor.close()
        connection.close()

def add_class(class_data):
    """Add a new class (Vorlesung) to the database."""
    connection = None
    cursor = None
    try:
        connection = sql_connect()
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO classes (name, course_id, taught_by)
            VALUES (%s, %s, %s)
        """, (
            class_data["name"],
            class_data["course_id"],
            class_data["taught_by"]
        ))
        connection.commit()
        return True, "Vorlesung erfolgreich hinzugefügt."
    except Exception as e:
        logging.error(f"Error adding class: {str(e)}")
        return False, f"Fehler beim Hinzufügen: {str(e)}"
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def delete_class(class_id):
    """Delete a class (Vorlesung) and its documents from the database."""
    connection = sql_connect()
    cursor = connection.cursor()
    try:
        # Optionally delete documents first if ON DELETE CASCADE is not set
        cursor.execute("DELETE FROM documents WHERE class_id = %s", (class_id,))
        cursor.execute("DELETE FROM classes WHERE id = %s", (class_id,))
        connection.commit()
        return True, "Vorlesung erfolgreich gelöscht."
    except Exception as e:
        logging.error(f"Error deleting class: {str(e)}")
        return False, f"Fehler beim Löschen: {str(e)}"
    finally:
        cursor.close()
        connection.close()


# ===============================
# PDFs
# ===============================

def get_pdfs_for_class(class_id):
    """Get all PDFs for a given class."""
    connection = sql_connect()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT d.id, d.name, d.created_by, d.created_at as uploaded_at, d.file_path, d.file_type
        FROM documents d
        WHERE d.class_id = %s
        ORDER BY d.created_at DESC
    """, (class_id,))
    pdfs = cursor.fetchall()
    cursor.close()
    connection.close()
    return pdfs

def add_document(document_data, file_content):
    connection = None
    cursor = None
    try:
        connection = sql_connect()
        cursor = connection.cursor()

        upload_dir = os.path.join(os.getcwd(), 'uploads')
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)

        filename = document_data['name']
        file_path = os.path.join(upload_dir, filename)

        # Save file to disk
        with open(file_path, 'wb') as f:
            f.write(file_content)

        # Insert document record into database
        cursor.execute("""
            INSERT INTO documents (name, created_by, class_id, file_path, file_type, content_extracted)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            filename,
            document_data['created_by'],
            document_data['class_id'],
            filename,  # Store just the filename
            document_data['file_type'],
            False
        ))
        connection.commit()
        return True, cursor.lastrowid
    except Exception as e:
        logging.error(f"Error adding document: {str(e)}")
        return False, f"Fehler beim Hinzufügen des Dokuments: {str(e)}"
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def delete_pdf(pdf_id):
    """Delete a PDF document and its file."""
    connection = sql_connect()
    cursor = connection.cursor(dictionary=True)
    # Get file path
    cursor.execute("SELECT file_path FROM documents WHERE id=%s", (pdf_id,))
    doc = cursor.fetchone()
    if doc and doc["file_path"]:
        file_path = os.path.join(os.getcwd(), 'uploads', doc["file_path"])
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            # Optionally log the error
            print(f"Error deleting file: {e}")
    # Delete from DB
    cursor.execute("DELETE FROM documents WHERE id=%s", (pdf_id,))
    connection.commit()
    cursor.close()
    connection.close()
    return True

def get_class_id_by_pdf(pdf_id):
    """Get the class_id for a given PDF/document."""
    connection = sql_connect()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT class_id FROM documents WHERE id=%s", (pdf_id,))
    doc = cursor.fetchone()
    cursor.close()
    connection.close()
    return doc["class_id"] if doc else None


def get_all_courses():
    conn = sql_connect()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM courses")
    courses = cursor.fetchall()
    cursor.close()
    conn.close()
    return courses

def add_course(course_data):
    conn = sql_connect()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO courses (id, name, created_by) VALUES (%s, %s, %s)", 
                       (course_data["id"], course_data["name"], course_data["created_by"]))
        conn.commit()
        return True, "Kurs hinzugefügt"
    except Exception as e:
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def delete_course(course_id):
    conn = sql_connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM courses WHERE id = %s", (course_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return True, "Kurs gelöscht"

def get_course_by_id(course_id):
    conn = sql_connect()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM courses WHERE id = %s", (course_id,))
    course = cursor.fetchone()
    cursor.close()
    conn.close()
    return course

def update_course(course_id, name):
    conn = sql_connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE courses SET name = %s WHERE id = %s", (name, course_id))
    conn.commit()
    cursor.close()
    conn.close()



# STUDENT

def anonymize_username(username):
    # Nutzt SHA1-Hash (alternativ SHA256)
    return hashlib.sha1(username.encode()).hexdigest()[:10] 

def get_all_students():
    connection = sql_connect()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT username, course FROM students")
    students = cursor.fetchall()
    cursor.close()
    connection.close()

    # Benutzername hashen für Admin-Anzeige
    for student in students:
        student["anonymized"] = anonymize_username(student["username"])
    return students




def count_prompts_by_user(username):
    connection = sql_connect()
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM chat_history WHERE user = %s", (username,))
    count = cursor.fetchone()[0]
    cursor.close()
    connection.close()
    return count


