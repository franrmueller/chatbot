from datetime import datetime
import uvicorn
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# internal imports
from backend.db import sql_connect, reset_database
from backend.auth import login, register_student  # Import the function, not decorated with @app.post

# API instanciation
app = FastAPI()

# Configure templates and static files
templates = Jinja2Templates(directory="frontend/templates")
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# HTML pages routing
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

# API Routes
@app.post("/register")
async def register_api(request: Request):
    user_data = await request.json()
    return await register_student(user_data, db=request.app.state.db)

@app.post("/login")
async def login_api(request: Request):
    user_data = await request.json()
    return await login(user_data, db=request.app.state.db)

# @app.post("/login")
# async def login_api(request: Request):
#     # Debug the raw request body
#     body = await request.json()
#     print(f"DEBUG: Request body: {body}")
#     return await login(body, db=request.app.state.db)

# Startup and Shutdown functions
@app.on_event("startup")
async def startup_db_client():
    """Initialize database connection on startup"""
    app.state.db = sql_connect()
    # Uncomment to reset database on startup (for development)
    # reset_database()

@app.on_event("shutdown")
async def shutdown_db_client():
    """Close database connection on shutdown"""
    if hasattr(app.state, "db") and app.state.db:
        app.state.db.close()