from fastapi import FastAPI, Request, HTTPException, Body, Depends, Cookie, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional, Dict, Any, Union
import uvicorn
from backend.auth import register_student, login_student, login_professor
import backend.db as db
import logging

# API instantiation
app = FastAPI()

# Initialize database on first startup
db.initialize_database()

# Configure frontend templates and static files
templates = Jinja2Templates(directory="frontend/templates")
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# =========================================
# Authentication Functions (unchanged)
# =========================================

async def get_current_user(request: Request):
    # Get token from cookie
    session_token = request.cookies.get("session_token")
    
    # If no token, redirect to login
    if not session_token:
        return RedirectResponse(url=f"/login/student?next={request.url.path}", status_code=302)
    
    # Get user from token
    user = db.get_user_by_session(session_token)
    if not user:
        return RedirectResponse(url=f"/login/student?next={request.url.path}", status_code=302)
    
    return user

async def verify_role(request: Request, allowed_roles: list):
    """Verify that the user has one of the allowed roles"""
    user = await get_current_user(request)
    
    if isinstance(user, RedirectResponse):
        return user
    
    if user.get("role") not in allowed_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    return user

# =========================================
# Public Routes
# =========================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Student login
@app.get("/login/student", response_class=HTMLResponse)
async def student_login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# Professor login
@app.get("/login/professor", response_class=HTMLResponse)
async def professor_login_page(request: Request):
    return templates.TemplateResponse("login_professors.html", {"request": request})

# Student registration
@app.get("/register/student", response_class=HTMLResponse)
async def student_register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

# Legacy routes for backward compatibility
@app.get("/login", response_class=HTMLResponse)
async def legacy_login_redirect(request: Request):
    return RedirectResponse(url="/login/student", status_code=302)

@app.get("/login_professors", response_class=HTMLResponse)
async def legacy_professor_login_redirect(request: Request):
    return RedirectResponse(url="/login/professor", status_code=302)

@app.get("/register", response_class=HTMLResponse)
async def legacy_register_redirect(request: Request):
    return RedirectResponse(url="/register/student", status_code=302)

# =========================================
# Student Routes
# =========================================

@app.get("/student/dashboard", response_class=HTMLResponse)
async def student_dashboard(request: Request):
    user = await verify_role(request, ["student"])
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("student_dashboard.html", {"request": request, "user": user})

@app.get("/student/classes", response_class=HTMLResponse)
async def student_classes(request: Request):
    user = await verify_role(request, ["student"])
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("classes.html", {"request": request, "user": user})

# =========================================
# Professor Routes
# =========================================

@app.get("/professor/dashboard", response_class=HTMLResponse)
async def professor_dashboard(request: Request):
    user = await verify_role(request, ["admin", "professor"])
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("professor_dashboard.html", {"request": request, "user": user})

@app.get("/professor/classes", response_class=HTMLResponse)
async def professor_classes(request: Request):
    user = await verify_role(request, ["admin", "professor"])
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("classes.html", {"request": request, "user": user})

# =========================================
# Admin Routes
# =========================================

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("admin_dashboard.html", {"request": request, "user": user})

@app.get("/admin/professors", response_class=HTMLResponse)
async def admin_professors(request: Request):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("admin_professors.html", {"request": request, "user": user})

@app.get("/admin/students", response_class=HTMLResponse)
async def admin_students(request: Request):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("admin_students.html", {"request": request, "user": user})

@app.get("/admin/chathistory", response_class=HTMLResponse)
async def admin_chathistory(request: Request):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("admin_chathistory.html", {"request": request, "user": user})

# Legacy route for backward compatibility
@app.get("/classes", response_class=HTMLResponse)
async def legacy_classes_redirect(request: Request):
    user = await get_current_user(request)
    if isinstance(user, RedirectResponse):
        return user
        
    if user.get("role") == "student":
        return RedirectResponse(url="/student/classes", status_code=302)
    elif user.get("role") == "professor":
        return RedirectResponse(url="/professor/classes", status_code=302)
    else:  # admin
        return RedirectResponse(url="/admin/dashboard", status_code=302)

# =========================================
# API Routes
# =========================================

# Authentication API endpoints
@app.post("/api/auth/login/student")
async def api_student_login(username: str = Form(...), password: str = Form(...)):
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

@app.post("/api/auth/login/professor")
async def api_professor_login(username: str = Form(...), password: str = Form(...)):
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

@app.post("/api/auth/logout")
async def api_logout():
    response = JSONResponse({"success": True})
    response.delete_cookie(key="session_token")
    return response

@app.post("/api/auth/register")
async def api_register(student_data: dict = Body(...)):
    try:
        new_student = register_student(student_data)
        return {"success": True, "student_id": new_student.get("id")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Data API endpoints
@app.get("/api/courses")
async def api_courses(request: Request):
    user = await verify_role(request, ["admin", "professor", "student"])
    if isinstance(user, RedirectResponse):
        raise HTTPException(status_code=401, detail="Authentication required")
    return db.get_courses()

# Admin API endpoints
@app.post("/api/admin/reset-database")
async def api_reset_db(request: Request):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        raise HTTPException(status_code=401, detail="Authentication required")
    success = db.reset_database()
    return JSONResponse({"success": success})

# Legacy API routes for backward compatibility
@app.post("/api/login")
async def legacy_api_login(username: str = Form(...), password: str = Form(...)):
    return await api_student_login(username, password)

@app.post("/api/login_professors")
async def legacy_api_professor_login(username: str = Form(...), password: str = Form(...)):
    return await api_professor_login(username, password)

@app.post("/api/logout")
async def legacy_api_logout():
    return await api_logout()

@app.post("/api/register")
async def legacy_api_register(student_data: dict = Body(...)):
    return await api_register(student_data)