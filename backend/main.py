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
from fastapi import UploadFile, File

#  HINZUGEFÜGT: Chatbot-Module importieren
from backend.rag.chains import (
    load_embedding_model,
    load_llm,
    configure_qa_rag_chain,
)
from backend.rag.utils import BaseLogger

#from backend.rag.zneo4j_operations import NEO4J_USERNAME, NEO4J_PASSWORD


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

@app.post("/admin/classes", response_class=HTMLResponse)
async def admin_add_class(
    request: Request,
    name: str = Form(...),
    course: str = Form(...)
):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    # Insert new class into DB
    success, message = db.add_class({
        "name": name,
        "course_id": course,
        "taught_by": user["username"]  # or let admin select a professor
    })

    # Reload classes for display
    classes = db.get_all_classes()
    return templates.TemplateResponse("classes.html", {
        "request": request,
        "user": user,
        "classes": classes,
        "success" if success else "error": message
    })
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
async def show_classes(request: Request):
    user = await get_current_user(request)
    if isinstance(user, RedirectResponse):
        return user

    if user["role"] == "student":
        classes = db.get_classes_for_student(user["username"])
    elif user["role"] == "professor":
        classes = db.get_classes_for_professor(user["username"])
    else:  # admin
        classes = db.get_all_classes()

    return templates.TemplateResponse("classes.html", {
        "request": request,
        "user": user,
        "classes": classes
    })
    return templates.TemplateResponse("classes.html", {"request": request, "user": user})
    
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
    first_name: str = Form(...),
    last_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...)
):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    professor_data = {
        "first_name": first_name,
        "last_name": last_name,
        "username": username,
        "password": password,
        "role": role
    }

    success, message = db.add_professor(professor_data)
    professors = db.get_all_professors_with_courses()

    return templates.TemplateResponse("admin_professors.html", {
        "request": request,
        "user": user,
        "professors": professors,
        "success" if success else "error": message
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

# =========================================
# Classes
# =========================================

@app.get("/chat/{class_code}", response_class=HTMLResponse)
async def chat_page(request: Request, class_code: str):
    user = await get_current_user(request)
    if isinstance(user, RedirectResponse):
        return user

    # Get class/course info by code
    connection = db.sql_connect()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM classes WHERE course_id = %s", (class_code,))
    course = cursor.fetchone()
    cursor.close()
    connection.close()

    if not course:
        return HTMLResponse(content="Kurs nicht gefunden.", status_code=404)

    return templates.TemplateResponse("chat.html", {
        "request": request,
        "user": user,
        "course": course
    })

@app.post("/admin/classes/delete/{class_id}")
async def admin_delete_class(request: Request, class_id: int):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    # Use the db function for deletion
    success, message = db.delete_class(class_id)

    # Reload classes for display
    classes = db.get_all_classes()
    return templates.TemplateResponse("classes.html", {
        "request": request,
        "user": user,
        "classes": classes,
        "success" if success else "error": message
    })

# PDF
# --- Admin PDF Übersicht ---
@app.get("/admin/pdf", response_class=HTMLResponse)
async def admin_pdf_overview(request: Request, class_id: int = None):
    user = await verify_role(request, ["admin"])
    if class_id:
        pdfs = db.get_pdfs_for_class(class_id)
        connection = db.sql_connect()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM classes WHERE id = %s", (class_id,))
        cls = cursor.fetchone()
        cursor.close()
        connection.close()
        return templates.TemplateResponse("pdf.html", {
        	"request": request,
            "user": user,
            "pdfs": pdfs,
            "class_id": class_id,
            "course": cls if cls else None
        })
    else:
        pdfs = db.get_pdfs_for_admin()
        return templates.TemplateResponse("pdf.html", {
            "request": request,
            "user": user,
            "pdfs": pdfs
        })

# --- Professor PDF Übersicht für Kurs ---
@app.get("/professor/pdf", response_class=HTMLResponse)
async def professor_pdf_overview(request: Request, class_id: int):
    user = await verify_role(request, ["professor", "admin"])
    if isinstance(user, RedirectResponse):
        return user

    pdfs = db.get_pdfs_for_class(class_id)
    return templates.TemplateResponse("pdf.html", {
        "request": request,
        "user": user,
        "pdfs": pdfs,
        "class_id": class_id
    })
# --- PDF Upload (Professor) ---
@app.post("/professor/pdf", response_class=HTMLResponse)
async def upload_pdf_professor(
    request: Request,
    course_id: str,
    pdf: UploadFile = File(...)
):
    user = await verify_role(request, ["professor"])
    course = db.get_course_by_id(course_id)
    cls = db.get_class_by_course_and_professor(course_id, user["username"])
    if not cls:
        return templates.TemplateResponse("pdf.html", {
            "request": request,
            "user": user,
            "pdfs": db.get_pdfs_for_professor_course(course_id),
            "course": course,
            "error": "Keine zugewiesene Klasse für diesen Kurs."
        })
    # Save file (implement your own logic)
    content = await pdf.read()
    db.add_document({
        "name": pdf.filename,
        "created_by": user["username"],
        "class_id": cls["id"],
        "file_type": pdf.content_type
    }, content)
    pdfs = db.get_pdfs_for_professor_course(course_id)
    return templates.TemplateResponse("pdf.html", {
        "request": request,
        "user": user,
        "pdfs": pdfs,
        "course": course,
        "success": "PDF erfolgreich hochgeladen."
    })

# --- PDF Update ---
@app.post("/admin/pdf/update/{pdf_id}", response_class=HTMLResponse)
async def admin_update_pdf(request: Request, pdf_id: int, updated_pdf: UploadFile = File(...)):
    user = await verify_role(request, ["admin"])
    db.update_pdf(pdf_id, updated_pdf)
    pdfs = db.get_pdfs_for_admin()
    return templates.TemplateResponse("pdf.html", {
        "request": request,
        "user": user,
        "pdfs": pdfs,
        "success": "PDF erfolgreich aktualisiert."
    })

@app.post("/professor/pdf/{course_id}/update/{pdf_id}", response_class=HTMLResponse)
async def professor_update_pdf(
    request: Request,
    course_id: str,
    pdf_id: int,
    updated_pdf: db.UploadFile = db.File(...)
):
    user = await verify_role(request, ["professor"])
    db.update_pdf(pdf_id, updated_pdf)
    pdfs = db.get_pdfs_for_professor_course(course_id)
    course = db.get_course_by_id(course_id)
    return templates.TemplateResponse("pdf.html", {
        "request": request,
        "user": user,
        "pdfs": pdfs,
        "course": course,
        "success": "PDF erfolgreich aktualisiert."
    })

# --- PDF Delete ---
@app.post("/admin/pdf/delete/{pdf_id}", response_class=HTMLResponse)
async def admin_delete_pdf(request: Request, pdf_id: int):
    user = await verify_role(request, ["admin"])
    db.delete_pdf(pdf_id)
    pdfs = db.get_pdfs_for_admin()
    return templates.TemplateResponse("pdf.html", {
        "request": request,
        "user": user,
        "pdfs": pdfs,
        "success": "PDF erfolgreich gelöscht."
    })

@app.post("/professor/pdf/{course_id}/delete/{pdf_id}", response_class=HTMLResponse)
async def professor_delete_pdf(request: Request, course_id: str, pdf_id: int):
    user = await verify_role(request, ["professor"])
    db.delete_pdf(pdf_id)
    pdfs = db.get_pdfs_for_professor_course(course_id)
    course = db.get_course_by_id(course_id)
    return templates.TemplateResponse("pdf.html", {
        "request": request,
        "user": user,
        "pdfs": pdfs,
        "course": course,
        "success": "PDF erfolgreich gelöscht."
    })


# =========================================
# Authentication Functions (unchanged)
# =========================================

async def get_current_user(request: Request):
    session_token = request.cookies.get("session_token")
    if not session_token:
        return RedirectResponse(url=f"/login/student?next={request.url.path}", status_code=302)
    user = db.get_user_by_session(session_token)
    if not user:
        return RedirectResponse(url=f"/login/student?next={request.url.path}", status_code=302)
    return user

async def verify_role(request: Request, allowed_roles: list):
    user = await get_current_user(request)
    if isinstance(user, RedirectResponse):
        return user
    if user.get("role") not in allowed_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return user

# =========================================
# NEU: Chatbot-Rückfrage-Endpunkt
# =========================================

@app.post("/api/chat")
async def ask_question(request: Request, question: str = Form(...), class_code: str = Form(...)):
    user = await get_current_user(request)
    if isinstance(user, RedirectResponse):
        return user

    config = {
        "ollama_base_url": "http://localhost:11434"
    }

    embeddings, dim = load_embedding_model("ollama", config=config)
    llm = load_llm("llama2", config=config)

    qa_chain = configure_qa_rag_chain(
        llm=llm,
        embeddings=embeddings,
        embeddings_store_url="bolt://localhost:7687",
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD
    )

    result = qa_chain({"question": question})
    return {"answer": result["answer"], "sources": result.get("sources", "")}



# =========================================
# NEU: JSON-basierter Endpunkt für chat.html
# =========================================
@app.post("/api/chat/{course_id}")
async def chat_api(request: Request, course_id: str, body: Dict[str, str] = Body(...)):
    user = await get_current_user(request)
    if isinstance(user, RedirectResponse):
        raise HTTPException(status_code=401, detail="Nicht eingeloggt.")

    prompt = body.get("prompt")
    if not prompt:
        raise HTTPException(status_code=400, detail="Kein Prompt erhalten.")

    config = {
        "ollama_base_url": "http://localhost:11434"
    }

    embeddings, dim = load_embedding_model("ollama", config=config)
    llm = load_llm("llama2", config=config)

    qa_chain = configure_qa_rag_chain(
        llm=llm,
        embeddings=embeddings,
        embeddings_store_url="bolt://localhost:7687",
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD  
    )

    result = qa_chain({"question": prompt})
    return {
        "answer": result.get("answer", "Keine Antwort gefunden."),
        "source": result.get("sources", "Keine Quelle angegeben.")
    }