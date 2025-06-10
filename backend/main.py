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
        "request": request,
        "deleted": request.query_params.get("deleted")
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

@app.get("/admin/classes", response_class=HTMLResponse)
async def admin_classes_page(request: Request):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    classes = db.get_all_classes()
    professors = db.get_all_professors_with_courses()
    professors = db.get_all_professors()  # Holt alle Prof-Datenbankeinträge

    return templates.TemplateResponse("classes.html", {
        "request": request,
        "user": user,
        "classes": classes,
        "professors": professors
    })



@app.post("/admin/classes", response_class=HTMLResponse)
async def admin_add_class(
    request: Request,
    name: str = Form(...),
    course: str = Form(...),
    taught_by: str = Form(...)
):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    # Insert new class into DB
    success, message = db.add_class({
        "name": name,
        "course_id": course,
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

@app.get("/all/professors")
async def test_professors():
    return db.get_all_professors()

# ======<===================================
# Professor Routes
# =========================================

# @app.get("/professor/dashboard", response_class=HTMLResponse)
# async def professor_dashboard(request: Request):
#     user = await verify_role(request, ["admin", "professor"])
#     if isinstance(user, RedirectResponse):
#         return user
#     return templates.TemplateResponse("admin_dashboard.html", {"request": request, "user": user})


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
    return templates.TemplateResponse("admin_chathistory.html", {"request": request, "user": user})

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
    
    success, message = db.delete_professor(professor_username)

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

    # Reload classes for display
    classes = db.get_all_classes()
    return templates.TemplateResponse("classes.html", {
        "request": request,
        "user": user,
        "classes": classes,
        "success" if success else "error": message
    })

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
    pdfs = db.get_pdfs_for_class(class_id)
    cls = db.get_class_by_id(class_id)
    return templates.TemplateResponse("pdf.html", {
        "request": request,
        "user": user,
        "pdfs": pdfs,
        "class_id": class_id,
        "course": cls,
        "success": "PDF erfolgreich gelöscht."
    })


# =========================================
# Chat
# =========================================
@app.get("/chat/{class_id}", response_class=HTMLResponse)
async def chat_page(request: Request, class_id: int):
    user = await get_current_user(request)
    if isinstance(user, RedirectResponse):
        return user
    cls = db.get_class_by_id(class_id)
    
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "user": user,
        "class": cls,
        "class_id": class_id
    })

@app.post("/api/ingest_pdfs/{class_id}")
async def ingest_pdfs(class_id: int):
    return await rag.ingest_pdfs(class_id)

@app.post("/chat/{class_id}")
async def chat_api(class_id: int, body: dict):
    prompt = body.get("prompt")
    if not prompt:
        return JSONResponse({"error": "No prompt provided"}, status_code=400)
    return await rag.chat_with_class(class_id, prompt)


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

    return templates.TemplateResponse("admin_courses.html", {
        "request": request,
        "user": user,
        "courses": courses,
        "student_counts": student_counts
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
    return templates.TemplateResponse("admin_courses.html", {
        "request": request,
        "user": user,
        "courses": courses,
        "edit_course": edit_course,
        "professors": professors
    })


# Kurs bearbeiten
@app.post("/admin/courses/edit/{course_id}")
async def admin_edit_course(
    request: Request,
    course_id: str,
    name: str = Form(...),
):
    await verify_role(request, ["admin"])
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






