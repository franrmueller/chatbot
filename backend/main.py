from typing import Optional, List
from fastapi import (
    FastAPI, Request, HTTPException,
    Body, Depends, Cookie, Form,
    UploadFile, File
    )

from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import backend.db as db
import backend.rag as rag


app = FastAPI()
pwd_context = db.pwd_context
db.initialize_database()

# Configure frontend templates and static files
templates = Jinja2Templates(directory="frontend/templates")
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# =========================================
# Authentication Functions
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
    return templates.TemplateResponse("index.html", {
        "request": request
    })


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
    response = RedirectResponse(url="/logout-page", status_code=302)  # Redirect to a logout page first
    response.delete_cookie(key="session_token", path="/", domain=None, secure=False, httponly=True)
    return response

@app.get("/logout-page", response_class=HTMLResponse)
async def logout_page(request: Request):
    return templates.TemplateResponse("logout.html", {"request": request})


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
    courses: list[str] = Form(...),  # This will now be a list
    taught_by: str = Form(...)
):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    # Insert new class into DB with multiple courses
    success, message = db.add_class({
        "name": name,
        "course_ids": courses,  # Changed from course_id to course_ids
        "taught_by": taught_by
    })

    # Reload classes for display
    classes = db.get_all_classes()
    professors = db.get_all_professors()
    return templates.TemplateResponse("classes.html", {
        "request": request,
        "user": user,
        "classes": classes,
        "professors": professors,
        "success" if success else "error": message
    })

# # Password Reset
# SECURITY_QUESTIONS = [
#     "Was ist der Name deines ersten Haustiers?",
#     "In welcher Stadt bist du geboren?",
#     "Wie lautet der Mädchenname deiner Mutter?"
# ]
# Add these routes to your existing FastAPI application

# @app.post("/api/password-reset/verify")
# async def verify_security_answers(request_data: dict):
#     """Verify a student's security answers before allowing password reset"""
#     username = request_data.get("username")
#     answers = request_data.get("answers", [])
    
#     if not username or len(answers) != 3:
#         raise HTTPException(status_code=400, detail="Missing username or answers")
    
#     success, message = db.verify_student_security_answers(username, answers)
    
#     if not success:
#         raise HTTPException(status_code=400, detail=message)
    
    # # Create temporary token for password reset
    # reset_token = secrets.token_hex(32)
    # return {"message": message, "reset_token": reset_token, "username": username}

# @app.get("/password-reset", response_class=HTMLResponse)
# async def password_reset_page(request: Request):
#     """Serve the password reset page"""
#     return templates.TemplateResponse("password-reset.html", {"request": request})

# @app.post("/api/password-reset")
# async def reset_password(request_data: dict):
#     """Reset a student's password after security answers have been verified"""
#     username = request_data.get("username")
#     new_password = request_data.get("new_password")
#     answers = request_data.get("answers", [])
    
#     if not username or not new_password or len(answers) != 3:
#         raise HTTPException(status_code=400, detail="Missing required fields")
    
#     # First verify the security answers
#     success, message = db.verify_student_security_answers(username, answers)
#     if not success:
#         raise HTTPException(status_code=400, detail=message)
    
#     # If answers are correct, reset the password
#     success, message = db.reset_student_password(username, new_password)
#     if not success:
#         raise HTTPException(status_code=400, detail=message)
    
#     return {"message": "Password reset successful"}

# ======<===================================
# Professor Routes
# =========================================

@app.get("/all/professors")
async def test_professors():
    return db.get_all_professors()

@app.get("/professor/dashboard", response_class=HTMLResponse)
async def professor_dashboard(request: Request):
    user = await verify_role(request, ["admin", "professor"])
    if isinstance(user, RedirectResponse):
        return user

    if user["role"] == "professor":
        classes = db.get_classes_for_professor(user["username"])
        return templates.TemplateResponse("classes.html", {
            "request": request,
            "user": user,
            "classes": classes
        })
    else:  # Falls Admin versehentlich diesen Pfad aufruft
        return RedirectResponse("/admin/dashboard")

    return templates.TemplateResponse("classes.html", {"request": request, "user": user})

@app.get("/api/professors")
async def api_professors():
    return {"professors": db.get_all_professors()}

# =========================================
# Admin Routes
# =========================================

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("admin_dashboard.html", {"request": request, "user": user})

@app.get("/admin/chathistory", response_class=HTMLResponse)
async def admin_chathistory(request: Request):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    classes = db.get_all_classes_with_courses()
    courses = db.get_all_courses()

    # Sichere Umwandlung der Query-Parameter
    selected_class_ids = [
        int(cid) for cid in request.query_params.getlist("class_id") if cid.isdigit()
    ]
    selected_course_ids = request.query_params.getlist("course_id")
    start_date = request.query_params.get("from")
    end_date = request.query_params.get("to")

    selected_class = None
    history = []

    # Wenn Filter aktiv → Chat-Historie laden
    if selected_class_ids or selected_course_ids or start_date or end_date:
        try:
            history = db.get_chat_history_filtered(
                class_ids=selected_class_ids if selected_class_ids else None,
                course_ids=selected_course_ids if selected_course_ids else None,
                start_date=start_date,
                end_date=end_date
            )
        except Exception as e:
            print(f"[ERROR] Fehler beim Laden der Chat-Historie: {e}")
            history = []

        # Erste ausgewählte Klasse anzeigen
        if selected_class_ids:
            try:
                selected_class = db.get_class_by_id(selected_class_ids[0])
            except Exception as e:
                print(f"[ERROR] Fehler bei selected_class: {e}")
                selected_class = None

    return templates.TemplateResponse("admin_chathistory.html", {
        "request": request,
        "user": user,
        "classes": classes,
        "courses": courses,
        "selected_class": selected_class,
        "history": history
    })

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
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    professors = db.get_all_professors_with_courses()

    # Hier wird error/success aus der URL gelesen
    error = request.query_params.get("error")
    success = request.query_params.get("success")

    return templates.TemplateResponse("admin_professors.html", {
        "request": request, 
        "user": user,
        "professors": professors,
        "error": error,
        "success": success
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
async def admin_delete_professor(request: Request, professor_username: str):
    """Delete a professor"""
    user = await verify_role(request, ["admin"])
    
    if isinstance(user, RedirectResponse):
        return user    # Prüfe ob Zielnutzer existiert
    target = db.get_user_by_username(professor_username)
    if not target:
        return RedirectResponse(url="/admin/professors", status_code=303)

    # Admins dürfen keine Admins löschen
    if target.get("role") == "admin":
        return RedirectResponse(url="/admin/professors", status_code=303)

    
    success, message = db.delete_professor(professor_username)

    # Clean redirect without exposing action details
    return RedirectResponse(url="/admin/professors", status_code=303)

# Add edit professor functionality
@app.get("/admin/professors/edit/{professor_username}", response_class=HTMLResponse)
async def admin_edit_professor_page(request: Request, professor_username: str): 
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user
    
    # Hole Professor-Daten aus der Datenbank
    connection = db.sql_connect()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM professors WHERE username = %s", (professor_username,))
    professor = cursor.fetchone()
    cursor.close()
    connection.close()
    
    if not professor:
        return RedirectResponse(
            url="/admin/professors?error=Professor nicht gefunden",
            status_code=303
        )

    # Beispiel: du könntest auf derselben Seite ein Inline-Edit-Formular anzeigen
    return templates.TemplateResponse("admin_professors.html", {
        "request": request, 
        "user": user,
        "professors": db.get_all_professors_with_courses(),
        "edit_professor": professor  # Übergib das zu bearbeitende Objekt
    })


@app.post("/admin/professors/edit/{professor_username}")
async def update_professor(
    request: Request,
    professor_username: str,
    first_name: str = Form(...),
    last_name: str = Form(...),
    role: str = Form(...)
):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    # UPDATE Logik in Datenbank (du kannst sie noch anpassen)
    connection = db.sql_connect()
    cursor = connection.cursor()
    cursor.execute("""
        UPDATE professors SET first_name=%s, last_name=%s, role=%s WHERE username=%s
    """, (first_name, last_name, role, professor_username))
    connection.commit()
    cursor.close()
    connection.close()

    return RedirectResponse(url="/admin/professors", status_code=303)



# =========================================
# API Routes
# =========================================

# Authentication API endpoints
@app.post("/api/auth/login/student")
async def api_student_login(username: str = Form(...), password: str = Form(...)):
    user = db.login_student(username, password)
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
    user = db.login_professor(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # RICHTIGE Weiterleitung nach Login
    redirect_url = "/admin/dashboard" if user.get("role") == "admin" else "/classes"
    
    response = JSONResponse({
        "success": True,
        "role": user.get("role"),
        "redirect_url": redirect_url
    })
    
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
        new_student = db.register_student(student_data)
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

@app.post("/admin/classes/delete/{class_id}")
async def admin_delete_class(request: Request, class_id: int):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    # Use the db function for deletion
    success, message = db.delete_class(class_id)

    # Clean redirect without exposing action details
    return RedirectResponse(url="/classes", status_code=303)

# =========================================
# PDFs
# =========================================

# PDF Overview
@app.get("/pdf", response_class=HTMLResponse)
async def pdf_overview(request: Request, class_id: int):
    user = await verify_role(request, ["professor", "admin"])
    if isinstance(user, RedirectResponse):
        return user

    pdfs = db.get_pdfs_for_class(class_id)
    cls = db.get_class_by_id(class_id)
    return templates.TemplateResponse("pdf.html", {
        "request": request,
        "user": user,
        "pdfs": pdfs,
        "class_id": int(class_id),
        "course": cls
    })

# PDF Upload
@app.post("/pdf", response_class=HTMLResponse)
async def upload_pdf(
    request: Request,
    class_id: int = Form(...),
    name: str = Form(...),
    pdf: UploadFile = File(...)
):
    user = await verify_role(request, ["professor", "admin"])
    cls = db.get_class_by_id(class_id)
    if not cls:
        return templates.TemplateResponse("pdf.html", {
            "request": request,
            "user": user,
            "pdfs": [],
            "error": "Klasse nicht gefunden."
        })
    content = await pdf.read()
    success, pdf_id = db.add_document({
        "name": name,
        "created_by": user["username"],
        "class_id": int(class_id),
        "file_type": pdf.content_type
    }, content)
    if not success:
        return templates.TemplateResponse("pdf.html", {
            "request": request,
            "user": user,
            "pdfs": [],
            "class_id": class_id,
            "course": cls,
            "error": pdf_id
        })
    await rag.ingest_pdf(pdf_id)
    pdfs = db.get_pdfs_for_class(class_id)
    return templates.TemplateResponse("pdf.html", {
        "request": request,
        "user": user,
        "pdfs": pdfs,
        "class_id": class_id,
        "course": cls,
        "success": "PDF erfolgreich hochgeladen."
    })

# PDF Delete
@app.post("/pdf/delete/{pdf_id}", response_class=HTMLResponse)
async def delete_pdf(request: Request, pdf_id: int):
    user = await verify_role(request, ["professor", "admin"])
    class_id = db.get_class_id_by_pdf(pdf_id)
    rag.delete_vectors_for_pdf(pdf_id)
    db.delete_pdf(pdf_id)
    return RedirectResponse(url="/pdf", status_code=303)


# =========================================
# Chat
# =========================================
@app.get("/chat/{class_id}", response_class=HTMLResponse)
async def chat_page(request: Request, class_id: int):
    user = await get_current_user(request)
    if isinstance(user, RedirectResponse):
        return user

    # Fetch class info from DB (implement db.get_class_by_id if needed)
    class_info = db.get_class_by_id(class_id)
    if not class_info:
        raise HTTPException(status_code=404, detail="Class not found")

    return templates.TemplateResponse("chat.html", {
        "request": request,
        "user": user,
        "class": class_info
    })

@app.post("/chat/{class_id}")
async def chat_api(class_id: int, body: dict, request: Request):
    user = await get_current_user(request)
    if isinstance(user, RedirectResponse):
        raise HTTPException(status_code=401, detail="Authentication required")
        
    prompt = body.get("prompt")
    if not prompt:
        return JSONResponse({"error": "No prompt provided"}, status_code=400)
    
    # Get the answer from RAG system
    result = await rag.chat_with_class(class_id, prompt)
    
    # Save to chat history
    db.save_chat_history(user["username"], class_id, prompt, result["answer"])
    
    return result

@app.post("/api/ingest_pdfs/{class_id}")
async def ingest_pdfs(class_id: int):
    return await rag.ingest_pdfs(class_id)

@app.post("/chat/{class_id}")
async def chat_api(class_id: int, body: dict):
    prompt = body.get("prompt")
    if not prompt:
        return JSONResponse({"error": "No prompt provided"}, status_code=400)
    return await rag.chat_with_class(class_id, prompt)

@app.get("/api/admin/chathistory/{course_id}")
async def api_admin_chathistory(course_id: str):
    """Return anonymized chat history for a course as JSON"""
    history = db.get_chat_history_by_course(course_id)
    return {"history": history}

@app.post("/admin/chathistory/reset/{class_id}")
async def admin_reset_chathistory(request: Request, class_id: int):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user    # Delete from DB and JSON
    db.delete_chat_history_for_class(class_id)

    # Clean redirect back to chathistory page
    return RedirectResponse(url="/admin/chathistory", status_code=303)


# =========================================	
# Admin Course Management
# =========================================

# Kursverwaltung anzeigen
@app.get("/admin/courses", response_class=HTMLResponse)
async def admin_courses(request: Request):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    courses = db.get_all_courses()
    student_counts = db.count_students_per_course()

    # Neu: Meldungen aus URL-Parametern lesen
    success = request.query_params.get("success")
    error = request.query_params.get("error")

    return templates.TemplateResponse("admin_courses.html", {
        "request": request,
        "user": user,
        "courses": courses,
        "student_counts": student_counts,
        "success": success,
        "error": error
    })



#Fehlermeldung 
# @app.get("/admin/courses")
# async def admin_courses(request: Request, success: Optional[str] = None, error: Optional[str] = None):
#     user = await verify_role(request, ["admin"])
#     courses = db.get_all_courses()
#     student_counts = db.get_student_counts_per_course()
    
#     return templates.TemplateResponse("admin_courses.html", {
#         "request": request,
#         "user": user,
#         "courses": courses,
#         "student_counts": student_counts,
#         "success": "Kurs erfolgreich hinzugefügt." if success else None,
#         "error": "Fehler beim Hinzufügen des Kurses." if error else None
#     })



# Kurs hinzufügen
@app.post("/admin/courses/add")
async def admin_add_course(
    request: Request,
    id: str = Form(...),
    name: str = Form(...),
    professor: str = Form(...)
):
    user = await verify_role(request, ["admin"])

    all_courses = db.get_all_courses()    # Prüfung: ID schon vergeben?
    if any(c["id"].lower() == id.lower() for c in all_courses):
        return RedirectResponse(url="/admin/courses", status_code=303)

    # Prüfung: Name schon vergeben?
    if any(c["name"].lower() == name.lower() for c in all_courses):
        return RedirectResponse(url="/admin/courses", status_code=303)

    db.add_course({
        "id": id,
        "name": name,
        "created_by": user["username"],
        "professor": professor
    })

    return RedirectResponse(url="/admin/courses", status_code=303)




#Fehlermeldung
# return RedirectResponse(url="/admin/courses?success=1", status_code=303)
# return RedirectResponse(url="/admin/courses?error=1", status_code=303)


# Kurs löschen
@app.post("/admin/courses/delete/{course_id}")
async def admin_delete_course(request: Request, course_id: str):
    await verify_role(request, ["admin"])
    db.delete_course(course_id)
    return RedirectResponse(url="/admin/courses", status_code=303)




# Kurs bearbeiten
@app.get("/admin/courses/edit/{course_id}", response_class=HTMLResponse)
async def admin_edit_course_inline(request: Request, course_id: str):
    user = await verify_role(request, ["admin"])
    courses = db.get_all_courses()
    edit_course = db.get_course_by_id(course_id)
    professors = db.get_all_professors()
    student_counts = db.count_students_per_course()
    return templates.TemplateResponse("admin_courses.html", {
        "request": request,
        "user": user,
        "courses": courses,
        "edit_course": edit_course,
        "professors": professors,
        "student_counts": student_counts
    })



# Kurs bearbeiten
@app.post("/admin/courses/edit/{course_id}")
async def admin_edit_course(
    request: Request,
    course_id: str,
    name: str = Form(...)
):
    await verify_role(request, ["admin"])    # Prüfung: Gleiche Beschreibung wie bei anderem Kurs?
    all_courses = db.get_all_courses()
    for course in all_courses:
        if course["id"] != course_id and course["name"].lower() == name.lower():
            return RedirectResponse(url="/admin/courses", status_code=303)

    db.update_course(course_id, name)

    return RedirectResponse(url="/admin/courses", status_code=303)


@app.get("/admin/students", response_class=HTMLResponse)
async def admin_students_page(request: Request):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    raw_students = db.get_all_students()
    students = [
        {
            "username": s["username"],  # noch für Link nötig
            "anonymized": s["anonymized"],  # <-- HINZUGEFÜGT
            "course": s.get("course", "")
        }
        for s in raw_students
    ]

    return templates.TemplateResponse("admin_students.html", {
        "request": request,
        "user": user,
        "students": students
    })



@app.post("/auth/delete")
async def delete_user(request: Request):
    # Cookie direkt auslesen
    session_token = request.cookies.get("session_token")
    user = db.get_user_by_session(session_token)

    if not user:
        return JSONResponse({"success": False, "message": "Du bist nicht eingeloggt."}, status_code=401)

    if user["role"] == "admin" and db.count_admins() <= 1:
        return JSONResponse({
            "success": False,
            "message": "Du bist der letzte Administrator. Mindestens ein Administrator muss erhalten bleiben."
        }, status_code=400)

    success = db.delete_current_user(user["username"], user["role"])
    if success:
        response = JSONResponse({"success": True, "message": "Dein Konto wurde erfolgreich gelöscht."})
        response.delete_cookie("session_token")
        return response
    else:
        return JSONResponse({"success": False, "message": "Fehler beim Löschen deines Kontos."}, status_code=500)
    
# =========================================
# Change Password
# =========================================

@app.get("/change/password", response_class=HTMLResponse)
async def change_password_page(request: Request):
    user = await get_current_user(request)
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("change_password.html", {"request": request, "user": user})

@app.post("/change/password", response_class=HTMLResponse)
async def change_password_action(
    request: Request,
    username: str = Form(...),
    old_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...)
):
    # Get the current user for template context
    user = await get_current_user(request)
    if isinstance(user, RedirectResponse):
        return user

    # Get the user by username for password verification
    target_user = db.get_user_by_username(username)
    if not target_user:
        return templates.TemplateResponse("change_password.html", {
            "request": request,
            "user": user,
            "error": "Benutzer nicht gefunden."
        })

    if not db.pwd_context.verify(old_password, target_user["password"]):
        return templates.TemplateResponse("change_password.html", {
            "request": request,
            "user": user,
            "error": "Aktuelles Passwort ist falsch."
        })

    if new_password != confirm_password:
        return templates.TemplateResponse("change_password.html", {
            "request": request,
            "user": user,
            "error": "Neue Passwörter stimmen nicht überein."
        })

    if new_password == old_password:
        return templates.TemplateResponse("change_password.html", {
            "request": request,
            "user": user,
            "error": "Neues Passwort darf nicht dem alten Passwort entsprechen."
        })

    hashed_new_password = db.pwd_context.hash(new_password)
    db.update_user_password(username, hashed_new_password)

    return templates.TemplateResponse("change_password.html", {
        "request": request,
        "user": user,
        "success": "Passwort erfolgreich geändert."
    })


@app.get("/admin/classes/edit/{class_id}", response_class=HTMLResponse)
async def edit_class_form(request: Request, class_id: int):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    class_data = db.get_class_by_id(class_id)
    if not class_data:
        return RedirectResponse(url="/admin/classes?error=Vorlesung nicht gefunden", status_code=303)

    all_courses = db.get_all_courses()

    return templates.TemplateResponse("edit_class_modal.html", {
        "request": request,
        "user": user,
        "edit_class": class_data,
        "courses": all_courses
    })


@app.post("/admin/classes/edit/{class_id}")
async def update_class_courses(
    request: Request,
    class_id: int,
    courses: Optional[List[int]] = Form(None)
):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    # Kurse aktualisieren (z. B. Join-Tabelle neu schreiben)
    db.update_class_courses(class_id, courses or [])

    return RedirectResponse(url="/admin/classes", status_code=303)
