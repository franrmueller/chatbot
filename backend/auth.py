import mysql.connector
from fastapi import HTTPException
from backend.db import sql_connect
from datetime import datetime
from passlib.context import CryptContext
import secrets

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
            INSERT INTO students (username, password, first_name, last_name, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (username, password, first_name, last_name, created_at))
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
