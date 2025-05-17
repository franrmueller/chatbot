from fastapi import HTTPException
import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

# Connect to MySQL database
load_dotenv()
def sql_connect():
    try:
        host=os.getenv("DB_HOST")
        user=os.getenv("DB_USER")
        password=os.getenv("DB_PASSWORD")
        database=os.getenv("DB_NAME")

        print(f"Attempting to connect to database: {database} at {host}:3306 as {user}")

        connection = mysql.connector.connect(
            host=host,
            port=3306,
            user=user,
            password=password,
            database=database,
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
        # Drop tables in reverse order of dependencies
        cursor.execute("DROP TABLE IF EXISTS documents")
        cursor.execute("DROP TABLE IF EXISTS classes")
        cursor.execute("DROP TABLE IF EXISTS users")
        cursor.execute("DROP TABLE IF EXISTS courses")
        
        # Step 1: Create users table WITHOUT the foreign key to courses
        cursor.execute("""
        CREATE TABLE users (
            username VARCHAR(50) PRIMARY KEY,
            password VARCHAR(255) NOT NULL,
            first_name VARCHAR(50),
            last_name VARCHAR(50),
            role VARCHAR(7) DEFAULT 'student',
            course VARCHAR(15),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Step 2: Create courses table with its foreign key to users
        cursor.execute("""
        CREATE TABLE courses (
            id VARCHAR(15) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by VARCHAR(50) NOT NULL,
            FOREIGN KEY (created_by) REFERENCES users(username)
        )
        """)
        
        # Step 3: Add the foreign key to users table AFTER both tables exist
        cursor.execute("""
        ALTER TABLE users 
        ADD CONSTRAINT fk_user_course
        FOREIGN KEY (course) REFERENCES courses(id)
        """)
        
        cursor.execute("""
        CREATE TABLE classes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            course_id VARCHAR(15) NOT NULL,
            teached_by VARCHAR(50) NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses(id),
            FOREIGN KEY (teached_by) REFERENCES users(username)
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
            FOREIGN KEY (created_by) REFERENCES users(username)
        )
        """)

        # Create admin user
        cursor.execute("""
        INSERT INTO users (username, password, first_name, last_name, role)
        VALUES ('admin', 'admin', 'System', 'Administrator', 'admin')
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