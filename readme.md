# Technische Dokumentation – Vorlesungschatbot DE

**🇬🇧 [Jump to English Version](#technical-documentation--vorlesungschatbot-en)**

## Inhaltsverzeichnis

1. [Überblick](#überblick)
2. [Installation](#installation)
3. [Architektur](#architektur)
4. [Verzeichnisstruktur](#verzeichnisstruktur)
5. [Hauptmerkmale](#hauptmerkmale)
6. [Backend](#backend)
7. [Frontend](#frontend)
8. [Beispielbenutzerflüsse](#beispielbenutzerflüsse)
9. [Sicherheit](#sicherheit)
10. [API-Dokumentation](#api-dokumentation)
11. [FAQ](#faq)
12. [Fehlerbehebung](#fehlerbehebung)
13. [Backup](#backup)

---

## Überblick

Der Vorlesungschatbot ist eine webbasierte Plattform zur Verwaltung von Universitätskursen, zum Hochladen von Kursmaterialien (PDFs) und zur Bereitstellung einer Chatbot-Schnittstelle für Studierende, um Fragen zu ihren Kursinhalten zu stellen. Das System unterstützt drei Benutzerrollen: **Administrator**, **Professor** und **Student**.

## Installation

### Voraussetzungen
- [Docker](https://www.docker.com/products/docker-desktop/) und [Docker Compose](https://docs.docker.com/compose/) auf Ihrem System installiert
- (Optional) [Git](https://git-scm.com/) zum Klonen des Repositories

### Umgebungskonfiguration

#### Erste Schritte
1. **Repository klonen:**
   ```sh
   git clone https://github.com/franrmueller/chatbot.git
   cd chatbot
   ```

2. **Beispiel-Umgebungsdatei kopieren:**
   ```sh
   cp .env.example .env
   ```

3. **Bearbeiten Sie die `.env`-Datei** mit Ihrer spezifischen Konfiguration (siehe Abschnitte unten)
   - **LLM-Konfiguration:** Wählen Sie zwischen OpenAI GPT-4 oder lokalem Ollama
   - **OpenAI API:** Fügen Sie Ihren API-Schlüssel hinzu, wenn Sie GPT-4 verwenden
   - **Neo4j:** Konfigurieren Sie Ihre Neo4j-Cloud-Instanz (erforderlich)
   - **MySQL:** Setzen Sie Ihre Datenbankverbindungsdetails

#### MySQL-Datenbank-Setup
Das System unterstützt zwei MySQL-Konfigurationsoptionen:

**Option 1: Docker Compose MySQL Container verwenden (Empfohlen für Entwicklung)**
```properties
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_ROOT_PASSWORD=root
MYSQL_DATABASE=chatbot
```
*Hinweis: Bei Verwendung des Docker Compose-Setups werden die MySQL-Datenbank und alle erforderlichen Tabellen automatisch erstellt und initialisiert. Es ist keine manuelle Datenbankeinrichtung erforderlich.*

**Option 2: Externen MySQL-Server verwenden**
Wenn Sie Ihren eigenen MySQL-Server haben, aktualisieren Sie die `.env`-Datei mit Ihren Serverdetails:
```properties
MYSQL_HOST=your-mysql-server.example.com
MYSQL_PORT=3306
MYSQL_ROOT_PASSWORD=your-root-password
MYSQL_DATABASE=chatbot
```

**Wichtig:** Der Datenbankname muss `chatbot` sein. Stellen Sie sicher, dass Sie diese Datenbank auf Ihrem MySQL-Server erstellen, bevor Sie die Anwendung ausführen:
```sql
CREATE DATABASE chatbot;
```
*Hinweis: Das Datenbankschema (Tabellen, Beziehungen usw.) wird beim Anwendungsstart automatisch für sowohl containerisierte als auch externe MySQL-Setups initialisiert.*

#### Neo4j-Datenbank-Konfiguration (Cloud-basiert)
**Wichtig:** Diese Anwendung benötigt eine Neo4j-Cloud-Datenbank für die Vektorspeicherung und Dokumentenabfrage. Sie müssen eine Neo4j AuraDB-Instanz einrichten und die Verbindungsdetails konfigurieren:

1. **Neo4j AuraDB-Instanz erstellen:**
   - Gehen Sie zu [Neo4j AuraDB](https://neo4j.com/cloud/aura/)
   - Erstellen Sie eine kostenlose oder kostenpflichtige Instanz
   - Notieren Sie sich Ihre Verbindungs-URI, Benutzername und Passwort

2. **Neo4j in `.env` konfigurieren:**
   ```properties
   NEO4J_URI=neo4j+s://your-instance-id.databases.neo4j.io
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your-generated-password
   ```

3. **Datenbankinitialisierung:**
   - Das Neo4j-Datenbankschema und die Vektorindizes werden beim ersten Anwendungsstart automatisch erstellt
   - PDF-Dokumente werden verarbeitet und als Vektoreinbettungen in Neo4j gespeichert

4. **Anwendung starten:**
   
   **Für Docker Compose mit integriertem MySQL:**
   ```sh
   docker-compose up --build
   ```
   
   **Für externen MySQL-Server:**
   - Stellen Sie sicher, dass Ihr MySQL-Server läuft und erreichbar ist
   - Erstellen Sie die `chatbot`-Datenbank
   - Führen Sie aus: `docker-compose up --build`

4. **Auf die Anwendung zugreifen:**
   - Öffnen Sie Ihren Browser und gehen Sie zu `http://localhost:8000`

    #### Standard-Admin-Anmeldeinformationen
    - **Benutzername:** kirchberg
    - **Passwort:** aperol77

## Architektur

- **Backend:** FastAPI (Python), MySQL, Neo4j (für Vektorspeicherung), LangChain für RAG (Retrieval-Augmented Generation)
- **Frontend:** HTML (Jinja2-Vorlagen), CSS, JavaScript (mit Bootstrap und FontAwesome)
- **Bereitstellung:** Docker, Docker Compose

### Datenbankschema

Das System verwendet MySQL zur Speicherung relationaler Daten mit folgendem Schema:

#### Tabellenstruktur

**professors**
```sql
CREATE TABLE professors (
    username VARCHAR(50) PRIMARY KEY,
    password VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    role VARCHAR(9) DEFAULT 'professor',
    session_token VARCHAR(64) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**courses**
```sql
CREATE TABLE courses (
    id VARCHAR(15) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(50) NOT NULL,
    FOREIGN KEY (created_by) REFERENCES professors(username)
)
```

**students**
```sql
CREATE TABLE students (
    username VARCHAR(50) PRIMARY KEY,
    password VARCHAR(255) NOT NULL,
    course VARCHAR(15),
    session_token VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course) REFERENCES courses(id)
)
```

**classes**
```sql
CREATE TABLE classes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    taught_by VARCHAR(50) NOT NULL,
    FOREIGN KEY (taught_by) REFERENCES professors(username)
)
```

**class_courses** (Verknüpfungstabelle für viele-zu-viele Beziehung)
```sql
CREATE TABLE class_courses (
    class_id INT,
    course_id VARCHAR(15),
    PRIMARY KEY (class_id, course_id),
    FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
)
```

**documents**
```sql
CREATE TABLE documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(50) NOT NULL,
    class_id INT NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    content_extracted BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (class_id) REFERENCES classes(id),
    FOREIGN KEY (created_by) REFERENCES professors(username)
)
```

**chat_history**
```sql
CREATE TABLE chat_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_hash VARCHAR(40) NOT NULL,  -- Anonymisierte Benutzerkennung
    class_id INT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
)
```

#### Standarddaten
- **Admin-Benutzer:** Benutzername: `kirchberg`, Passwort: `aperol77`
- **Standardkurs:** `WWI-BE122` - "Wirtschaftsinformatik - Business Engineering"
- **Standardklasse:** "Datenbanken" (assoziiert mit dem Standardkurs)

### Neo4j Graph-Datenbankstruktur

Das System verwendet Neo4j als Vektordatenbank für die Speicherung und den Abruf von Dokumenteneinbettungen, die für die RAG (Retrieval-Augmented Generation) Funktionalität des Chatbots verwendet werden.

#### Node-Typen

**PdfBotChunk**
```cypher
(:PdfBotChunk {
    text: STRING,           // Der Textinhalt des Dokumentenchunks
    embedding: VECTOR,      // Vektoreinbettung des Textes (384 Dimensionen)
    class_id: INTEGER,      // Referenz zur Klassen-ID in MySQL
    source: STRING          // Dateipfad des ursprünglichen PDF-Dokuments
})
```

**Question** (für erweiterte Funktionalität)
```cypher
(:Question {
    id: STRING,             // Eindeutige Fragekennung
    title: STRING,          // Fragetitel
    body: STRING,           // Frageinhalt
    score: INTEGER,         // Bewertung der Frage
    embedding: VECTOR       // Vektoreinbettung der Frage
})
```

**Answer** (für erweiterte Funktionalität)
```cypher
(:Answer {
    id: STRING,             // Eindeutige Antwortkennung
    body: STRING,           // Antwortinhalt
    score: INTEGER,         // Bewertung der Antwort
    embedding: VECTOR       // Vektoreinbettung der Antwort
})
```

**User** (für erweiterte Funktionalität)
```cypher
(:User {
    id: STRING,             // Eindeutige Benutzerkennung
    display_name: STRING    // Anzeigename des Benutzers
})
```

**Tag** (für erweiterte Funktionalität)
```cypher
(:Tag {
    name: STRING            // Tag-Name
})
```

#### Vektorindizes

Das System erstellt automatisch Vektorindizes für die semantische Suche:

```cypher
// Hauptindex für PDF-Chunks
CALL db.index.vector.createNodeIndex(
    'pdf_bot',              // Index-Name
    'PdfBotChunk',         // Node-Label
    'embedding',           // Eigenschaft mit Vektoreinbettungen
    384,                   // Dimension (abhängig vom Embedding-Modell)
    'cosine'               // Similarity-Metrik
)

// Erweiterte Indizes für zukünftige Funktionen
CALL db.index.vector.createNodeIndex('stackoverflow', 'Question', 'embedding', 384, 'cosine')
CALL db.index.vector.createNodeIndex('top_answers', 'Answer', 'embedding', 384, 'cosine')
```

#### Constraints

```cypher
CREATE CONSTRAINT question_id IF NOT EXISTS FOR (q:Question) REQUIRE (q.id) IS UNIQUE
CREATE CONSTRAINT answer_id IF NOT EXISTS FOR (a:Answer) REQUIRE (a.id) IS UNIQUE
CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE (u.id) IS UNIQUE
CREATE CONSTRAINT tag_name IF NOT EXISTS FOR (t:Tag) REQUIRE (t.name) IS UNIQUE
```

#### Datenfluss und Verarbeitung

1. **PDF-Upload**: Wenn ein PDF hochgeladen wird, wird es in Textchunks von ~1000 Zeichen mit 200 Zeichen Überlappung aufgeteilt
2. **Einbettungsgenerierung**: Jeder Chunk wird mit dem konfigurierten Embedding-Modell (Standard: SentenceTransformer "all-MiniLM-L6-v2") in einen 384-dimensionalen Vektor umgewandelt
3. **Speicherung**: Die Chunks werden als `PdfBotChunk`-Nodes mit ihren Metadaten gespeichert
4. **Abfrage**: Bei Chatbot-Anfragen wird eine Vektorähnlichkeitssuche durchgeführt, um relevante Chunks zu finden
5. **Filterung**: Die Suche wird nach `class_id` gefiltert, um nur relevante Dokumente für die jeweilige Klasse zurückzugeben

#### Embedding-Modell-Konfiguration

Das System unterstützt verschiedene Embedding-Modelle:

- **SentenceTransformer** (Standard): 384 Dimensionen
- **Ollama**: 768 Dimensionen  
- **Bedrock**: 1536 Dimensionen

Die Dimensionalität der Vektorindizes wird automatisch basierend auf dem gewählten Modell konfiguriert.

#### RAG-Workflow

1. **Benutzeranfrage** wird als Vektor eingebettet
2. **Cosinus-Ähnlichkeitssuche** findet die relevantesten Dokumentenchunks
3. **Kontext-Aufbau** aus den gefundenen Chunks
4. **LLM-Antwortgenerierung** mit dem bereitgestellten Kontext
5. **Quellenangaben** werden aus den Metadaten der gefundenen Chunks extrahiert

#### Standarddaten
- **Admin-Benutzer:** Benutzername: `kirchberg`, Passwort: `aperol77`
- **Standardkurs:** `WWI-BE122` - "Wirtschaftsinformatik - Business Engineering"
- **Standardklasse:** "Datenbanken" (assoziiert mit dem Standardkurs)

#### Wichtige Beziehungen
- Professoren können mehrere Klassen unterrichten
- Klassen können mit mehreren Kursen verknüpft sein (viele-zu-viele über `class_courses`)
- Studenten sind in einen Kurs eingeschrieben, können aber auf mehrere Klassen innerhalb dieses Kurses zugreifen
- Dokumente werden bestimmten Klassen zugeordnet
- Der Chatverlauf ist anonymisiert und mit Klassen verknüpft, um die Datenschutzbestimmungen einzuhalten
- **Neo4j PdfBotChunks** sind über `class_id` mit MySQL-Klassen verknüpft und ermöglichen klassenspezifische Dokumentenabfragen

## Verzeichnisstruktur

- [`backend`](backend): FastAPI-Backend, Datenbankoperationen, RAG-Logik
- [`frontend`](frontend): Statische Dateien und Jinja2-Vorlagen für die Web-Benutzeroberfläche
- [`uploads`](uploads): Hochgeladene PDF-Dateien
- [`chats`](chats): JSON-Dateien, die Chatverläufe speichern (anonymisiert)
- [`compose.yaml`](compose.yaml), [`Dockerfile`](Dockerfile): Bereitstellungskonfiguration

## Hauptmerkmale

- **Authentifizierung:** Rollenbasierte Anmeldung für Administratoren, Professoren und Studenten
- **Kursverwaltung:** Administratoren können Kurse erstellen, bearbeiten und löschen sowie Professoren zuweisen
- **PDF-Verwaltung:** Professoren und Administratoren können Kurs-PDFs hochladen, aktualisieren und löschen
- **Chatbot:** Studenten können Fragen zu Kursmaterialien stellen; die Antworten werden mithilfe von RAG mit Dokumentenabfrage aus Neo4j generiert
- **Chatverlauf:** Administratoren können anonymisierte Chatverläufe pro Kurs/Klasse einsehen

## Empfehlungen für Dokumenten-Upload

Für eine optimale Leistung des Chatbots und zur effizienten Nutzung der Vektordatenbank sollten Sie folgende Richtlinien beim Hochladen von Dokumenten beachten:

### Bevorzugte Dokumenttypen
- **Lehrbücher und Fachbücher:** PDF-Versionen der Bücher, auf denen die Vorlesung basiert
- **Fachspezifische Literatur:** Relevante wissenschaftliche Artikel und Fachpublikationen
- **Umfassende Lernmaterialien:** Detaillierte Studienunterlagen mit ausführlichen Erklärungen

### Zu vermeidende Dokumenttypen
- **Vorlesungsfolien:** Standard-PowerPoint-Folien enthalten meist nur Stichpunkte und wenig Kontext
- **Kurze Zusammenfassungen:** Oberflächliche Materialien ohne tiefgreifende Erklärungen
- **Präsentationen:** Folien-basierte Dokumente mit geringem Textinhalt

### Best Practices
- **Selektiver Upload:** Laden Sie nur die Kapitel/Abschnitte der Bücher hoch, die in der Vorlesung behandelt werden
- **Platzoptimierung:** Dies spart Speicherplatz in der Vektordatenbank und verbessert die Antwortqualität
- **Qualität vor Quantität:** Wenige, aber inhaltlich reiche Dokumente sind besser als viele oberflächliche Materialien
- **Zusammenhängende Inhalte:** Stellen Sie sicher, dass die hochgeladenen Abschnitte thematisch zusammenhängen

### Warum diese Empfehlungen?
Der Chatbot funktioniert am besten mit detaillierten, erklärenden Texten, die Konzepte vollständig beschreiben. Lehrbücher bieten diesen Kontext, während Vorlesungsfolien oft nur Schlagworte enthalten, die für den Chatbot schwer zu verarbeiten sind.

## Backend

### Hauptkomponenten

- [`backend/main.py`](backend/main.py): FastAPI-App, Routen-Definitionen, Authentifizierung und Vorlagen-Rendering
- [`backend/db.py`](backend/db.py): Datenbankoperationen (MySQL), Benutzerverwaltung, Kurs- und PDF-CRUD, Speicherung des Chatverlaufs
- [`backend/rag.py`](backend/rag.py): PDF-Import, Vektorspeicherung in Neo4j, RAG-basiertes Fragen und Antworten

### Bemerkenswerte Endpunkte

- `/login`, `/register`: Benutzer-Authentifizierung und -Registrierung
- `/admin/dashboard`: Admin-Dashboard
- `/admin/courses`: Kursverwaltung (CRUD)
- `/admin/professors`: Professorenverwaltung (CRUD)
- `/classes`: Kursübersicht für Studenten und Professoren
- `/pdf`: PDF-Hochladung und -Verwaltung
- `/chat/{class_id}`: Chatbot-Schnittstelle für eine bestimmte Klasse

### Datenspeicherung

- **MySQL:** Benutzer, Kurse, Klassen, Dokumentenmetadaten
- **Neo4j:** Vektorspeicherung für Dokumentenstücke (verwendet von RAG)
- **Dateisystem:** Hochgeladene PDFs ([`uploads`](uploads)), Chatverläufe ([`chats`](chats))

## Frontend

- Verwendet Jinja2-Vorlagen für die dynamische HTML-Generierung
- CSS-Styles in [`frontend/static/css/main.css`](frontend/static/css/main.css)
- JavaScript für Formularverarbeitung und dynamische UI-Aktualisierungen

## Beispielbenutzerflüsse

### Student

1. Registriert sich und meldet sich an
2. Sieht sich die eingeschriebenen Kurse an
3. Lädt Sicherheitsantworten für die Passwortzurücksetzung hoch
4. Chattet mit dem Bot über Kursmaterialien

### Professor

1. Meldet sich an über `/login/professor`
2. Sieht und verwaltet zugewiesene Kurse
3. Lädt PDFs für Kurse hoch

### Admin

1. Meldet sich an über `/login`
2. Verwaltet Kurse, Professoren und Studenten
3. Sieht anonymisierte Chatverläufe

## Sicherheit

- Passwörter und Sicherheitsantworten werden mit Passlib gehasht
- Rollenbasierte Zugriffskontrolle für alle Endpunkte
- Chatverläufe werden vor der Speicherung anonymisiert

## API-Dokumentation

### 1. Überblick
Die Vorlesungschatbot-API bietet Endpunkte für die Benutzer-Authentifizierung, Kursverwaltung, Dokumentenverwaltung und Chat-Funktionalität. Die API ist mit FastAPI erstellt und unterstützt die rollenbasierte Zugriffskontrolle.

### 2. Datenbankstruktur
Das System verwendet MySQL für relationale Daten und Neo4j für die Vektorspeicherung von Dokumenteneinbettungen.

### 3. Allgemeine Informationen

#### 3.1 Basis-URL
```
http://localhost:8000
```

#### 3.2 Unterstützte HTTP-Methoden
- `GET` - Daten abrufen
- `POST` - Neue Ressourcen erstellen
- `PUT` - Vorhandene Ressourcen aktualisieren
- `DELETE` - Ressourcen entfernen

#### 3.3 Antwortformate
Alle API-Antworten liegen im JSON-Format vor, sofern nicht anders angegeben.

#### 3.4 Statuscodes und Standardverhalten
- `200` - Erfolg
- `201` - Erstellt
- `400` - Ungültige Anfrage
- `401` - Nicht autorisiert
- `403` - Verboten
- `404` - Nicht gefunden
- `500` - Interner Serverfehler

#### 3.5 Beispiel-Fehlermeldungen
```json
{
  "error": "Invalid credentials",
  "status_code": 401
}
```

#### 3.6 API-Versionierung
Derzeit wird Version 1.0 verwendet (keine Versionierung in URLs)

### 4. Authentifizierung und Benutzerverwaltung

#### Studenten-Authentifizierung
- `login_student(username, password)` - Authentifiziert Studentenbenutzer
- `register_student(student_data)` - Registriert neuen Studenten
- `reset_student_password(username, new_password)` - Setzt das Studentenpasswort zurück

#### Professoren-Authentifizierung  
- `login_professor(username, password)` - Authentifiziert Professorenbenutzer

#### Sitzungsverwaltung
- `get_user_by_session(session_token)` - Ruft Benutzer anhand des Sitzungstokens ab

#### Benutzerverwaltung
- `delete_current_user(username, role)` - Löscht Benutzerkonto

### 5. Professorenverwaltung

#### Professoren-Operationen
- `get_all_professors()` - Ruft alle Professoren ab
- `get_all_professors_with_courses()` - Holt Professoren mit ihren zugewiesenen Kursen
- `add_professor(professor_data)` - Fügt neuen Professor hinzu
- `delete_professor(professor_username)` - Entfernt Professor

### 6. Kursverwaltung

#### Kurs-Operationen
- `get_all_courses()` - Ruft alle Kurse ab
- `add_course(course_data)` - Erstellt neuen Kurs
- `update_course(course_id, name)` - Aktualisiert Kursinformationen
- `delete_course(course_id)` - Entfernt Kurs
- `get_course_by_id(course_id)` - Holt spezifische Kursdetails
- `get_courses_for_user(user)` - Holt Kurse für spezifischen Benutzer

### 7. Klassenverwaltung

#### Klassen-Operationen
- `get_all_classes()` - Ruft alle Klassen ab
- `get_class_by_id(class_id)` - Holt spezifische Klassendetails
- `get_classes_for_student(username)` - Holt Klassen für Studenten
- `get_classes_for_professor(username)` - Holt Klassen für Professoren
- `add_class(class_data)` - Erstellt neue Klasse
- `delete_class(class_id)` - Entfernt Klasse

### 8. Dokumentenverwaltung (PDFs)

#### PDF-Operationen
- `get_pdfs_for_class(class_id)` - Holt alle PDFs für eine Klasse
- `get_document_by_id(pdf_id)` - Holt spezifische Dokumentdetails
- `add_document(document_data, file_content)` - Lädt neues PDF-Dokument hoch
- `delete_pdf(pdf_id)` - Entfernt PDF-Dokument

### 9. Verwaltung des Chatverlaufs

#### Chat-Operationen
- `save_chat_history(user_id, class_id, question, answer)` - Speichert Chat-Interaktion
- `get_chat_history_by_course(course_id)` - Holt Chatverlauf für Kurs
- `get_chat_history_by_class(class_id)` - Holt Chatverlauf für Klasse
- `get_chat_history_filtered(...)` - Holt gefilterten Chatverlauf
- `delete_chat_history_for_class(class_id)` - Entfernt Chatverlauf für Klasse

### 10. Systemfunktionen und Analysen

#### Systemoperationen
- `sql_connect()` - Stellt Datenbankverbindung her
- `initialize_database()` - Initialisiert das Datenbankschema
- `reset_database()` - Setzt die Datenbank auf den ursprünglichen Zustand zurück

#### Hilfsfunktionen
- `anonymize_username(username)` - Anonymisiert Benutzerkennungen für datenschutzkonforme Verarbeitung
- `count_students_per_course()` - Holt Studentenstatistiken pro Kurs
- `count_admins()` - Zählt die Gesamtzahl der Administratoren

### 11. Konfiguration

#### Umgebungsvariablen (.env-Datei)
Das System erfordert die Konfiguration der folgenden Umgebungsvariablen:

**Datenbankkonfiguration:**
```properties
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_ROOT_PASSWORD=root
MYSQL_DATABASE=chatbot
```

**LLM-Konfiguration:**
```properties
LLM=gpt-4                               # LLM-Auswahl: GPT-4 oder LLaMA2
EMBEDDING_MODEL=sentence_transformer
OLLAMA_BASE_URL=http://host.docker.internal:11434
OPENAI_API_KEY=<your-openai-api-key>
```

**Neo4j Graphdatenbank:**
```properties
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<your-neo4j-password>
```

### 12. Authentifizierung

Die API verwendet ein einfaches authentifizierungsbasiertes Sitzungsmodell. Nach erfolgreicher Anmeldung erhalten Benutzer ein eindeutiges Sitzungstoken, das für alle geschützten Anfragen erforderlich ist.

#### Anmeldeprozess

**Studenten:**
```python
login_student(username, password)
```

**Professoren/Administratoren:**
```python
login_professor(username, password)
```

Beide Funktionen überprüfen die Benutzername/Passwort-Kombination. Nach erfolgreicher Authentifizierung wird ein zufälliges alphanumerisches Token erstellt und gespeichert.

#### Sitzungsvalidierung
Das Token wird mit jeder geschützten Anfrage (z. B. in Headern) übertragen und gegen die Datenbank validiert:
```python
get_user_by_session(session_token)
```

#### Passwortzurücksetzung
Benutzer können ihr Passwort über Sicherheitsfragen zurücksetzen:
1. `verify_student_security_answers` - Überprüfen der Sicherheitsantworten
2. `reset_student_password` - Zurücksetzen des Passworts nach der Überprüfung

#### Benutzerverwaltung
Benutzerkonten können mit `delete_current_user` gelöscht werden, wobei rollenbasierte Abhängigkeitprüfungen (z. B. verknüpfte Klassen für Professoren) durchgeführt werden.

**Hinweis:** Für Produktionsumgebungen wird empfohlen, ein verbessertes Authentifizierungssystem (z. B. OAuth2, JWT) zu implementieren.

## FAQ

### Häufige Fragen

**F: Wie setze ich die Datenbank zurück?**
A: Verwenden Sie die Funktion `reset_database()` oder starten Sie die Docker-Container mit neuen Volumes neu.

**F: Kann ich eine lokale Neo4j-Instanz anstelle der Cloud verwenden?**
A: Ja, aktualisieren Sie die `NEO4J_URI`, um auf Ihre lokale Instanz zu verweisen (z. B. `bolt://localhost:7687`)

**F: Wie füge ich neue Benutzerrollen hinzu?**
A: Ändern Sie die Authentifizierungslogik in `backend/main.py` und aktualisieren Sie das Datenbankschema entsprechend.

**F: Was sind die Standard-Anmeldeinformationen?**
A: Admin - Benutzername: `kirchberg`, Passwort: `aperol77`

## Fehlerbehebung

### Häufige Probleme

**Docker-Container starten nicht:**
- Stellen Sie sicher, dass Docker läuft
- Überprüfen Sie die Umgebungsvariablen in der `.env`-Datei
- Stellen Sie sicher, dass die Ports 8000, 3306 und 7687 verfügbar sind

**Datenbankverbindungsfehler:**
- Überprüfen Sie die MySQL-Anmeldeinformationen in der `.env`
- Überprüfen Sie, ob der MySQL-Container läuft: `docker-compose ps`
- Stellen Sie sicher, dass die Datenbank `chatbot` existiert

**Neo4j-Verbindungsprobleme:**
- Überprüfen Sie die Neo4j-Anmeldeinformationen und die URI
- Überprüfen Sie die Firewall-Einstellungen für Cloud-Neo4j-Instanzen
- Stellen Sie sicher, dass der Neo4j-Dienst läuft

**Chat-Antworten funktionieren nicht:**
- Überprüfen Sie die Gültigkeit des OpenAI-API-Schlüssels
- Stellen Sie sicher, dass Ollama läuft (wenn lokales LLM verwendet wird)
- Stellen Sie sicher, dass PDFs ordnungsgemäß hochgeladen und verarbeitet werden

## Backup

### Datenbank-Backup
```bash
# MySQL-Backup
docker exec mysql_container mysqldump -u root -p chatbot > backup.sql

# MySQL-Backup wiederherstellen
docker exec -i mysql_container mysql -u root -p chatbot < backup.sql
```

### Datei-Backup
```bash
# Sichern Sie hochgeladene Dateien und Chatverläufe
tar -czf backup_files.tar.gz uploads/ chats/
```

### Neo4j-Backup
Bitte beachten Sie die Dokumentation zu Neo4j AuraDB für Cloud-Backup-Verfahren oder verwenden Sie die Neo4j-Dump-Dienstprogramme für lokale Instanzen.

---

# Technical Documentation – Vorlesungschatbot EN

## Table of Contents

1. [Overview](#overview-1)
2. [Installation](#installation-1)
3. [Architecture](#architecture-1)
4. [Directory Structure](#directory-structure-1)
5. [Key Features](#key-features-1)
6. [Backend](#backend-1)
7. [Frontend](#frontend-1)
8. [Example User Flows](#example-user-flows-1)
9. [Security](#security-1)
10. [API Documentation](#api-documentation-1)
11. [FAQ](#faq-1)
12. [Troubleshooting](#troubleshooting-1)
13. [Backup](#backup-1)

---

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
   git clone https://github.com/franrmueller/chatbot.git
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

### Database Schema

The system uses MySQL for relational data storage with the following schema:

#### Tables Structure

**professors**
```sql
CREATE TABLE professors (
    username VARCHAR(50) PRIMARY KEY,
    password VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    role VARCHAR(9) DEFAULT 'professor',
    session_token VARCHAR(64) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**courses**
```sql
CREATE TABLE courses (
    id VARCHAR(15) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(50) NOT NULL,
    FOREIGN KEY (created_by) REFERENCES professors(username)
)
```

**students**
```sql
CREATE TABLE students (
    username VARCHAR(50) PRIMARY KEY,
    password VARCHAR(255) NOT NULL,
    course VARCHAR(15),
    session_token VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course) REFERENCES courses(id)
)
```

**classes**
```sql
CREATE TABLE classes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    taught_by VARCHAR(50) NOT NULL,
    FOREIGN KEY (taught_by) REFERENCES professors(username)
)
```

**class_courses** (Junction table for many-to-many relationship)
```sql
CREATE TABLE class_courses (
    class_id INT,
    course_id VARCHAR(15),
    PRIMARY KEY (class_id, course_id),
    FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
)
```

**documents**
```sql
CREATE TABLE documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(50) NOT NULL,
    class_id INT NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    content_extracted BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (class_id) REFERENCES classes(id),
    FOREIGN KEY (created_by) REFERENCES professors(username)
)
```

**chat_history**
```sql
CREATE TABLE chat_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_hash VARCHAR(40) NOT NULL,  -- Anonymized user identifier
    class_id INT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
)
```

#### Default Data
- **Admin User:** username: `kirchberg`, password: `aperol77`
- **Default Course:** `WWI-BE122` - "Wirtschaftsinformatik - Business Engineering"
- **Default Class:** "Datenbanken" (associated with the default course)

### Neo4j Graph Database Structure

The system uses Neo4j as a vector database for storing and retrieving document embeddings used for the chatbot's RAG (Retrieval-Augmented Generation) functionality.

#### Node Types

**PdfBotChunk**
```cypher
(:PdfBotChunk {
    text: STRING,           // The text content of the document chunk
    embedding: VECTOR,      // Vector embedding of the text (384 dimensions)
    class_id: INTEGER,      // Reference to class ID in MySQL
    source: STRING          // File path of the original PDF document
})
```

**Question** (for extended functionality)
```cypher
(:Question {
    id: STRING,             // Unique question identifier
    title: STRING,          // Question title
    body: STRING,           // Question content
    score: INTEGER,         // Question rating
    embedding: VECTOR       // Vector embedding of the question
})
```

**Answer** (for extended functionality)
```cypher
(:Answer {
    id: STRING,             // Unique answer identifier
    body: STRING,           // Answer content
    score: INTEGER,         // Answer rating
    embedding: VECTOR       // Vector embedding of the answer
})
```

**User** (for extended functionality)
```cypher
(:User {
    id: STRING,             // Unique user identifier
    display_name: STRING    // User display name
})
```

**Tag** (for extended functionality)
```cypher
(:Tag {
    name: STRING            // Tag name
})
```

#### Vector Indexes

The system automatically creates vector indexes for semantic search:

```cypher
// Main index for PDF chunks
CALL db.index.vector.createNodeIndex(
    'pdf_bot',              // Index name
    'PdfBotChunk',         // Node label
    'embedding',           // Property with vector embeddings
    384,                   // Dimension (depends on embedding model)
    'cosine'               // Similarity metric
)

// Extended indexes for future features
CALL db.index.vector.createNodeIndex('stackoverflow', 'Question', 'embedding', 384, 'cosine')
CALL db.index.vector.createNodeIndex('top_answers', 'Answer', 'embedding', 384, 'cosine')
```

#### Constraints

```cypher
CREATE CONSTRAINT question_id IF NOT EXISTS FOR (q:Question) REQUIRE (q.id) IS UNIQUE
CREATE CONSTRAINT answer_id IF NOT EXISTS FOR (a:Answer) REQUIRE (a.id) IS UNIQUE
CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE (u.id) IS UNIQUE
CREATE CONSTRAINT tag_name IF NOT EXISTS FOR (t:Tag) REQUIRE (t.name) IS UNIQUE
```

#### Data Flow and Processing

1. **PDF Upload**: When a PDF is uploaded, it is split into text chunks of ~1000 characters with 200 character overlap
2. **Embedding Generation**: Each chunk is converted into a 384-dimensional vector using the configured embedding model (default: SentenceTransformer "all-MiniLM-L6-v2")
3. **Storage**: The chunks are stored as `PdfBotChunk` nodes with their metadata
4. **Query**: During chatbot requests, a vector similarity search is performed to find relevant chunks
5. **Filtering**: The search is filtered by `class_id` to return only relevant documents for the respective class

#### Embedding Model Configuration

The system supports various embedding models:

- **SentenceTransformer** (default): 384 dimensions
- **Ollama**: 768 dimensions  
- **Bedrock**: 1536 dimensions

The dimensionality of vector indexes is automatically configured based on the chosen model.

#### RAG Workflow

1. **User query** is embedded as a vector
2. **Cosine similarity search** finds the most relevant document chunks
3. **Context building** from the found chunks
4. **LLM response generation** with the provided context
5. **Source citations** are extracted from the metadata of found chunks

#### Default Data
- **Admin User:** username: `kirchberg`, password: `aperol77`
- **Default Course:** `WWI-BE122` - "Wirtschaftsinformatik - Business Engineering"
- **Default Class:** "Datenbanken" (associated with the default course)

#### Key Relationships
- Professors can teach multiple classes
- Classes can be associated with multiple courses (many-to-many via `class_courses`)
- Students are enrolled in one course but can access multiple classes within that course
- Documents are uploaded to specific classes
- Chat history is anonymized and linked to classes for privacy compliance
- **Neo4j PdfBotChunks** are linked to MySQL classes via `class_id` enabling class-specific document queries

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

## Document Upload Recommendations

For optimal chatbot performance and efficient use of the vector database, please follow these guidelines when uploading documents:

### Preferred Document Types
- **Textbooks and Academic Books:** PDF versions of books on which the class is based
- **Specialized Literature:** Relevant academic articles and professional publications
- **Comprehensive Learning Materials:** Detailed study materials with thorough explanations

### Document Types to Avoid
- **Lecture Slides:** Standard PowerPoint slides usually contain only bullet points with little context
- **Brief Summaries:** Superficial materials without in-depth explanations
- **Presentations:** Slide-based documents with minimal text content

### Best Practices
- **Selective Upload:** Only upload the chapters/sections of books that are covered in the class
- **Space Optimization:** This saves space in the vector database and improves answer quality
- **Quality over Quantity:** Few but content-rich documents are better than many superficial materials
- **Coherent Content:** Ensure that uploaded sections are thematically connected

### Why These Recommendations?
The chatbot works best with detailed, explanatory texts that fully describe concepts. Textbooks provide this context, while lecture slides often contain only keywords that are difficult for the chatbot to process effectively.

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