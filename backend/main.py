# FastAPI imports and utilities for route handling and request parsing
from typing import Optional, List
import logging
from fastapi import (
    FastAPI, Request, HTTPException,
    Body, Depends, Cookie, Form,
    UploadFile, File
    )

from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# Custom database and RAG module imports
import backend.db as db
import backend.rag as rag


# Create FastAPI instance and set up logging
app = FastAPI()
pwd_context = db.pwd_context

# Initialize DB connection
db.initialize_database()

# Configure frontend templates and static files
templates = Jinja2Templates(directory="frontend/templates")
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# =========================================
# Authentication Functions
# =========================================

# Get current logged-in user based on session token in cookie
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


# Validate that a user has one of the allowed roles
async def verify_role(request: Request, allowed_roles: list):
    """Verify that the user has one of the allowed roles"""
    user = await get_current_user(request)
    
    if isinstance(user, RedirectResponse):
        return user
    
    if user.get("role") not in allowed_roles:
        return RedirectResponse(url="/login/professor", status_code=302)
    return user

# =========================================
# Public Routes
# =========================================

# Homepage
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
    registered = request.query_params.get("registered")
    url = "/login/student"
    if registered:
        url += f"?registered={registered}"
    return RedirectResponse(url=url, status_code=302)

# Legacy route for professor login
@app.get("/login_professors", response_class=HTMLResponse)
async def legacy_professor_login_redirect(request: Request):
    return RedirectResponse(url="/login/professor", status_code=302)

# Legacy route for student registration
@app.get("/register", response_class=HTMLResponse)
async def legacy_register_redirect(request: Request):
    return RedirectResponse(url="/register/student", status_code=302)

# =========================================
# Authentication Routes
# =========================================

# logout route
@app.get("/auth/logout")
async def logout():
    response = RedirectResponse(url="/logout-page", status_code=302)  # Redirect to a logout page first
    response.delete_cookie(key="session_token", path="/", domain=None, secure=False, httponly=True)
    return response

# Logout page
@app.get("/logout-page", response_class=HTMLResponse)
async def logout_page(request: Request):
    return templates.TemplateResponse("logout.html", {"request": request})


# =========================================
# Student Routes
# =========================================

# Route to render the student dashboard page
# If the user is not authenticated or does not have the correct role, they are redirected
@app.get("/student/dashboard", response_class=HTMLResponse)
async def student_dashboard(request: Request):
    user = await verify_role(request, ["student"]) # Ensure user has the "student" role
    if isinstance(user, RedirectResponse):
        return user # Redirect if unauthorized
    return templates.TemplateResponse("student_dashboard.html", {"request": request, "user": user})


# Route to handle the creation of a new class (Vorlesung) by an admin
@app.post("/admin/classes", response_class=HTMLResponse)
async def admin_add_class(
    request: Request,
    name: str = Form(...),
    courses: list[str] = Form(...),  # This will now be a list
    taught_by: str = Form(...)
):
    user = await verify_role(request, ["admin"]) # Ensure user is an admin
    if isinstance(user, RedirectResponse):
        return user # Redirect unauthorized users

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

# Route to display the admin view for managing classes (Vorlesungen)
@app.get("/admin/classes", response_class=HTMLResponse)
async def admin_classes_page(request: Request):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    # Retrieve all classes, professors, and courses from the database
    classes = db.get_all_classes()
    professors = db.get_all_professors()
    courses = db.get_all_courses()

     # Check for optional success or error messages passed as URL query parameters
    success = request.query_params.get("success")
    error = request.query_params.get("error")

    # Render the admin classes management page with the retrieved data
    return templates.TemplateResponse("classes.html", {
        "request": request,
        "user": user,
        "classes": classes,
        "professors": professors,
        "courses": courses,
        "success": success,
        "error": error
    })  

# ======<===================================
# Professor Routes
# =========================================

# Route to return a list of all professors from the database
@app.get("/all/professors")
async def test_professors():
    return db.get_all_professors()

# Route for the professor dashboard
# Verifies that the user is either an admin or a professor
# - If the user is a professor, their associated classes are retrieved and shown
# - If an admin accesses this route by mistake, they are redirected to the admin dashboard
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
    else:  # If Admin calls this path by mistake
        return RedirectResponse("/admin/dashboard")

    return templates.TemplateResponse("classes.html", {"request": request, "user": user})

# API endpoint to retrieve all professors
# Returns a JSON object with a list of all professors from the database
@app.get("/api/professors")
async def api_professors():
    return {"professors": db.get_all_professors()}

# =========================================
# Admin Routes
# =========================================

# Route to render the admin dashboard
@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("admin_dashboard.html", {"request": request, "user": user})

# Admin Chat History Page
# Allows admin users to view chat history, optionally filtered by class, course, or date range
@app.get("/admin/chathistory", response_class=HTMLResponse)
async def admin_chathistory(request: Request):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user
    
    # Load all courses and classes for filtering options
    courses = db.get_all_courses()
    classes = db.get_all_classes()
    
    # Read filter parameters from query string
    selected_class_ids = [
        int(cid) for cid in request.query_params.getlist("class_id") if cid.isdigit()
    ]
    selected_course_ids = request.query_params.getlist("course_id")
    start_date = request.query_params.get("from")
    end_date = request.query_params.get("to")
    
    # Get filtered and grouped chat history
    history = {}
    selected_class = None
    filter_info = None  # Add this to show what's being filtered
    
    if selected_class_ids or selected_course_ids or start_date or end_date:
        history = db.get_chat_history_filtered_grouped(
            class_ids=selected_class_ids if selected_class_ids else None,
            course_ids=selected_course_ids if selected_course_ids else None,
            start_date=start_date,
            end_date=end_date
        )
        
        # Set selected_class if only one class is selected
        if len(selected_class_ids) == 1:
            selected_class = db.get_class_by_id(selected_class_ids[0])
        
        # Create filter description
        filter_parts = []
        if selected_class_ids:
            if len(selected_class_ids) == 1:
                class_name = db.get_class_by_id(selected_class_ids[0])['name']
                filter_parts.append(f"Vorlesung: {class_name}")
            else:
                filter_parts.append(f"{len(selected_class_ids)} Vorlesungen")
        
        if selected_course_ids:
            if len(selected_course_ids) == 1:
                course_name = db.get_course_by_id(selected_course_ids[0])['name']
                filter_parts.append(f"Kurs: {course_name}")
            else:
                filter_parts.append(f"{len(selected_course_ids)} Kurse")
        
        if start_date or end_date:
            if start_date and end_date:
                filter_parts.append(f"Zeitraum: {start_date} bis {end_date}")
            elif start_date:
                filter_parts.append(f"Ab: {start_date}")
            elif end_date:
                filter_parts.append(f"Bis: {end_date}")
        
        filter_info = " | ".join(filter_parts) if filter_parts else "Alle Filter"
    
     # Render the chat history template with the filtered results
    return templates.TemplateResponse("admin_chathistory.html", {
        "request": request,
        "user": user,
        "courses": courses,
        "classes": classes,
        "history": history,
        "selected_class": selected_class,
        "filter_info": filter_info 
    })

# Displays the list of classes to the logged-in user based on their role.
# - Students see only the classes they are enrolled in.
# - Professors see only the classes they teach.
# - Admins see all classes.
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
    
# =========================================
# Admin Professor Management
# =========================================

# Displays the list of professors and their courses for admin users
@app.get("/admin/professors", response_class=HTMLResponse)
async def admin_professors_page(request: Request):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    professors = db.get_all_professors_with_courses()

    # Read success or error messages from URL parameters
    # This allows us to show messages after actions like adding or deleting professors
    error = request.query_params.get("error")
    success = request.query_params.get("success")

    # Render the admin professors management page with the retrieved data
    return templates.TemplateResponse("admin_professors.html", {
        "request": request, 
        "user": user,
        "professors": professors,
        "error": error,
        "success": success
    })

# Route to add a new professor
# This route handles the form submission for adding a new professor
# It verifies that the user is an admin and processes the form data
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

# Route to delete a professor
# This route handles the deletion of a professor by their username
@app.post("/admin/professors/delete/{professor_username}")
async def admin_delete_professor(request: Request, professor_username: str):
    """Delete a professor"""
    user = await verify_role(request, ["admin"])
    
    if isinstance(user, RedirectResponse):
        return user
    
    # Check if target user exists
    target = db.get_user_by_username(professor_username)
    if not target:
        return RedirectResponse(url="/admin/professors?error=Benutzer nicht gefunden.", status_code=303)

    # Admins are not allowed to delete admins
    if target.get("role") == "admin":
        return RedirectResponse(url="/admin/professors?error=Administratoren können nicht gelöscht werden.", status_code=303)

    # Try to delete the professor
    success, message = db.delete_professor(professor_username)
    
    if success:
        return RedirectResponse(url="/admin/professors?success=Benutzer erfolgreich gelöscht.", status_code=303)
    else:
        return RedirectResponse(url="/admin/professors?error=" + message, status_code=303)


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

    # Example: you could display an inline edit form on the same page
    return templates.TemplateResponse("admin_professors.html", {
        "request": request, 
        "user": user,
        "professors": db.get_all_professors_with_courses(),
        "edit_professor": professor  # Transfer the object to be edited
    })

# Route to update a professor's details
# This route handles the form submission for editing a professor's information
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

    # UPDATE logic in database 
    connection = db.sql_connect()
    cursor = connection.cursor()
    cursor.execute("""
        UPDATE professors SET first_name=%s, last_name=%s, role=%s WHERE username=%s
    """, (first_name, last_name, role, professor_username))
    connection.commit()
    cursor.close()
    connection.close()

    return RedirectResponse(url="/admin/professors?success=Benutzer erfolgreich aktualisiert.", status_code=303)




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

# Professor login API endpoint
@app.post("/api/auth/login/professor")
async def api_professor_login(username: str = Form(...), password: str = Form(...)):
    user = db.login_professor(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # CORRECT forwarding after login
    redirect_url = "/admin/dashboard" if user.get("role") == "admin" else "/classes"
    
    response = JSONResponse({
        "success": True,
        "role": user.get("role"),
        "redirect_url": redirect_url
    })
    
    response.set_cookie(key="session_token", value=user.get("session_token"))
    return response

# API endpoint to verify whether a user is currently authenticated.
# - If the user is authenticated, return their role.
# - If not authenticated or an error occurs, return `authenticated: False`.
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

# API endpoint to log out the user
# - Deletes the session token cookie and returns a success message.
@app.post("/api/auth/logout")
async def api_logout():
    response = JSONResponse({"success": True})
    response.delete_cookie(key="session_token", path="/", domain=None, secure=False, httponly=True)
    return response

# API endpoint for student registration
# - Accepts student data in JSON format and registers a new student.
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

# Legacy API endpoint for professor login.
# For backward compatibility: simply forwards login requests to the modern `api_professor_login` handler.
@app.post("/api/login_professors")
async def legacy_api_professor_login(username: str = Form(...), password: str = Form(...)):
    return await api_professor_login(username, password)

# Legacy API endpoint for logging out.
# For backward compatibility: delegates to the modern `api_logout` endpoint to clear the session cookie.
@app.post("/api/logout")
async def legacy_api_logout():
    return await api_logout()

# Legacy API endpoint for student registration.
@app.post("/api/register")
async def legacy_api_register(student_data: dict = Body(...)):
    return await api_register(student_data)

# =========================================
# Classes
# =========================================

# Admin endpoint to delete a specific class by its ID.
# Verifies the user has admin privileges, then calls the DB deletion function.
# Redirects back to the admin class management page with a success message.
@app.post("/admin/classes/delete/{class_id}")
async def admin_delete_class(request: Request, class_id: int):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    # Use the db function for deletion
    success, message = db.delete_class(class_id)

    # Clean redirect without exposing action details
    return RedirectResponse(url="/admin/classes?success=Vorlesung erfolgreich gelöscht.", status_code=303)


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

# Endpoint for professors and admins to upload a PDF file for a specific class.
# - Validates user role and class existence.
# - Reads the uploaded PDF content and stores its metadata and content in the database.
# - Triggers the RAG pipeline to process and embed the PDF content.
# - Renders the PDF management page with the updated list and a success or error message.
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

# Endpoint to delete a PDF file by its ID.
# Accessible only to users with the role 'professor' or 'admin'.
# - Retrieves the class ID associated with the PDF.
# - Deletes any vector data linked to the PDF (e.g., embeddings from the RAG system).
# - Removes the PDF record and file from the database.
# - Redirects the user back to the PDF overview page for the same class.
@app.post("/pdf/delete/{pdf_id}", response_class=HTMLResponse)
async def delete_pdf(request: Request, pdf_id: int):
    user = await verify_role(request, ["professor", "admin"])
    class_id = db.get_class_id_by_pdf(pdf_id)
    rag.delete_vectors_for_pdf(pdf_id)
    db.delete_pdf(pdf_id)
    return RedirectResponse(url=f"/pdf?class_id={class_id}", status_code=303)


# =========================================
# Chat
# =========================================

# Route to display the chat interface for a specific class.
# - Requires user to be authenticated.
# - Retrieves the class details from the database using the class_id.
# - If the class is not found, returns a 404 error.
# - Renders the 'chat.html' template, passing the user and class information.
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

# Route to handle user chat input and return chatbot response for a specific class.
# - Requires the user to be authenticated.
# - Expects a JSON body with a 'prompt' field.
# - Uses the RAG system to generate a response based on the class context.
# - Saves the chat interaction to the chat history for future reference.
# - Returns the generated result to the frontend.
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

# API endpoint to manually trigger ingestion of all PDFs for a given class.
# - Accepts a class ID as a path parameter.
# - Calls the RAG system to (re)process and index all associated PDF documents.
# - Returns the result of the ingestion process.
@app.post("/api/ingest_pdfs/{class_id}")
async def ingest_pdfs(class_id: int):
    return await rag.ingest_pdfs(class_id)

# Lightweight chat API endpoint (no authentication).
# - Accepts a class ID as a path parameter.
# - Expects a JSON body with a "prompt" key containing the user's question.
# - Returns the generated answer from the RAG system for the given class.
@app.post("/chat/{class_id}")
async def chat_api(class_id: int, body: dict):
    prompt = body.get("prompt")
    if not prompt:
        return JSONResponse({"error": "No prompt provided"}, status_code=400)
    return await rag.chat_with_class(class_id, prompt)

# API endpoint for administrators to retrieve anonymized chat history for a specific course.
# - Accepts a course ID as a path parameter.
# - Calls the database function to fetch anonymized chat records related to that course.
# - Returns the chat history as a JSON object.
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

# Admin endpoint to delete chat history based on selected filters (class, course, date range).
# - Accepts lists of class_ids and course_ids from the form.
# - Parses optional "from" and "to" date range from query parameters.
# - Uses db.delete_chat_history_filtered() to remove only matching chat records.
# - On success or failure, redirects back to the admin chat history page with appropriate status info.
@app.post("/admin/chathistory/reset_filtered")
async def reset_filtered_chat_history(request: Request, class_id: List[str] = Form([]), course_id: List[str] = Form([])):
    user = await get_current_user(request)
    await verify_role(request, ["admin"])
    
    try:
        # Convert class_ids to integers
        class_ids = [int(cid) for cid in class_id if cid.isdigit()]
        
        # Use the new filtered deletion function instead of deleting entire classes
        success = db.delete_chat_history_filtered(
            class_ids=class_ids if class_ids else None,
            course_ids=course_id if course_id else None,
            start_date=request.query_params.get("from"),
            end_date=request.query_params.get("to")
        )
        
        if success:
            return RedirectResponse(url="/admin/chathistory?success=filtered_reset", status_code=303)
        else:
            return RedirectResponse(url="/admin/chathistory?error=filtered_reset_failed", status_code=303)
            
    except Exception as e:
        logging.error(f"Error resetting filtered chat history: {e}")
        return RedirectResponse(url="/admin/chathistory?error=filtered_reset_failed", status_code=303)

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

    # New: Read messages from URL parameters
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

# add course form
@app.post("/admin/courses/add")
async def admin_add_course(
    request: Request,
    id: str = Form(...),
    name: str = Form(...),
    professor: str = Form(...)
):
    user = await verify_role(request, ["admin"])

   
    all_courses = db.get_all_courses()   

    # Check: ID already assigned?
    if any(c["id"].lower() == id.lower() for c in all_courses):
        return RedirectResponse(url="/admin/courses", status_code=303)

    # Check: Name already assigned?
    if any(c["name"].lower() == name.lower() for c in all_courses):
        return RedirectResponse(url="/admin/courses", status_code=303)

    db.add_course({
        "id": id,
        "name": name,
        "created_by": user["username"],
        "professor": professor
    })

    return RedirectResponse(url="/admin/courses?success=Kurs erfolgreich hinzugefügt.", status_code=303)

# delete course
@app.post("/admin/courses/delete/{course_id}")
async def admin_delete_course(request: Request, course_id: str):
    await verify_role(request, ["admin"])
    success, message = db.delete_course(course_id)
    
    if success:
        from urllib.parse import quote
        return RedirectResponse(url=f"/admin/courses?success={quote(message)}", status_code=303)
    else:
        from urllib.parse import quote
        return RedirectResponse(url=f"/admin/courses?error={quote(message)}", status_code=303)

# Admin endpoint to display all students in the system.
# - Only accessible to users with the "admin" role.
# - Retrieves all student records from the database.
# - Each student entry includes: username, anonymization status, and course (if available).
# - Passes the data to the 'admin_students.html' template for rendering in the UI.
@app.get("/admin/students", response_class=HTMLResponse)
async def admin_students_page(request: Request):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    raw_students = db.get_all_students()
    students = [
        {
            "username": s["username"],  
            "anonymized": s["anonymized"],  
            "course": s.get("course", "")
        }
        for s in raw_students
    ]

    return templates.TemplateResponse("admin_students.html", {
        "request": request,
        "user": user,
        "students": students
    })


# Endpoint to delete the currently authenticated user's account.
# - Reads the session token directly from the user's cookies.
# - Verifies the session token to identify the user.
# - Prevents deletion if the user is the last remaining admin.
# - Calls the database function to delete the user account.
# - On success, returns a JSON response and deletes the session cookie.
# - On failure or if unauthorized, returns an appropriate error message.
@app.post("/auth/delete")
async def delete_user(request: Request):
    
    # Read cookie directly
    session_token = request.cookies.get("session_token")
    user = db.get_user_by_session(session_token)

    if not user:
        return JSONResponse({"success": False, "message": "Du bist nicht eingeloggt."}, status_code=401)

    # Prevent deletion if user is the last admin
    if user["role"] == "admin" and db.count_admins() <= 1:
        return JSONResponse({
            "success": False,
            "message": "Du bist der letzte Administrator. Mindestens ein Administrator muss erhalten bleiben."
        }, status_code=400)

    # Delete the user account
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

# Endpoint to render the change password page.
# - Checks if the user is authenticated.
@app.get("/change/password", response_class=HTMLResponse)
async def change_password_page(request: Request):
    user = await get_current_user(request)
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("change_password.html", {"request": request, "user": user})

# Endpoint for handling user password change requests.
# - Accepts the current and new passwords via form data.
# - Retrieves the currently logged-in user from the session.
# - Verifies that the provided username exists.
# - Checks if the current password is correct.
# - Ensures the new password and confirmation match.
# - Prevents the user from reusing the old password.
# - Hashes and updates the password in the database.
# - Returns an HTML response with either success or error messages.
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
    
    # Verify current password
    if not db.pwd_context.verify(old_password, target_user["password"]):
        return templates.TemplateResponse("change_password.html", {
            "request": request,
            "user": user,
            "error": "Aktuelles Passwort ist falsch."
        })

    # Check if new password and confirmation match
    if new_password != confirm_password:
        return templates.TemplateResponse("change_password.html", {
            "request": request,
            "user": user,
            "error": "Neue Passwörter stimmen nicht überein."
        })

    # Check if new password is the same as the old password
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

# Admin-only endpoint to display the class edit form.
# - Verifies that the user has admin privileges.
# - Retrieves the class with the given class_id for editing.
# - Loads all available classes and courses for context (e.g., dropdowns).
# - Renders the "classes.html" template with the necessary data.
# - Logs any exceptions and returns a 500 error if something goes wrong.
@app.get("/admin/classes/edit/{class_id}")
async def edit_class_form(class_id: int, request: Request, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        # Get the class to edit
        edit_class = db.get_class_by_id(class_id)
        if not edit_class:
            raise HTTPException(status_code=404, detail="Class not found")
        
        # Get all classes for the main list
        all_classes = db.get_all_classes()  # Changed to use correct function name
        # Get all courses for the form
        all_courses = db.get_all_courses()  # Changed to use correct function name
        
        return templates.TemplateResponse("classes.html", {
            "request": request,
            "user": current_user,
            "classes": all_classes,
            "courses": all_courses,
            "edit_class": edit_class
        })
    except Exception as e:
        logging.error(f"Error loading edit class form: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Admin endpoint to update a class's courses.
# - Verifies that the user has admin privileges.
@app.post("/admin/classes/edit/{class_id}")
async def update_class_courses(
    request: Request,
    class_id: int,
    courses: Optional[List[str]] = Form(None)  # Changed from List[int] to List[str]
):
    user = await verify_role(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    # Update courses (e.g. rewrite join table)
    db.update_class_courses(class_id, courses or [])

    return RedirectResponse(url="/admin/classes?success=Vorlesung erfolgreich aktualisiert.", status_code=303)

