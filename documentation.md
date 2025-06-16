# Technical Documentation – Vorlesungschatbot

## Overview

Vorlesungschatbot is a web-based platform for managing university courses, uploading course materials (PDFs), and providing a chatbot interface for students to ask questions about their course content. The system supports three user roles: **Admin**, **Professor**, and **Student**.

## Architecture

- **Backend:** FastAPI (Python), MySQL, Neo4j (for vector storage), LangChain for RAG (Retrieval-Augmented Generation)
- **Frontend:** HTML (Jinja2 templates), CSS, JavaScript (with Bootstrap and FontAwesome)
- **Deployment:** Docker, Docker Compose

## Directory Structure

- [`backend`](backend): FastAPI backend, database operations, RAG logic
- [`frontend`](frontend): Static files and Jinja2 templates for the web UI
- [`uploads`](uploads): Uploaded PDF files
- [`chats`](chats): JSON files storing chat histories (anonymized)
- [`compose.yaml`](compose.yaml), [`Dockerfile`](Dockerfile): Deployment configuration

## Key Features

- **Authentication:** Role-based login for admins, professors, and students
- **Course Management:** Admins can create, edit, and delete courses and assign professors
- **PDF Management:** Professors and admins can upload, update, and delete course PDFs
- **Chatbot:** Students can ask questions about course materials; answers are generated using RAG with document retrieval from Neo4j
- **Chathistory:** Admins can view anonymized chat histories per course/class

## Backend

### Main Components

- [`backend/main.py`](backend/main.py): FastAPI app, route definitions, authentication, and template rendering
- [`backend/db.py`](backend/db.py): Database operations (MySQL), user management, course and PDF CRUD, chat history storage
- [`backend/rag.py`](backend/rag.py): PDF ingestion, vector storage in Neo4j, RAG-based question answering

### Notable Endpoints

- `/login`, `/register`: User authentication and registration
- `/admin/dashboard`: Admin dashboard
- `/admin/courses`: Course management (CRUD)
- `/admin/professors`: Professor management (CRUD)
- `/classes`: Course overview for students and professors
- `/pdf`: PDF upload and management
- `/chat/{class_id}`: Chatbot interface for a specific class

### Data Storage

- **MySQL:** Users, courses, classes, documents metadata
- **Neo4j:** Vector storage for document chunks (used by RAG)
- **Filesystem:** Uploaded PDFs ([`uploads`](uploads)), chat histories ([`chats`](chats))

## Frontend

- Uses Jinja2 templates for dynamic HTML rendering
- CSS styling in [`frontend/static/css/main.css`](frontend/static/css/main.css)
- JavaScript for form handling and dynamic UI updates

## Example User Flows

### Student

1. Registers and logs in
2. Views enrolled courses
3. Uploads security answers for password reset
4. Chats with the bot about course materials

### Professor

1. Logs in via `/login/professor`
2. Views and manages assigned courses
3. Uploads PDFs for courses

### Admin

1. Logs in via `/login`
2. Manages courses, professors, and students
3. Views anonymized chat histories

## Security

- Passwords and security answers are hashed using Passlib
- Role-based access control for all endpoints
- Chat histories are anonymized before storage

## Deployment

- Use Docker Compose:  
  ```sh
  docker-compose up --build
  ```
- Environment variables are managed via [`.env`](.env) files

## Extending the System

- Add new endpoints in [`backend/main.py`](backend/main.py)
- Add new database operations in [`backend/db.py`](backend/db.py)
- Update frontend templates in [`frontend/templates`](frontend/templates)

1. Installation
  1. End-user instructions
  2. how to set up llamafile / chatgpt-api
  3. how to use containers / host services in server (neo4j and mysql)
  4. how to set up his own environment files
  5. DB-Schema SQL (Egzona)
    1. default user is kirchberg password: aperol77
  6. how to prompt engineering
2. Specifications
  1. system infrastructure
  (what we already have)
  2. api documentation
3. (FAQs)
4. (Troubleshooting)
5. Backup