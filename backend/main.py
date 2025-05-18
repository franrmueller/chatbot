from fastapi import FastAPI, Request, HTTPException, Body, Depends, Cookie, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional
import uvicorn
from backend.auth import register_student, login_student, login_professor
import backend.db as db

# API instantiation
app = FastAPI()

# Initialize database on first startup
db.initialize_database()

# Configure templates and static files
templates = Jinja2Templates(directory="frontend/templates")
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# Simple authentication middleware
async def get_current_user(session_token: Optional[str] = Cookie(None)):
    if not session_token:
        return None
    user = db.get_user_by_session(session_token)
    return user

# Admin check
async def verify_admin(request: Request):
    session_token = request.cookies.get("session_token")
    if not session_token:
        return RedirectResponse(url="/login?next=" + request.url.path)
    
    user = db.get_user_by_session(session_token)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    return user

# Frontend HTML Routing

# Startseite (index.html)
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
 
# Login-Seite (login.html)
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# Dozenten-Login-Seite (login_professors.html)
@app.get("/login_professors", response_class=HTMLResponse)
async def login_professors_page(request: Request):
    return templates.TemplateResponse("login_professors.html", {"request": request})

 
# Registrierung (register.html)
@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})



# Logout
@app.post("/api/logout")
async def logout_endpoint():
    response = JSONResponse({"success": True})
    response.delete_cookie(key="session_token")
    return response


@app.post("/api/register")
async def register_endpoint(student_data: dict = Body(...)):
    try:
        new_student = register_student(student_data)
        return {"success": True, "student_id": new_student.get("id")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Protected admin routes
@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    admin = await verify_admin(request)
    return templates.TemplateResponse("admin_dashboard.html", {"request": request, "user": admin})

@app.get("/admin/professors", response_class=HTMLResponse)
async def admin_professors(request: Request):
    admin = await verify_admin(request)
    return templates.TemplateResponse("admin_professors.html", {"request": request, "user": admin})

@app.get("/admin/students", response_class=HTMLResponse)
async def admin_students(request: Request):
    admin = await verify_admin(request)
    return templates.TemplateResponse("admin_students.html", {"request": request, "user": admin})

@app.get("/admin/chathistory", response_class=HTMLResponse)
async def admin_chathistory(request: Request):
    admin = await verify_admin(request)
    return templates.TemplateResponse("admin_chathistory.html", {"request": request, "user": admin})

@app.get("/classes", response_class=HTMLResponse)
async def classes(request: Request):
    try:
        # Get token from cookie
        session_token = request.cookies.get("session_token")
        
        # If no session token in cookie, check for Authorization header
        if not session_token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                session_token = auth_header.replace("Bearer ", "")
        
        # If still no token, redirect to login
        if not session_token:
            return RedirectResponse(url="/login?next=/classes", status_code=302)
        
        # Get user from token
        user = db.get_user_by_session(session_token)
        if not user:
            return RedirectResponse(url="/login?next=/classes", status_code=302)
        
        # Render template with user data
        return templates.TemplateResponse("classes.html", {"request": request, "user": user})
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return HTMLResponse(f"<h1>Server Error</h1><p>Details: {str(e)}</p>", status_code=500)

@app.get("/api/courses")
async def get_courses():
    return db.get_courses()

@app.post("/api/admin/reset-database")
async def reset_db_endpoint(request: Request):
    admin = await verify_admin(request)
    success = db.reset_database()
    return JSONResponse({"success": success})


@app.post("/api/login")
async def student_login_endpoint(username: str = Form(...), password: str = Form(...)):
    user = login_student(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    response = JSONResponse({
        "success": True,
        "role": user.get("role"),
        "access_token": user.get("session_token")
    })
    response.set_cookie(key="session_token", value=user.get("session_token"))
    return response


@app.post("/api/login_professors")
async def professor_login_endpoint(username: str = Form(...), password: str = Form(...)):
    user = login_professor(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    response = JSONResponse({
        "success": True,
        "role": user.get("role"),
        "access_token": user.get("session_token")
    })
    response.set_cookie(key="session_token", value=user.get("session_token"))
    return response

