# Technical Documentation – Vorlesungschatbot

## Overview

Vorlesungschatbot is a web-based platform for managing university courses, uploading course materials (PDFs), and providing a chatbot interface for students to ask questions about their course content. The system supports three user roles: **Admin**, **Professor**, and **Student**.

## Installation

### Prerequisites
- [Docker](https://www.docker.com/products/docker-desktop/) and [Docker Compose](https://docs.docker.com/compose/) installed on your system
- (Optional) [Git](https://git-scm.com/) to clone the repository

### Environment Configuration

#### Getting Started
1. **Clone the repository:**
   ```sh
   git clone <your-repo-url>
   cd chatbot
   ```

2. **Copy the example environment file:**
   ```sh
   cp .env.example .env
   ```

3. **Edit the `.env` file** with your specific configuration (see sections below)

#### MySQL Database Setup
The system supports two MySQL configuration options:

**Option 1: Use Docker Compose MySQL Container (Recommended for Development)**
```properties
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_ROOT_PASSWORD=root
MYSQL_DATABASE=chatbot
```
*Note: When using the Docker Compose setup, the MySQL database and all required tables are automatically created and initialized. No manual database setup is required.*

**Option 2: Use External MySQL Server**
If you have your own MySQL server, update the `.env` file with your server details:
```properties
MYSQL_HOST=your-mysql-server.example.com
MYSQL_PORT=3306
MYSQL_ROOT_PASSWORD=your-root-password
MYSQL_DATABASE=chatbot
```

**Important:** The database name must be `chatbot`. Make sure to create this database on your MySQL server before running the application:
```sql
CREATE DATABASE chatbot;
```
*Note: The database schema (tables, relationships, etc.) will be automatically initialized on application startup for both containerized and external MySQL setups.*

#### Setting Up Environment Variables
1. Copy the example environment file:
   ```sh
   cp .env.example .env
   ```
2. Edit the `.env` file with your specific configuration:
   - **LLM Configuration:** Choose between OpenAI GPT-4 or local Ollama
   - **OpenAI API:** Add your API key if using GPT-4
   - **Neo4j:** Configure your Neo4j cloud instance (required)
   - **MySQL:** Set your database connection details

#### Neo4j Database Configuration (Cloud-Based)
**Important:** This application requires a Neo4j cloud database for vector storage and document retrieval. You must set up a Neo4j AuraDB instance and configure the connection details:

1. **Create a Neo4j AuraDB instance:**
   - Go to [Neo4j AuraDB](https://neo4j.com/cloud/aura/)
   - Create a free or paid instance
   - Note down your connection URI, username, and password

2. **Configure Neo4j in `.env`:**
   ```properties
   NEO4J_URI=neo4j+s://your-instance-id.databases.neo4j.io
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your-generated-password
   ```

3. **Database initialization:**
   - The Neo4j database schema and vector indexes will be automatically created on first application startup
   - PDF documents will be processed and stored as vector embeddings in Neo4j

4. **Start the application:**
   
   **For Docker Compose with included MySQL:**
   ```sh
   docker-compose up --build
   ```
   
   **For external MySQL server:**
   - Ensure your MySQL server is running and accessible
   - Create the `chatbot` database
   - Run: `docker-compose up --build`

4. **Access the application:**
   - Open your browser and go to `http://localhost:8000`

    #### Default Admin Credentials
    - **Username:** kirchberg
    - **Password:** aperol77

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


## API Documentation

### 1. Overview
The Vorlesungschatbot API provides endpoints for user authentication, course management, document handling, and chat functionality. The API is built with FastAPI and supports role-based access control.

### 2. Database Structure
The system uses MySQL for relational data and Neo4j for vector storage of document embeddings.

### 3. General Information

#### 3.1 Base URL
```
http://localhost:8000
```

#### 3.2 Supported HTTP Methods
- `GET` - Retrieve data
- `POST` - Create new resources
- `PUT` - Update existing resources
- `DELETE` - Remove resources

#### 3.3 Response Formats
All API responses are in JSON format unless otherwise specified.

#### 3.4 Status Codes and Standard Behavior
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `500` - Internal Server Error

#### 3.5 Example Error Messages
```json
{
  "error": "Invalid credentials",
  "status_code": 401
}
```

#### 3.6 API Versioning
Currently using version 1.0 (no versioning in URLs)

### 4. Authentication and User Management

#### Student Authentication
- `login_student(username, password)` - Authenticate student users
- `register_student(student_data)` - Register new student
- `reset_student_password(username, new_password)` - Reset student password

#### Professor Authentication  
- `login_professor(username, password)` - Authenticate professor users

#### Session Management
- `get_user_by_session(session_token)` - Retrieve user by session token

#### User Management
- `delete_current_user(username, role)` - Delete user account

### 5. Professor Management

#### Professor Operations
- `get_all_professors()` - Retrieve all professors
- `get_all_professors_with_courses()` - Get professors with their assigned courses
- `add_professor(professor_data)` - Add new professor
- `delete_professor(professor_username)` - Remove professor

### 6. Course Management

#### Course Operations
- `get_all_courses()` - Retrieve all courses
- `add_course(course_data)` - Create new course
- `update_course(course_id, name)` - Update course information
- `delete_course(course_id)` - Remove course
- `get_course_by_id(course_id)` - Get specific course details
- `get_courses_for_user(user)` - Get courses for specific user

### 7. Class Management

#### Class Operations
- `get_all_classes()` - Retrieve all classes
- `get_class_by_id(class_id)` - Get specific class details
- `get_classes_for_student(username)` - Get classes for student
- `get_classes_for_professor(username)` - Get classes for professor
- `add_class(class_data)` - Create new class
- `delete_class(class_id)` - Remove class

### 8. Document Management (PDFs)

#### PDF Operations
- `get_pdfs_for_class(class_id)` - Get all PDFs for a class
- `get_document_by_id(pdf_id)` - Get specific document details
- `add_document(document_data, file_content)` - Upload new PDF document
- `delete_pdf(pdf_id)` - Remove PDF document

### 9. Chat History Management

#### Chat Operations
- `save_chat_history(user_id, class_id, question, answer)` - Save chat interaction
- `get_chat_history_by_course(course_id)` - Get chat history for course
- `get_chat_history_by_class(class_id)` - Get chat history for class
- `get_chat_history_filtered(...)` - Get filtered chat history
- `delete_chat_history_for_class(class_id)` - Remove chat history for class

### 10. System Functions and Analytics

#### System Operations
- `sql_connect()` - Establish database connection
- `initialize_database()` - Initialize database schema
- `reset_database()` - Reset database to initial state

#### Utility Functions
- `anonymize_username(username)` - Anonymize user identifiers for privacy-compliant processing
- `count_students_per_course()` - Get student statistics per course
- `count_admins()` - Count total administrators

### 11. Configuration

#### Environment Variables (.env file)
The system requires the following environment variables to be configured:

**Database Configuration:**
```properties
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_ROOT_PASSWORD=root
MYSQL_DATABASE=chatbot
```

**LLM Configuration:**
```properties
LLM=gpt-4                               # LLM selection: GPT-4 or LLaMA2
EMBEDDING_MODEL=sentence_transformer
OLLAMA_BASE_URL=http://host.docker.internal:11434
OPENAI_API_KEY=<your-openai-api-key>
```

**Neo4j Graph Database:**
```properties
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<your-neo4j-password>
```

### 12. Authentication

The API uses a simple session-token-based authentication model. After successful login, users receive a unique session token required for all protected requests.

#### Login Process

**Students:**
```python
login_student(username, password)
```

**Professors/Admins:**
```python
login_professor(username, password)
```

Both functions verify the username/password combination. After successful authentication, a random alphanumeric token is created and stored.

#### Session Validation
The token is transmitted with each protected request (e.g., in headers) and validated against the database:
```python
get_user_by_session(session_token)
```

#### Password Reset
Users can reset their password through security questions:
1. `verify_student_security_answers` - Verify security answers
2. `reset_student_password` - Reset password after verification

#### User Management
User accounts can be deleted using `delete_current_user`, with role-specific dependency checks (e.g., linked classes for professors).

**Note:** For production environments, implementing an enhanced authentication system (e.g., OAuth2, JWT) is recommended.

## FAQ

### Common Questions

**Q: How do I reset the database?**
A: Use the `reset_database()` function or restart the Docker containers with fresh volumes.

**Q: Can I use a local Neo4j instance instead of cloud?**
A: Yes, update the `NEO4J_URI` to point to your local instance (e.g., `bolt://localhost:7687`)

**Q: How do I add new user roles?**
A: Modify the authentication logic in `backend/main.py` and update the database schema accordingly.

**Q: What are the default login credentials?**
A: Admin - Username: `kirchberg`, Password: `aperol77`

## Troubleshooting

### Common Issues

**Docker containers won't start:**
- Check that Docker is running
- Verify environment variables in `.env` file
- Ensure ports 8000, 3306, and 7687 are available

**Database connection errors:**
- Verify MySQL credentials in `.env`
- Check if MySQL container is running: `docker-compose ps`
- Ensure database `chatbot` exists

**Neo4j connection issues:**
- Verify Neo4j credentials and URI
- Check firewall settings for cloud Neo4j instances
- Ensure Neo4j service is running

**Chat responses not working:**
- Check OpenAI API key validity
- Verify Ollama is running (if using local LLM)
- Ensure PDFs are properly uploaded and processed

## Backup

### Database Backup
```bash
# MySQL backup
docker exec mysql_container mysqldump -u root -p chatbot > backup.sql

# Restore MySQL backup
docker exec -i mysql_container mysql -u root -p chatbot < backup.sql
```

### File Backup
```bash
# Backup uploaded files and chat histories
tar -czf backup_files.tar.gz uploads/ chats/
```

### Neo4j Backup
Refer to Neo4j AuraDB documentation for cloud backup procedures, or use Neo4j dump utilities for local instances.