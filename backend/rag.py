import os
import logging
import PyPDF2
from typing import List, Any, Optional
from dotenv import load_dotenv
from neo4j import GraphDatabase
from backend import db
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain.vectorstores.neo4j_vector import Neo4jVector

# ========== CONFIGURATION ==========
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Environment variables
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence_transformer")
LLM = os.getenv("LLM", "llama2")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# ========== NEO4J SETUP ==========

def create_vector_index(driver, dimension: int) -> None:
    """Create vector indexes for Neo4j."""
    indexes = [
        ("stackoverflow", "Question", "embedding"),
        ("top_answers", "Answer", "embedding")
    ]
    
    for index_name, label, property_name in indexes:
        index_query = f"CALL db.index.vector.createNodeIndex('{index_name}', '{label}', '{property_name}', $dimension, 'cosine')"
        try:
            driver.query(index_query, {"dimension": dimension})
        except Exception as e:
            logger.warning(f"Index {index_name} might already exist: {e}")

def create_constraints(driver):
    """Create database constraints."""
    constraints = [
        "CREATE CONSTRAINT question_id IF NOT EXISTS FOR (q:Question) REQUIRE (q.id) IS UNIQUE",
        "CREATE CONSTRAINT answer_id IF NOT EXISTS FOR (a:Answer) REQUIRE (a.id) IS UNIQUE",
        "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE (u.id) IS UNIQUE",
        "CREATE CONSTRAINT tag_name IF NOT EXISTS FOR (t:Tag) REQUIRE (t.name) IS UNIQUE"
    ]
    
    for constraint in constraints:
        try:
            driver.query(constraint)
        except Exception as e:
            logger.warning(f"Constraint might already exist: {e}")

# ========== MODEL LOADING ==========

def load_embedding_model():
    """Load the appropriate embedding model based on configuration."""
    from langchain.embeddings import (
        OllamaEmbeddings,
        SentenceTransformerEmbeddings,
        BedrockEmbeddings,
    )
    
    if EMBEDDING_MODEL.lower() == "ollama":
        return OllamaEmbeddings(base_url=OLLAMA_BASE_URL), 768
    elif EMBEDDING_MODEL.lower() == "bedrock":
        return BedrockEmbeddings(), 1536
    else:
        return SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2"), 384

def load_llm():
    """Load the appropriate LLM based on configuration."""
    from langchain.chat_models import ChatOpenAI, ChatOllama, BedrockChat
    
    if LLM.lower().startswith("gpt"):
        return ChatOpenAI(model=LLM)
    elif LLM.lower() == "bedrock":
        return BedrockChat()
    else:
        return ChatOllama(base_url=OLLAMA_BASE_URL)

# Initialize models
embeddings, embedding_dimension = load_embedding_model()
llm = load_llm()

# ========== VECTORSTORE OPERATIONS ==========

def get_vectorstore() -> Neo4jVector:
    """Get Neo4j vector store instance."""
    logger.info(f"Connecting to Neo4j at {NEO4J_URI} with user {NEO4J_USERNAME}")
    return Neo4jVector(
        url=NEO4J_URI,
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD,
        embedding=embeddings,
        index_name="pdf_bot",
        node_label="PdfBotChunk",
    )

def delete_vectors_for_pdf(pdf_id: int) -> bool:
    """Delete all vectors/embeddings for a specific PDF from Neo4j."""
    try:
        doc = db.get_document_by_id(pdf_id)
        if not doc:
            logger.warning(f"No document found with id: {pdf_id}")
            return False
        
        file_name = doc.get("name", "")
        file_path = os.path.join(os.getcwd(), 'uploads', file_name)
        
        vectorstore = get_vectorstore()
        driver = vectorstore._driver
        
        with driver.session() as session:
            result = session.run(
                "MATCH (n:PdfBotChunk {source: $source}) DETACH DELETE n",
                source=file_path
            )
            
            summary = result.consume()
            deleted_count = summary.counters.nodes_deleted
            logger.info(f"Deleted {deleted_count} vector nodes for PDF: {file_path}")
            
        return True
    except Exception as e:
        logger.error(f"Error deleting vectors for PDF {pdf_id}: {str(e)}")
        return False

# ========== PDF PROCESSING ==========

def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from a PDF file."""
    try:
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text
        return text
    except Exception as e:
        logger.error(f"Error extracting text from {file_path}: {e}")
        return ""

def split_text_into_chunks(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    """Split text into chunks for processing."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, 
        chunk_overlap=chunk_overlap
    )
    return splitter.split_text(text)

async def ingest_pdf(pdf_id: int) -> dict:
    """Ingest a single PDF into the vector database."""
    try:
        doc = db.get_document_by_id(pdf_id)
        if not doc:
            logger.warning(f"No document found with id: {pdf_id}")
            return {"success": False, "error": "Document not found"}
        
        # Get file path
        upload_dir = os.path.join(os.getcwd(), 'uploads')
        file_name = doc.get("name", "")
        file_path = os.path.join(upload_dir, file_name)
        
        if not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            return {"success": False, "error": "File not found"}
        
        # Extract and process text
        text = extract_text_from_pdf(file_path)
        if not text:
            logger.warning(f"No text extracted from: {file_path}")
            return {"success": False, "error": "No text extracted"}
        
        chunks = split_text_into_chunks(text)
        logger.info(f"Extracted {len(chunks)} chunks from {file_path}")
        
        if not chunks:
            logger.warning("No chunks to upload.")
            return {"success": False, "error": "No chunks to upload"}
        
        # Create metadata
        metadatas = [{"class_id": doc.get("class_id"), "source": file_path}] * len(chunks)
        
        # Upload to Neo4j
        logger.info(f"Uploading {len(chunks)} chunks to Neo4j...")
        Neo4jVector.from_texts(
            texts=chunks,
            embedding=embeddings,
            url=NEO4J_URI,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            index_name="pdf_bot",
            node_label="PdfBotChunk",
            metadatas=metadatas,
            pre_delete_collection=False,
        )
        
        logger.info("Upload complete.")
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Error ingesting PDF {pdf_id}: {str(e)}")
        return {"success": False, "error": str(e)}

async def ingest_pdfs(class_id: int) -> dict:
    """Ingest all PDFs for a class into the vector database."""
    try:
        pdfs = db.get_pdfs_for_class(class_id)
        all_texts = []
        metadatas = []
        upload_dir = os.path.join(os.getcwd(), 'uploads')
        
        for doc in pdfs:
            file_name = doc.get("name", "")
            file_path = os.path.join(upload_dir, file_name)
            
            if not os.path.exists(file_path):
                logger.warning(f"File not found: {file_path}")
                continue
            
            text = extract_text_from_pdf(file_path)
            if not text:
                logger.warning(f"No text extracted from: {file_path}")
                continue
            
            chunks = split_text_into_chunks(text)
            logger.info(f"Extracted {len(chunks)} chunks from {file_path}")
            
            all_texts.extend(chunks)
            metadatas.extend([{"class_id": class_id, "source": file_path}] * len(chunks))
        
        if all_texts:
            logger.info(f"Uploading {len(all_texts)} chunks to Neo4j...")
            Neo4jVector.from_texts(
                texts=all_texts,
                embedding=embeddings,
                url=NEO4J_URI,
                username=NEO4J_USERNAME,
                password=NEO4J_PASSWORD,
                index_name="pdf_bot",
                node_label="PdfBotChunk",
                metadatas=metadatas,
                pre_delete_collection=False,
            )
            logger.info("Upload complete.")
        else:
            logger.warning("No chunks to upload.")
        
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Error ingesting PDFs for class {class_id}: {str(e)}")
        return {"success": False, "error": str(e)}

# ========== CHAT FUNCTIONALITY ==========

def create_chat_prompt() -> ChatPromptTemplate:
    """Create the chat prompt template for the RAG system."""
    general_system_template = """ 
    Du bist ein virtueller Assistant an der Dualen Hochschule Baden-Württemberg (DHBW).
    Deine Aufgabe ist es, Studierende individuell bei ihren Fragen zu unterstützen, indem du ausschließlich auf die vom echten Professor bereitgestellten Dokumente zugreifst.
    Antworte klar, präzise und fachlich korrekt auf Deutsch (wenn der Student auf Englisch schreibt, du kannst auf Englisch antworten). 
    Wenn du Informationen aus den Dokumenten verwendest, gib bitte immer an, aus welchem Dokument und ggf. aus welchem Abschnitt oder Seite die Information stammt, damit die Studierenden diese selbst nachschlagen können.
    Falls du eine Frage nicht beantworten kannst, weil die Information nicht in den Dokumenten enthalten ist, sage ehrlich, dass du dazu keine Auskunft geben kannst.
    ----
       {summaries}
    ----
    Jede Antwort soll am Ende eine Quellenangabe enthalten, damit die Studierenden nachvollziehen können, woher die Information stammt. Please specify the exact name of the document and the page number if available.
    """
    
    general_user_template = "Frage:```{question}```"
    
    messages = [
        SystemMessagePromptTemplate.from_template(general_system_template),
        HumanMessagePromptTemplate.from_template(general_user_template),
    ]
    
    return ChatPromptTemplate.from_messages(messages)

async def chat_with_class(class_id: int, prompt: str) -> dict:
    """Chat with documents for a specific class."""
    try:
        vectorstore = get_vectorstore()
        retriever = vectorstore.as_retriever(
            search_kwargs={"filter": {"class_id": class_id}}
        )
        
        qa_prompt = create_chat_prompt()
        
        qa = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True,
            chain_type_kwargs={"prompt": qa_prompt, "document_variable_name": "summaries"},
        )
        
        result = qa.invoke({"query": prompt})
        
        return {
            "answer": result.get("result") or result.get("answer"),
            "sources": result.get("sources")        }
        
    except Exception as e:
        logger.error(f"Error in chat_with_class: {str(e)}")
        return {
            "answer": "Es tut mir leid, es ist ein Fehler aufgetreten. Bitte versuchen Sie es später erneut.",
            "sources": None
        }