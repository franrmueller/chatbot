from multiprocessing import get_context
import mysql.connector
from fastapi import HTTPException
from backend.db import sql_connect
from datetime import datetime
from passlib.context import CryptContext

async def login(user_data: dict, db=None):
    try:
        # Manual validation of required fields
        required_fields = ["username", "password"]
        for field in required_fields:
            if field not in user_data:
                raise HTTPException(status_code=400, detail=f"Pflichtenfeld fehlt: {field}")

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        # Extract user data directly from dictionary
        username = user_data["username"]
        password = user_data["password"]

        # Database operations
        connection = db
        if connection is None:
            connection = sql_connect()
        cursor = connection.cursor()
        try:
            # Check if username exists
            cursor.execute("SELECT * FROM students WHERE username = %s", (username,))
            student = cursor.fetchone()
            if not student:
                raise HTTPException(status_code=400, detail="Benutzername falsch.")

            # Verify password
            if not pwd_context.verify(password, student[1]):
                raise HTTPException(status_code=400, detail="Passwort falsch.")

            return {"message": "Login erfolgreich", "user_id": student[0]}

        except mysql.connector.Error as e:
            raise HTTPException(status_code=500, detail=f"Database error: {e}")

        finally:
            # Only close cursor here, connection management is handled differently
            if cursor:
                cursor.close()
            # Only close connection if we created it in this function
            if connection and db is None:
                connection.close()

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

async def register_student(user_data: dict, db=None):
    try:
        # Manual validation of required fields
        required_fields = ["username", "password", "first_name", "last_name"]
        for field in required_fields:
            if field not in user_data or not user_data[field]:
                raise HTTPException(status_code=400, detail=f"Pflichtenfeld fehlt: {field}")
        
        # Password hashing context
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        # Extract user data directly from dictionary
        username = user_data["username"]
        password = pwd_context.hash(user_data["password"])
        first_name = user_data["first_name"]
        last_name = user_data["last_name"]
        created_at = datetime.now()
        course = "db"

        # Database operations
        connection = db
        if connection is None:
            connection = sql_connect()
        cursor = connection.cursor()
        try:
            # Check if username already exists
            cursor.execute("SELECT * FROM students WHERE username = %s", (username,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Benutzername bereits vergeben.")

            # Insert new student
            query = """
                INSERT INTO students (username, password, first_name, last_name, created_at, course)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            values = (username, password, first_name, last_name, created_at, course)
            cursor.execute(query, values)
            connection.commit()

            return {"message": "User registered successfully", "user_id": cursor.lastrowid}

        except mysql.connector.Error as e:
            raise HTTPException(status_code=500, detail=f"Database error: {e}")

        finally:
            # Only close cursor here, connection management is handled differently
            if cursor:
                cursor.close()
            # Only close connection if we created it in this function
            if connection and db is None:
                connection.close()

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))