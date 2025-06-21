import logging
from typing import List
import mysql.connector
from fastapi.responses import JSONResponse
from passlib.context import CryptContext
from fastapi import UploadFile, File, HTTPException
from datetime import datetime
import os
import hashlib
import secrets
import json

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
        
        # Drop tables in reverse order of dependencies - add the new junction table
        cursor.execute("DROP TABLE IF EXISTS chat_history")
        cursor.execute("DROP TABLE IF EXISTS class_courses")
        cursor.execute("DROP TABLE IF EXISTS documents")
        cursor.execute("DROP TABLE IF EXISTS classes")
        cursor.execute("DROP TABLE IF EXISTS students")
        cursor.execute("DROP TABLE IF EXISTS courses")
        cursor.execute("DROP TABLE IF EXISTS professors")
        
        # Create proffessors table - unchanged
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
        
        # Create admin user - unchanged
        hashed_password = pwd_context.hash("aperol77")
        cursor.execute("""
        INSERT INTO professors (username, password, first_name, last_name, role)
        VALUES (%s, %s, %s, %s, %s)
        """, ('kirchberg', hashed_password, 'Paul', 'Kirchberg', 'admin'))

        # Create courses table - unchanged
        cursor.execute("""
        CREATE TABLE courses (
            id VARCHAR(15) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by VARCHAR(50) NOT NULL,
            FOREIGN KEY (created_by) REFERENCES professors(username)
        )
        """)
        
        # Create default course - unchanged
        cursor.execute("""
        INSERT INTO courses (id, name, created_by)
        VALUES (%s, %s, %s)
        """, ('WWI-BE122', 'Wirtschaftsinformatik - Business Engineering', 'kirchberg'))
        
        # Create students table - unchanged
        cursor.execute("""
        CREATE TABLE students (
            username VARCHAR(50) PRIMARY KEY,
            password VARCHAR(255) NOT NULL,
            course VARCHAR(15),
            session_token VARCHAR(64),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course) REFERENCES courses(id)
        )
        """)
        
        # Modified classes table - removed course_id field
        cursor.execute("""
        CREATE TABLE classes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            taught_by VARCHAR(50) NOT NULL,
            FOREIGN KEY (taught_by) REFERENCES professors(username)
        )
        """)
        
        # New junction table for many-to-many relationship
        cursor.execute("""
        CREATE TABLE class_courses (
            class_id INT,
            course_id VARCHAR(15),
            PRIMARY KEY (class_id, course_id),
            FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
        )
        """)
        
        # Documents table - unchanged
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
        CREATE TABLE chat_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_hash VARCHAR(40) NOT NULL,  # Anonymized user identifier
            class_id INT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
        )
        """)

        # Insert default class without course_id
        cursor.execute("""
        INSERT INTO classes (name, taught_by)
        VALUES (%s, %s)
        """, ('Datenbanken', 'kirchberg'))
        
        # Get the inserted class ID
        class_id = cursor.lastrowid
        
        # Associate the class with the default course
        cursor.execute("""
        INSERT INTO class_courses (class_id, course_id)
        VALUES (%s, %s)
        """, (class_id, 'WWI-BE122'))

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
        required_fields = ["username", "password"]
        for field in required_fields:
            if field not in student_data or not student_data[field]:
                raise HTTPException(status_code=400, detail=f"Pflichtfeld fehlt: {field}")
        
        username = student_data["username"]
        password = pwd_context.hash(student_data["password"])
        course_id = student_data["course_id"]
        created_at = datetime.now()
        
    

        connection = sql_connect()
        cursor = connection.cursor(dictionary=True)

        # Check for duplicate username
        cursor.execute("SELECT * FROM students WHERE username = %s", (username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Benutzername bereits vergeben.")

        # Insert new student with security answers
        query = """
            INSERT INTO students (username, password, course, created_at)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (username, password, course_id, created_at))
        connection.commit()

        return {
            "id": cursor.lastrowid,
            "username": username,
            "role": "student"
        }

    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# def verify_student_security_answers(username, answers):
#     """Verify a student's security answers"""
#     connection = None
#     cursor = None
#     try:
#         connection = sql_connect()
#         cursor = connection.cursor(dictionary=True)
        
#         # Get the student's stored security answers
#         cursor.execute("SELECT security_answer1, security_answer2, security_answer3 FROM students WHERE username = %s", 
#                       (username,))
#         student = cursor.fetchone()
        
#         if not student:
#             return False, "Student not found"
        
#         # Check if any answers are missing
#         if not all([student['security_answer1'], student['security_answer2'], student['security_answer3']]):
#             return False, "Security answers not set up for this student"
        
#         # Verify each answer
#         is_valid = (
#             pwd_context.verify(answers[0], student['security_answer1']) and
#             pwd_context.verify(answers[1], student['security_answer2']) and
#             pwd_context.verify(answers[2], student['security_answer3'])
#         )
        
#         if is_valid:
#             return True, "Security answers verified"
#         else:
#             return False, "Incorrect security answers"
            
#     except Exception as e:
#         logging.error(f"Error verifying security answers: {str(e)}")
#         return False, f"Error: {str(e)}"
#     finally:
#         if cursor:
#             cursor.close()
#         if connection:
#             connection.close()

# def reset_student_password(username, new_password):
#     """Reset a student's password after security verification"""
#     connection = None
#     cursor = None
#     try:
#         connection = sql_connect()
#         cursor = connection.cursor()
        
#         # Hash the new password
#         password_hash = pwd_context.hash(new_password)
        
#         # Update the student's password
#         cursor.execute("UPDATE students SET password = %s WHERE username = %s", 
#                       (password_hash, username))
        
#         connection.commit()
        
#         if cursor.rowcount > 0:
#             return True, "Password reset successfully"
#         else:
#             return False, "Student not found"
            
#     except Exception as e:
#         logging.error(f"Error resetting password: {str(e)}")
#         return False, f"Error: {str(e)}"
#     finally:
#         if cursor:
#             cursor.close()
#         if connection:
#             connection.close()

            
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

def login_student(username, password):
    """Login a student with username and password"""
    connection = sql_connect()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT * FROM students WHERE username = %s", (username,))
    user = cursor.fetchone()

    if user and pwd_context.verify(password, user["password"]):
        session_token = secrets.token_hex(32)
        cursor.execute("UPDATE students SET session_token = %s WHERE username = %s", (session_token, username))
        connection.commit()
        user["session_token"] = session_token
        user["role"] = "student"  # Add role since it's not in students table
        return user

    cursor.close()
    connection.close()
    return None

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

def get_all_professors():
    connection = sql_connect()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT username, first_name, last_name FROM professors")
    professors = cursor.fetchall()
    cursor.close()
    connection.close()
    return [
        {
            "username": prof["username"],
            "name": f"{prof['first_name']} {prof['last_name']}"
        }
        for prof in professors
    ]

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
            
            # Get courses for this professor using the junction table
            cursor.execute("""
                SELECT c.id, c.name 
                FROM courses c
                JOIN class_courses cc ON c.id = cc.course_id
                JOIN classes cls ON cc.class_id = cls.id
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
        return True, "Benutzer erfolgreich hinzugefügt."
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
            return False, "Professor kann nicht gelöscht werden, da noch Kurse zugeordnet sind."
        
        # Delete the professor (no professor_courses table in schema)
        cursor.execute("DELETE FROM professors WHERE username = %s", (professor_username,))
        
        if cursor.rowcount == 0:
            return False, "Professor nicht gefunden."
        
        connection.commit()
        return True, "Benutzer erfolgreich gelöscht."
    
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
                CONCAT(p.first_name, ' ', p.last_name) as professor_name,
                cls.taught_by as professor_username
            FROM classes cls
            LEFT JOIN professors p ON cls.taught_by = p.username
            ORDER BY cls.name
        """)
        classes = cursor.fetchall()
        
        # For each class, get its associated courses
        for cls in classes:
            cursor.execute("""
                SELECT c.id as code, c.name as course_name 
                FROM courses c
                JOIN class_courses cc ON c.id = cc.course_id
                WHERE cc.class_id = %s
            """, (cls['id'],))
            courses = cursor.fetchall()
            
            # Add the courses to the class
            cls['courses'] = courses

            

            total_students = 0
            cursor.execute("""
                SELECT c.id 
                FROM courses c
                JOIN class_courses cc ON c.id = cc.course_id
                WHERE cc.class_id = %s
            """, (cls['id'],))
            linked_courses = cursor.fetchall()

            for course in linked_courses:
                cursor.execute("SELECT COUNT(*) as count FROM students WHERE course = %s", (course['id'],))
                result = cursor.fetchone()
                total_students += result['count']

            cls['student_counts'] = total_students


            
            # Add first course name for backward compatibility
            if courses:
                cls['course_name'] = courses[0]['course_name']
                cls['code'] = courses[0]['code']
            else:
                cls['course_name'] = "Kein Kurs zugewiesen"
                cls['code'] = ""
                
        return classes
    finally:
        cursor.close()
        connection.close()

def get_all_classes_with_courses():
    connection = sql_connect()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT cls.id, cls.name, c.name as course_name
        FROM classes cls
        JOIN class_courses cc ON cls.id = cc.class_id
        JOIN courses c ON cc.course_id = c.id
        ORDER BY c.name, cls.name
    """)
    result = cursor.fetchall()
    cursor.close()
    connection.close()
    return result

def get_class_by_id(class_id):
    """Retrieve a class by its ID."""
    connection = sql_connect()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT 
                cls.id, 
                cls.name, 
                cls.created_at,
                cls.taught_by,
                CONCAT(p.first_name, ' ', p.last_name) as professor_name
            FROM classes cls
            LEFT JOIN professors p ON cls.taught_by = p.username
            WHERE cls.id = %s
        """, (class_id,))
        cls = cursor.fetchone()
        
        if cls:
            # Get associated courses
            cursor.execute("""
                SELECT c.id, c.name as course_name
                FROM courses c
                JOIN class_courses cc ON c.id = cc.course_id
                WHERE cc.class_id = %s
            """, (class_id,))
            courses = cursor.fetchall()
            cls['courses'] = courses
            
            # Set first course as primary for backwards compatibility
            if courses:
                cls['course_id'] = courses[0]['id']
                cls['course_name'] = courses[0]['course_name']
                
        return cls
    finally:
        cursor.close()
        connection.close()

def get_classes_for_student(student_username):
    """Return all classes for a given student (based on their course)"""
    connection = sql_connect()
    cursor = connection.cursor(dictionary=True)
    try:
        # First get the student's course
        cursor.execute("SELECT course FROM students WHERE username = %s", (student_username,))
        student = cursor.fetchone()
        
        if not student:
            return []
            
        student_course = student['course']
        
        # Get classes for this course through junction table
        cursor.execute("""
            SELECT 
                cls.id, 
                cls.name, 
                cls.created_at,
                c.id as code,
                c.name as course_name,
                CONCAT(p.first_name, ' ', p.last_name) as professor_name
            FROM classes cls
            JOIN class_courses cc ON cls.id = cc.class_id
            JOIN courses c ON cc.course_id = c.id
            LEFT JOIN professors p ON cls.taught_by = p.username
            WHERE cc.course_id = %s
            ORDER BY cls.name
        """, (student_course,))
        
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
                cls.created_at
            FROM classes cls
            WHERE cls.taught_by = %s
            ORDER BY cls.name
        """, (professor_username,))
        
        classes = cursor.fetchall()

        for cls in classes:
            # Kurse zur Klasse
            cursor.execute("""
                SELECT c.id as code, c.name as course_name 
                FROM courses c
                JOIN class_courses cc ON c.id = cc.course_id
                WHERE cc.class_id = %s
            """, (cls['id'],))
            courses = cursor.fetchall()

            cls['courses'] = courses
            cls['professor_name'] = professor_username

            # Studentenzahl berechnen
            total_students = 0
            for course in courses:
                cursor.execute("SELECT COUNT(*) as count FROM students WHERE course = %s", (course['code'],))
                result = cursor.fetchone()
                total_students += result['count']
            cls['student_counts'] = total_students

            # Backward compatibility
            if courses:
                cls['code'] = courses[0]['code']
                cls['course_name'] = courses[0]['course_name']
            else:
                cls['code'] = ""
                cls['course_name'] = "Kein Kurs zugewiesen"
        
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
        
        # First, insert into classes table without course_id
        cursor.execute("""
            INSERT INTO classes (name, taught_by)
            VALUES (%s, %s)
        """, (
            class_data["name"],
            class_data["taught_by"]
        ))
        
        # Get the new class ID
        class_id = cursor.lastrowid
        
        # Now add the course association in the junction table
        # If there's a list of courses, add all of them
        if "course_ids" in class_data and isinstance(class_data["course_ids"], list):
            for course_id in class_data["course_ids"]:
                cursor.execute("""
                    INSERT INTO class_courses (class_id, course_id)
                    VALUES (%s, %s)
                """, (class_id, course_id))
        # For backward compatibility - if there's a single course_id
        elif "course_id" in class_data:
            cursor.execute("""
                INSERT INTO class_courses (class_id, course_id)
                VALUES (%s, %s)
            """, (class_id, class_data["course_id"]))
            
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
    cursor = connection.cursor(dictionary=True)
    try:
        # Get all documents for this class to clean up files and vectors
        cursor.execute("SELECT id, file_path FROM documents WHERE class_id = %s", (class_id,))
        documents = cursor.fetchall()
        
        # Delete vectors from Neo4j and physical files for each document
        for doc in documents:
            try:
                # Import rag module to delete vectors
                import backend.rag as rag
                rag.delete_vectors_for_pdf(doc['id'])
                
                # Delete physical file from uploads folder
                file_path = os.path.join(os.getcwd(), 'uploads', doc['file_path'])
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logging.info(f"Deleted file: {file_path}")
                else:
                    logging.warning(f"File not found: {file_path}")
            except Exception as e:
                logging.error(f"Error cleaning up document {doc['id']}: {str(e)}")
        
        # Delete documents from database (this will cascade)
        cursor.execute("DELETE FROM documents WHERE class_id = %s", (class_id,))
        
        # Delete chat history for this class
        cursor.execute("DELETE FROM chat_history WHERE class_id = %s", (class_id,))
        
        # Delete JSON chat files for this class
        chats_dir = os.path.join(os.getcwd(), 'chats', f'class_{class_id}')
        if os.path.exists(chats_dir):
            import shutil
            shutil.rmtree(chats_dir)
            logging.info(f"Deleted chat directory: {chats_dir}")
        
        # Delete class-course relationships
        cursor.execute("DELETE FROM class_courses WHERE class_id = %s", (class_id,))
        
        # Delete the class
        cursor.execute("DELETE FROM classes WHERE id = %s", (class_id,))
        
        connection.commit()
        return True, "Vorlesung erfolgreich gelöscht."
    except Exception as e:
        logging.error(f"Error deleting class: {str(e)}")
        connection.rollback()
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

def get_document_by_id(pdf_id):
    connection = sql_connect()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM documents WHERE id=%s", (int(pdf_id),))
    doc = cursor.fetchone()
    cursor.close()
    connection.close()
    return doc


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


def delete_current_user(username, role):
    connection = sql_connect()
    cursor = connection.cursor()
    
    try:
        if role == "student":
            cursor.execute("DELETE FROM students WHERE username = %s", (username,))
        elif role in ["professor", "admin"]:
            cursor.execute("DELETE FROM professors WHERE username = %s", (username,))
        else:
            return False

        connection.commit()
        return True
    except Exception as e:
        logging.error(f"Error deleting user {username}: {str(e)}")
        return False
    finally:
        cursor.close()
        connection.close()

def count_admins():
    connection = sql_connect()
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM professors WHERE role = 'admin'")
    result = cursor.fetchone()[0]
    cursor.close()
    connection.close()
    return result


def count_students_per_course():
    connection = sql_connect()
    cursor = connection.cursor(dictionary=True)  
    cursor.execute("""
        SELECT course, COUNT(*) as count
        FROM students
        GROUP BY course
    """)
    result = cursor.fetchall()
    cursor.close()
    connection.close()
    return {row["course"]: row["count"] for row in result}

def get_user_by_username(username):
    """Get user from either students or professors table"""
    connection = None
    cursor = None
    try:
        connection = sql_connect()
        cursor = connection.cursor(dictionary=True)
        
        # First check professors table (includes admin and professor roles)
        cursor.execute("SELECT username, password, role FROM professors WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        if user:
            return user
            
        # If not found in professors, check students table
        cursor.execute("SELECT username, password, 'student' as role FROM students WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        return user
        
    except Exception as e:
        logging.error(f"Error getting user by username: {str(e)}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# Chat History
def save_chat_history(user_id, class_id, question, answer):
    """Save a chat interaction to the history and to JSON file"""
    connection = None
    cursor = None
    try:
        connection = sql_connect()
        cursor = connection.cursor()
        
        # Anonymize the user_id for database storage
        user_hash = anonymize_username(user_id)
        timestamp = datetime.now()
        
        # Save to database
        cursor.execute("""
        INSERT INTO chat_history (user_hash, class_id, question, answer)
        VALUES (%s, %s, %s, %s)
        """, (user_hash, class_id, question, answer))
        
        connection.commit()
        
        # Also save to JSON file
        save_chat_to_json(user_id, class_id, question, answer, timestamp.isoformat())
        
        return True
    except Exception as e:
        logging.error(f"Error saving chat history: {str(e)}")
        return False
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def get_chat_history_filtered_grouped(class_ids=None, course_ids=None, start_date=None, end_date=None):
    connection = sql_connect()
    if not connection:
        return {}
        
    cursor = connection.cursor(dictionary=True)

    query = """
        SELECT h.*, cls.name AS class_name, c.id AS course_id
        FROM chat_history h
        JOIN classes cls ON h.class_id = cls.id
        JOIN class_courses cc ON cls.id = cc.class_id
        JOIN courses c ON cc.course_id = c.id
        WHERE 1=1
    """
    params = []

    if class_ids:
        placeholders = ','.join(['%s'] * len(class_ids))
        query += f" AND h.class_id IN ({placeholders})"
        params.extend(class_ids)

    if course_ids:
        placeholders = ','.join(['%s'] * len(course_ids))
        query += f" AND c.id IN ({placeholders})"
        params.extend(course_ids)

    if start_date:
        query += " AND DATE(h.timestamp) >= %s"
        params.append(start_date)

    if end_date:
        query += " AND DATE(h.timestamp) <= %s"
        params.append(end_date)

    query += " ORDER BY h.user_hash, h.timestamp ASC"

    try:
        cursor.execute(query, params)
        result = cursor.fetchall()
        
        # Group by user_hash
        grouped_chats = {}
        for chat in result:
            user_hash = chat['user_hash']
            if user_hash not in grouped_chats:
                grouped_chats[user_hash] = {
                    'user_hash': user_hash,
                    'class_name': chat['class_name'],
                    'conversations': []
                }
            grouped_chats[user_hash]['conversations'].append(chat)
        
        return grouped_chats
    except Exception as e:
        logging.error(f"Chat-History Filter Error: {e}")
        return {}
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def get_chat_history_by_course(course_id):
    """Get chat history for a specific course, grouped by class"""
    connection = None
    cursor = None
    try:
        connection = sql_connect()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                ch.user_hash, 
                ch.question, 
                ch.answer, 
                ch.timestamp, 
                cls.id as class_id,
                cls.name as class_name
            FROM chat_history ch
            JOIN classes cls ON ch.class_id = cls.id
            JOIN class_courses cc ON cls.id = cc.class_id
            WHERE cc.course_id = %s
            ORDER BY cls.name, ch.timestamp DESC
        """, (course_id,))
        rows = cursor.fetchall()
        # Group by class
        classes = {}
        for row in rows:
            cid = row["class_id"]
            if cid not in classes:
                classes[cid] = {
                    "class_name": row["class_name"],
                    "chats": []
                }
            classes[cid]["chats"].append({
                "user_hash": row["user_hash"],
                "question": row["question"],
                "answer": row["answer"],
                "timestamp": row["timestamp"]
            })
        return classes
    except Exception as e:
        logging.error(f"Error retrieving course chat history: {str(e)}")
        return {}
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def get_chat_history_by_class(class_id):
    connection = sql_connect()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT user_hash, question, answer, timestamp
        FROM chat_history
        WHERE class_id = %s
        ORDER BY timestamp DESC
    """, (class_id,))
    result = cursor.fetchall()
    cursor.close()
    connection.close()
    return result

def save_chat_to_json(user_id, class_id, question, answer, timestamp=None):
    """Save a chat interaction to a JSON file in the chats folder"""
    try:
        # Create chats directory if it doesn't exist
        chats_dir = os.path.join(os.getcwd(), 'chats')
        if not os.path.exists(chats_dir):
            os.makedirs(chats_dir)
        
        # Generate timestamp if not provided
        if not timestamp:
            timestamp = datetime.now().isoformat()
            
        # Create a unique filename based on class and user
        user_hash = anonymize_username(user_id)
        class_dir = os.path.join(chats_dir, f"class_{class_id}")
        if not os.path.exists(class_dir):
            os.makedirs(class_dir)
            
        # Construct the chat message
        chat_message = {
            "user_hash": user_hash,
            "user_id": user_id,  # Store real ID in file for reference
            "class_id": class_id,
            "question": question,
            "answer": answer,
            "timestamp": timestamp
        }
        
        # Determine the filename - one file per user per class
        filename = os.path.join(class_dir, f"{user_hash}.json")
        
        # Read existing file or create new one
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                try:
                    chat_data = json.load(f)
                except json.JSONDecodeError:
                    chat_data = {"messages": []}
        else:
            chat_data = {"messages": []}
        
        # Append the new message
        chat_data["messages"].append(chat_message)
        
        # Write the updated data back to the file
        with open(filename, 'w') as f:
            json.dump(chat_data, f, indent=2)
            
        return True
    except Exception as e:
        logging.error(f"Error saving chat to JSON: {str(e)}")
        return False
    

# def get_chat_history_filtered(class_ids=None, course_ids=None, start_date=None, end_date=None):
#     connection = sql_connect()
#     cursor = connection.cursor(dictionary=True)

#     query = """
#         SELECT h.*, cls.name AS class_name, c.id AS course_id
#         FROM chat_history h
#         JOIN classes cls ON h.class_id = cls.id
#         JOIN class_courses cc ON cls.id = cc.class_id
#         JOIN courses c ON cc.course_id = c.id
#         WHERE 1=1    """
#     params = []

#     if class_ids:
#         placeholders = ','.join(['%s'] * len(class_ids))
#         query += f" AND h.class_id IN ({placeholders})"
#         params.extend(class_ids)

#     if course_ids:
#         placeholders = ','.join(['%s'] * len(course_ids))
#         query += f" AND c.id IN ({placeholders})"
#         params.extend(course_ids)

#     if start_date:
#         query += " AND DATE(h.timestamp) >= %s"
#         params.append(start_date)

#     if end_date:
#         query += " AND DATE(h.timestamp) <= %s"
#         params.append(end_date)

#     query += " ORDER BY h.timestamp DESC"

#     try:
#         cursor.execute(query, params)
#         result = cursor.fetchall()
#     except Exception as e:
#         print(f"[DB ERROR] Chat-History Filter Error: {e}")
#         result = []

#     cursor.close()
#     connection.close()
#     return result

def delete_chat_history_for_class(class_id):
    # Delete from SQL
    connection = sql_connect()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM chat_history WHERE class_id = %s", (class_id,))
    connection.commit()
    cursor.close()
    connection.close()

    # Delete JSON files
    chats_dir = os.path.join(os.getcwd(), 'chats', f'class_{class_id}')
    if os.path.exists(chats_dir):
        for filename in os.listdir(chats_dir):
            file_path = os.path.join(chats_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception as e:
                logging.error(f"Error deleting chat JSON file: {file_path} - {str(e)}")
        try:
            os.rmdir(chats_dir)
        except Exception as e:
            logging.error(f"Error removing chat directory: {chats_dir} - {str(e)}")
    connection.close()

    # Delete JSON files
    chats_dir = os.path.join(os.getcwd(), 'chats', f'class_{class_id}')
    if os.path.exists(chats_dir):
        for filename in os.listdir(chats_dir):
            file_path = os.path.join(chats_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception as e:
                logging.error(f"Error deleting chat JSON file: {file_path} - {str(e)}")
        try:
            os.rmdir(chats_dir)
        except Exception as e:
            logging.error(f"Error removing chat directory: {chats_dir} - {str(e)}")



def update_user_password(username, hashed_password):
    """
    Reset a user's password. Takes already hashed password.
    """
    try:
        connection = sql_connect()
        cursor = connection.cursor()

        # Update password in students
        cursor.execute("UPDATE students SET password = %s WHERE username = %s", (hashed_password, username))
        updated = cursor.rowcount

        # Falls kein Treffer: versuche professors
        if updated == 0:
            cursor.execute("UPDATE professors SET password = %s WHERE username = %s", (hashed_password, username))
            updated = cursor.rowcount

        connection.commit()

        if updated > 0:
            return True, "Passwort erfolgreich geändert."
        else:
            return False, "Benutzer nicht gefunden."

    except Exception as e:
        logging.error(f"Fehler beim Zurücksetzen des Passworts: {str(e)}")
        return False, f"Fehler: {str(e)}"

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()



def update_class_courses(class_id: int, course_ids: List[int]):
    connection = sql_connect()
    cursor = connection.cursor()
    try:
        # Zuerst alte Verknüpfungen löschen
        cursor.execute("DELETE FROM class_courses WHERE class_id = %s", (class_id,))
        
        # Neue Verknüpfungen einfügen
        for course_id in course_ids:
            cursor.execute("INSERT INTO class_courses (class_id, course_id) VALUES (%s, %s)", (class_id, course_id))
        
        connection.commit()
    finally:
        cursor.close()
        connection.close()

def get_classes_by_course_id(course_id):
    """Get all classes for a specific course"""
    connection = sql_connect()
    if not connection:
        return []
        
    cursor = connection.cursor(dictionary=True)
    try:
        query = """
            SELECT cls.* FROM classes cls
            JOIN class_courses cc ON cls.id = cc.class_id
            WHERE cc.course_id = %s
        """
        cursor.execute(query, (course_id,))
        result = cursor.fetchall()
        return result
    except Exception as e:
        logging.error(f"Error getting classes by course: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
