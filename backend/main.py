from datetime import datetime
import uvicorn
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import logging
# Add this with the other imports at the top
from fastapi.responses import JSONResponse

# internal imports
from backend.db import sql_connect, reset_database
from backend.auth import login, register_student  # Import the function, not decorated with @app.post

# API instanciation
app = FastAPI()

# Configure templates and static files
templates = Jinja2Templates(directory="frontend/templates")
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# database initialization
@app.on_event("startup")
async def initialize_database():
    """Check if database is initialized, and set it up if not."""
    logging.info("Checking database initialization status...")
    try:
        connection = sql_connect()
        if not connection:
            logging.error("Could not connect to database during startup")
            return
            
        cursor = connection.cursor()
        
        # Check if the users table exists - if not, we need to initialize
        cursor.execute("SHOW TABLES LIKE 'users'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            logging.info("First-time startup detected. Setting up database...")
            reset_database()
            logging.info("Database initialization complete.")
        else:
            logging.info("Database already initialized. Skipping setup.")
            
        cursor.close()
        connection.close()
    except Exception as e:
        logging.error(f"Error during database initialization check: {str(e)}")

# Frontend HTML Routing

# Startseite (index.html)
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
 
# Login-Seite (login.html)
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})
 
# Registrierung (register.html)
@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})
 
# Gemeinsame Kursübersicht (classes.html – dynamisch je nach Rolle)
@app.get("/classes", response_class=HTMLResponse)
async def classes(request: Request):
    return templates.TemplateResponse("classes.html", {"request": request})
 
# Kursbasierter Chat (chat.html – verwendet course_id)
@app.get("/chat/{course_id}", response_class=HTMLResponse)
async def chat_view(request: Request, course_id: str):
    return templates.TemplateResponse("chat.html", {"request": request, "course_id": course_id})
 
# PDF-Übersicht für Admin oder Professor (pdf.html)
@app.get("/pdf", response_class=HTMLResponse)
async def pdf_admin(request: Request):
    return templates.TemplateResponse("pdf.html", {"request": request})
 
@app.get("/pdf/{course_id}", response_class=HTMLResponse)
async def pdf_professor(request: Request, course_id: str):
    return templates.TemplateResponse("pdf.html", {"request": request, "course_id": course_id})
 
# Chathistorie (admin_chathistory.html)
@app.get("/admin/chathistory", response_class=HTMLResponse)
async def admin_chathistory(request: Request):
    return templates.TemplateResponse("admin_chathistory.html", {"request": request})
 
# Admin-Dashboard (admin_dashboard.html)
@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    return templates.TemplateResponse("admin_dashboard.html", {"request": request})
 
# Professor:innenverwaltung (admin_professors.html)
@app.get("/admin/professors", response_class=HTMLResponse)
async def admin_professors(request: Request):
    return templates.TemplateResponse("admin_professors.html", {"request": request})
 
# Studierendenverwaltung (admin_students.html)
@app.get("/admin/students", response_class=HTMLResponse)
async def admin_students(request: Request):
    return templates.TemplateResponse("admin_students.html", {"request": request})

@app.get("/api/courses")
async def get_courses():
    try:
        connection = sql_connect()
        if not connection:
            return JSONResponse(
                status_code=500,
                content={"detail": "Database connection failed"}
            )
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, name FROM courses")
        courses = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return {"courses": courses}
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error fetching courses: {str(e)}"}
        )