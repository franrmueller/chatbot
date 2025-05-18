import logging
import mysql.connector
from fastapi.responses import JSONResponse
import random, string 

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
        if not connection:
            logging.error("Failed to connect to database for initialization check")
            return False
            
        cursor = connection.cursor()
        
        # Check if the users table exists - if not, we need to initialize
        cursor.execute("SHOW TABLES LIKE 'users'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            logging.info("First-time startup detected. Setting up database...")
            cursor.close()
            connection.close()
            reset_database()
            logging.info("Database initialization complete.")
        else:
            logging.info("Database already initialized. Skipping setup.")
            cursor.close()
            connection.close()
            
        return True
    except Exception as e:
        logging.error(f"Error during database initialization check: {str(e)}")
        return False

# Database setup function
def admin_user():
    try:
        connection = sql_connect()
        if not connection:
            logging.error("Failed to connect to database for reset")
            return False
            
        cursor = connection.cursor()
        
        # Create admin with hashed password
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed_password = pwd_context.hash("admin")
        
        cursor.execute("""
        INSERT INTO teachers (username, password, first_name, last_name, role)
        VALUES (%s, %s, %s, %s, %s)
        """, ('admin', hashed_password, 'System', 'Administrator', 'admin'))
        
        cursor.execute("""
        INSERT INTO courses (id, name, created_by)
        VALUES (%s, %s, %s)
        """, ('DEFAULT', 'Default Course', 'admin'))
        
        connection.commit()
        logging.info("Database reset successfully.")
        return True
    
    except mysql.connector.Error as e:
        logging.error(f"Database reset error: {e}")
        return False
    
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'connection' in locals() and connection:
            connection.close()

# Connect to MySQL database
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
        if not connection:
            logging.error("Failed to connect to database for initialization check")
            return False
            
        cursor = connection.cursor()
        
        # Check if the users table exists - if not, we need to initialize
        cursor.execute("SHOW TABLES LIKE 'users'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            logging.info("First-time startup detected. Setting up database...")
            cursor.close()
            connection.close()
            reset_database()
            logging.info("Database initialization complete.")
        else:
            logging.info("Database already initialized. Skipping setup.")
            cursor.close()
            connection.close()
            
        return True
    except Exception as e:
        logging.error(f"Error during database initialization check: {str(e)}")
        return False

# Database setup function
def reset_database():
    try:
        connection = sql_connect()
        if not connection:
            logging.error("Failed to connect to database for reset")
            return False
            
        cursor = connection.cursor()
        
        # Drop tables in reverse order of dependencies
        cursor.execute("DROP TABLE IF EXISTS documents")
        cursor.execute("DROP TABLE IF EXISTS classes")
        cursor.execute("DROP TABLE IF EXISTS users")
        cursor.execute("DROP TABLE IF EXISTS courses")
        
        # Step 1: Create users table with USERNAME as primary key
        cursor.execute("""
        CREATE TABLE teachers (
            username VARCHAR(50) PRIMARY KEY,
            password VARCHAR(255) NOT NULL,
            first_name VARCHAR(50),
            last_name VARCHAR(50),
            role VARCHAR(7) DEFAULT 'student',
            session_token VARCHAR(64),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE courses (
            id VARCHAR(15) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by VARCHAR(50) NOT NULL,
            FOREIGN KEY (created_by) REFERENCES teachers(username)
        )
        """)

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
            teached_by VARCHAR(50) NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses(id),
            FOREIGN KEY (teached_by) REFERENCES teachers(username)
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
            FOREIGN KEY (created_by) REFERENCES teachers(username)
        )
        """)

        connection.commit()
        logging.info("Database reset successfully.")
        return True
    
    except mysql.connector.Error as e:
        logging.error(f"Database reset error: {e}")
        return False
    
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'connection' in locals() and connection:
            connection.close()

# Authentication function to get user by session token
def get_user_by_session(session_token):
    """Get user by session token"""
    if not session_token:
        return None
    
    try:
        connection = sql_connect()
        if not connection:
            return None
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE session_token = %s", (session_token,))
        user = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        return user
    
    except Exception as e:
        logging.error(f"Error retrieving user by session: {str(e)}")
        return None

# Function to check if a professor is assigned to a course
def is_professor_for_course(professor_id, course_id):
    """Check if a user is a professor for a specific course"""
    try:
        connection = sql_connect()
        if not connection:
            return False
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT 1 FROM classes 
            WHERE course_id = %s AND teached_by = %s
        """, (course_id, professor_id))
        
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
    
    import random, string

# Get courses for a specific professor
def get_courses_for_professor(username):
    try:
        connection = sql_connect()
        if not connection:
            return []

        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT c.id, c.name, c.id AS code, c.created_at
            FROM courses c
            WHERE c.created_by = %s
        """, (username,))
        courses = cursor.fetchall()

        cursor.close()
        connection.close()
        return courses

    except Exception as e:
        logging.error(f"Fehler beim Abrufen von Professor-Kursen: {e}")
        return []
        

# Create a new class
def create_class(name, course_id, professor_username):
    try:
        connection = sql_connect()
        if not connection:
            return False

        cursor = connection.cursor()

        class_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        cursor.execute("""
            INSERT INTO classes (id, name, created_by, course_id)
            VALUES (%s, %s, %s, %s)
        """, (class_id, name, professor_username, course_id))

        connection.commit()
        return True

    except Exception as e:
        logging.error(f"Fehler beim Erstellen der Klasse: {e}")
        return False

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# Create a new class 
def create_class(name, professor_username):
    try:
        connection = sql_connect()
        if not connection:
            return False

        cursor = connection.cursor()

        class_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        cursor.execute("""
            INSERT INTO courses (id, name, created_by)
            VALUES (%s, %s, %s)
        """, (class_id, name, professor_username))

        connection.commit()
        return True

    except Exception as e:
        logging.error(f"Fehler beim Erstellen des Kurses: {e}")
        return False

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
