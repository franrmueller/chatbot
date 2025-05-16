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
        else:
            raise HTTPException(status_code=500, detail="Failed to connect to the database")
    except mysql.connector.Error as e:
        print(f"{e}")
        return None
        

# Database setup function
def reset_database():
    connection = sql_connect()
    if not connection:
        print("Failed to connect to the database.")
        return False

    cursor = connection.cursor()
    try:
        # Drop tables in reverse dependency order
        cursor.execute("DROP TABLE IF EXISTS student_enrollments")
        cursor.execute("DROP TABLE IF EXISTS documents")
        cursor.execute("DROP TABLE IF EXISTS classes")
        cursor.execute("DROP TABLE IF EXISTS courses")
        cursor.execute("DROP TABLE IF EXISTS students")
        cursor.execute("DROP TABLE IF EXISTS teachers")

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
        
        CREATE TABLE courses (
            id VARCHAR(15) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by VARCHAR(50) NOT NULL,
            FOREIGN KEY (created_by) REFERENCES teachers(username)
        )
        
        CREATE TABLE students (
            username VARCHAR(50) PRIMARY KEY,
            password VARCHAR(255) NOT NULL,
            first_name VARCHAR(50),
            last_name VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            course VARCHAR(15) NOT NULL,
            FOREIGN KEY (course) REFERENCES courses(id)
        )
    
        CREATE TABLE classes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            course_id VARCHAR(15) NOT NULL,
            teached_by VARCHAR(50) NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses(id),
            FOREIGN KEY (teached_by) REFERENCES teachers(username)
        )
                
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
        print("Database reset successfully.")
        return True
    
    except mysql.connector.Error as e:
        print(f"Error: {e}")
        return False
    
    finally:
        cursor.close()
        connection.close()