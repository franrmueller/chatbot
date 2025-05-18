import mysql.connector
from fastapi import HTTPException
from backend.db import sql_connect
from datetime import datetime
from passlib.context import CryptContext
import secrets

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def login(username, password):
    """Authenticate user and return user data with session token"""
    try:
        # Validate inputs
        if not username or not password:
            return None

        # Database operations
        connection = sql_connect()
        cursor = connection.cursor(dictionary=True)
        try:
            # Check if username exists
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            if not user:
                return None

            # Verify password
            if not pwd_context.verify(password, user["password"]):
                return None

            # Generate session token
            session_token = secrets.token_hex(32)
            
            # Store session token in database
            cursor.execute(
                "UPDATE users SET session_token = %s WHERE username = %s", 
                (session_token, user["username"])
            )
            connection.commit()
            
            # Return user with session token
            return {
                "username": user["username"],
                "role": user["role"],
                "session_token": session_token
            }

        except mysql.connector.Error as e:
            raise HTTPException(status_code=500, detail=f"Database error: {e}")

        finally:
            cursor.close()
            connection.close()

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

def register_student(student_data):
    """Register a new student and return the created user"""
    try:
        # Manual validation of required fields
        required_fields = ["username", "password", "first_name", "last_name"]
        for field in required_fields:
            if field not in student_data or not student_data[field]:
                raise HTTPException(status_code=400, detail=f"Pflichtenfeld fehlt: {field}")
        
        # Extract user data
        username = student_data["username"]
        password = pwd_context.hash(student_data["password"])
        first_name = student_data["first_name"]
        last_name = student_data["last_name"]
        created_at = datetime.now()
        
        # Database operations
        connection = sql_connect()
        cursor = connection.cursor(dictionary=True)
        try:
            # Check if username already exists
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Benutzername bereits vergeben.")

            # Insert new student
            query = """
                INSERT INTO users (username, password, first_name, last_name, created_at, role)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            values = (username, password, first_name, last_name, created_at, "student")
            cursor.execute(query, values)
            connection.commit()
            
            new_id = cursor.lastrowid
            
            return {
                "id": new_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "role": "student"
            }

        except mysql.connector.Error as e:
            raise HTTPException(status_code=500, detail=f"Database error: {e}")

        finally:
            cursor.close()
            connection.close()

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))