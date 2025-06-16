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

### Installation Steps
1. **Clone the repository:**
   ```sh
   git clone <your-repo-url>
   cd chatbot
   ```

2. **Configure environment variables** (see section above)

3. **Start the application:**
   
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

### Default Admin Credentials
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

## Extending the System

- Add new endpoints in [`backend/main.py`](backend/main.py)
- Add new database operations in [`backend/db.py`](backend/db.py)
- Update frontend templates in [`frontend/templates`](frontend/templates)

## Specifications
  1. system infrastructure
  (what we already have)
  2. api documentation
## (FAQs)
## (Troubleshooting)
## Backup