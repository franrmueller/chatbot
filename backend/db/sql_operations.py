import mysql.connector
from mysql.connector import Error

# MySQL connection parameters

# Connect to MySQL database
def sql_connect():
    try:
        connection = mysql.connector.connect(
            host="mysql",
            port=3306,
            user="root",
            password="root",
            database="chatbot"
        )
        if connection.is_connected():
            print("Connected to MySQL database")
            return connection
    except mysql.connector.Error as e:
        print(f"{e}")
        return None
        
# Database setup function
def reset_database():
    connection = sql_connect()
    cursor = connection.cursor()
    try:
        cursor.execute("DROP TABLE IF EXISTS student_enrollments")
        cursor.execute("DROP TABLE IF EXISTS courses")
        cursor.execute("DROP TABLE IF EXISTS students")
        cursor.execute("DROP TABLE IF EXISTS teachers")
        # Create students table
        cursor.execute("""
        CREATE TABLE students (
            username VARCHAR(50) PRIMARY KEY,
            password VARCHAR(255) NOT NULL,
            first_name VARCHAR(50),
            last_name VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            course VARCHAR(15) NOT NULL,
            FOREIGN KEY (course) REFERENCES courses(id)
        )
        """)
        
        # Create teachers table
        cursor.execute("""
        CREATE TABLE teachers (
            username VARCHAR(50) PRIMARY KEY,
            password VARCHAR(255) NOT NULL,
            first_name VARCHAR(50),
            last_name VARCHAR(50),
            role VARCHAR(7) DEFAULT 'teacher',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create courses table
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
        CREATE TABLE classes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            course_id VARCHAR(15) NOT NULL,
            teached_by VARCHAR(50) NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses(id),
            FOREIGN KEY (teached_by) REFERENCES teachers(username)
        )""")
        
        cursor.execute("""
        CREATE TABLE documents (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by VARCHAR(50) NOT NULL,
            course_id VARCHAR(15) NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses(id),
            FOREIGN KEY (created_by) REFERENCES teachers(username)
        )        
        """)
        connection.commit()
        return True
    
    except mysql.connector.Error as e:
        print(f"{e}")
        return None
    
    finally:
        cursor.close()
        connection.close()

# Student registration function
def register_student(username, password, email=None, first_name=None, last_name=None):
    connection = sql_connect()
    cursor = connection.cursor()
    try:
        # Check if student already exists
        cursor.execute("SELECT * FROM students WHERE username = %s", (username,))
        if cursor.fetchone():
            return False, "Username already exists"
        
        # Insert new student
        query = "INSERT INTO students (username, password, email, first_name, last_name) VALUES (%s, %s, %s, %s, %s)"
        values = (username, password, email, first_name, last_name)
        cursor.execute(query, values)
        connection.commit()
        return True, cursor.lastrowid
    
    except mysql.connector.Error as e:
        print(f"{e}")
        return None
    
    finally:
        cursor.close()
        connection.close()