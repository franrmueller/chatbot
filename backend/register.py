from fastapi import FastAPI, HTTPException, Request
from passlib.context import CryptContext
import main
import mysql.connector  # Import missing module

app = FastAPI()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@app.post("/auth/register")
async def register_user(request: Request):
    try:
        # Parse the JSON body
        user_data = await request.json()

        # Manual validation
        required_fields = ["first_name", "last_name", "username", "password", "role"]
        for field in required_fields:
            if field not in user_data or not user_data[field]:
                raise HTTPException(status_code=400, detail=f"Missing or empty field: {field}")

        # Hash the password
        hashed_password = pwd_context.hash(user_data["password"])
        username = user_data["username"]
        email = user_data.get("email")
        first_name = user_data["first_name"]
        last_name = user_data["last_name"]

        # Database operations
        connection = main.sql_connect()
        cursor = connection.cursor()

        try:
            # Check if username already exists
            cursor.execute("SELECT * FROM students WHERE username = %s", (username,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Username already exists")

            # Insert new student
            query = """
                INSERT INTO students (username, password, email, first_name, last_name)
                VALUES (%s, %s, %s, %s, %s)
            """
            values = (username, hashed_password, email, first_name, last_name)
            cursor.execute(query, values)
            connection.commit()

            return {"message": "User registered successfully", "user_id": cursor.lastrowid}

        except mysql.connector.Error as e:
            raise HTTPException(status_code=500, detail=f"Database error: {e}")

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))