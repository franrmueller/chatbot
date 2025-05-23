import logging
import mysql.connector
from fastapi.responses import JSONResponse
from passlib.context import CryptContext

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
        hashed_password = pwd_context.hash("admin")
        
        cursor.execute("""
        INSERT INTO professors (username, password, first_name, last_name, role)
        VALUES (%s, %s, %s, %s, %s)
        """, ('admin', hashed_password, 'System', 'Administrator', 'admin'))

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
        """, ('DEFAULT', 'Default Course', 'admin'))
        
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
            name VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by VARCHAR(50) NOT NULL,
            class_id INT NOT NULL,
            FOREIGN KEY (class_id) REFERENCES classes(id),
            FOREIGN KEY (created_by) REFERENCES professors(username)
        )
        """)

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
    """Add a new professor"""
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
        
        # Parse name into first_name and last_name
        name_parts = professor_data['name'].split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        # Insert professor
        cursor.execute("""
            INSERT INTO professors (username, password, first_name, last_name, role)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            professor_data['username'],
            password_hash,
            first_name,
            last_name,
            'professor'  # Default role
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