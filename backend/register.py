from fastapi import FastAPI, HTTPException, Request
from passlib.context import CryptContext
import main

app = FastAPI()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Database connection function

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
        password = hashed_password
        email = user_data.get("email")
        first_name = user_data["first_name"]
        last_name = user_data["last_name"]
        try:
            connection = main.sql_connect()
            cursor = connection.cursor()
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

    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Database error: {err}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()

    return {"message": "User registered successfully"}
