import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from backend.db import sql_operations
import mysql.connector
from mysql.connector import Error

app = FastAPI()

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
            sql_operations.reset_database()
            print("Connected to MySQL database")
            return connection
    except mysql.connector.Error as e:
        print(f"{e}")
        return None

sql_operations.reset_database()

# Configure templates and static files
templates = Jinja2Templates(directory="frontend/templates")
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the home page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render the login page"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Render the registration page"""
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/student/class", response_class=HTMLResponse)
async def student_class_page(request: Request):
    """Render the student class overview page"""
    return templates.TemplateResponse("student_class.html", {"request": request})

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Render the admin dashboard"""
    return templates.TemplateResponse("admin_dashboard.html", {"request": request})