from fastapi import FastAPI, Request, HTTPException, Body, Depends, Cookie, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional, Dict, Any, Union
import uvicorn
from backend import auth
from backend.auth import register_student, login_student, login_professor
import backend.db as db
import logging

# API instantiation
app = FastAPI()

pwd_context = auth.pwd_context

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

@app.get("/auth/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(key="session_token", path="/", domain=None, secure=False, httponly=True)
    return response

# =========================================
# Student Routes
# =========================================

@app.get("/student/dashboard", response_class=HTMLResponse)
async def student_dashboard(request: Request):
    user = await verify_role(request, ["student"])
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("student_dashboard.html", {"request": request, "user": user})

# @app.get("/student/classes", response_class=HTMLResponse)
# async def student_classes(request: Request):
#     user = await verify_role(request, ["student"])
#     if isinstance(user, RedirectResponse):
#         return user
#     return templates.TemplateResponse("classes.html", {"request": request, "user": user})

# =========================================
# Professor Routes
# =========================================

@app.get("/professor/dashboard", response_class=HTMLResponse)
async def professor_dashboard(request: Request):
    user = await verify_role(request, ["admin", "professor"])
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("professor_dashboard.html", {"request": request, "user": user})

# @app.get("/professor/classes", response_class=HTMLResponse)
# async def professor_classes(request: Request):
#     user = await verify_role(request, ["admin", "professor"])
#     if isinstance(user, RedirectResponse):
#         return user
#     return templates.TemplateResponse("classes.html", {"request": request, "user": user})

# =========================================
# Admin Routes
# =========================================

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("admin_dashboard.html", {"request": request, "user": user})

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

    courses = db.get_courses_for_user(user)
    return templates.TemplateResponse("classes.html", {
        "request": request,
        "user": user,
        "courses": courses
    })

    return templates.TemplateResponse("classes.html", {"request": request, "user": user})
    # if user.get("role") == "student":
    #     return RedirectResponse(url="/student/classes", status_code=302)
    # elif user.get("role") == "professor":
    #     return RedirectResponse(url="/professor/classes", status_code=302)
    # else:  # admin
    #     return RedirectResponse(url="/admin/dashboard", status_code=302)
    
@app.get("/admin/professors", response_class=HTMLResponse)
async def admin_professors_page(request: Request):
    """Render the professor management page"""
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user
    
    # Get all professors with their courses
    professors = db.get_all_professors_with_courses()
    
    return templates.TemplateResponse("admin_professors.html", {
        "request": request, 
        "user": user,
        "professors": professors
    })

@app.post("/admin/professors", response_class=HTMLResponse)
async def admin_add_professor(
    request: Request,
    name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...)
):
    """Add a new professor"""
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user
    
    # Create professor data
    professor_data = {
        "name": name,
        "username": username,
        "password": password
    }
    
    # Add professor
    success, message = db.add_professor(professor_data)
    
    # Get all professors for display
    professors = db.get_all_professors_with_courses()
    
    # Return template with appropriate message
    if success:
        return templates.TemplateResponse("admin_professors.html", {
            "request": request, 
            "user": user,
            "professors": professors,
            "success": message
        })
    else:
        return templates.TemplateResponse("admin_professors.html", {
            "request": request, 
            "user": user,
            "professors": professors,
            "error": message
        })

@app.post("/admin/professors/delete/{professor_username}")
async def admin_delete_professor(request: Request, professor_username: int):
    """Delete a professor"""
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user
    
    # Delete professor
    success, message = db.delete_professor(professor_username)
    
    # Redirect back to professors page
    if success:
        return RedirectResponse(
            url=f"/admin/professors?success={message}",
            status_code=303
        )
    else:
        return RedirectResponse(
            url=f"/admin/professors?error={message}",
            status_code=303
        )

# Add edit professor functionality
@app.get("/admin/professors/edit/{professor_username}", response_class=HTMLResponse)
async def admin_edit_professor_page(request: Request, professor_username: int):
    """Render the professor edit page"""
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user
    
    # Get professor details
    connection = db.sql_connect()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM professors WHERE id = %s", (professor_username,))
    professor = cursor.fetchone()
    cursor.close()
    connection.close()
    
    if not professor:
        return RedirectResponse(
            url="/admin/professors?error=Professor nicht gefunden",
            status_code=303
        )
    
    # Format professor data for template
    professor_data = {
        "id": professor["id"],
        "username": professor["username"],
        "name": f"{professor['first_name']} {professor['last_name']}"
    }
    
    return templates.TemplateResponse("admin_edit_professor.html", {
        "request": request, 
        "user": user,
        "professor": professor_data
    })

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
    
    # Return JSON response with redirect information
    redirect_url = "/admin/dashboard" if user.get("role") == "admin" else "/professor/dashboard"
    
    response = JSONResponse({
        "success": True,
        "role": user.get("role"),
        "redirect_url": redirect_url
    })
    
    # Set authentication cookie
    response.set_cookie(key="session_token", value=user.get("session_token"))
    return response

@app.get("/api/auth/check")
async def check_auth(request: Request):
    """Check if the user is authenticated and return their role"""
    try:
        user = await get_current_user(request)
        if isinstance(user, RedirectResponse):
            return JSONResponse({
                "authenticated": False
            })
        
        return JSONResponse({
            "authenticated": True,
            "role": user.get("role", "unknown")
        })
    except:
        return JSONResponse({
            "authenticated": False
        })

@app.post("/api/auth/logout")
async def api_logout():
    response = JSONResponse({"success": True})
    response.delete_cookie(key="session_token", path="/", domain=None, secure=False, httponly=True)
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