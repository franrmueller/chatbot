import os
import logging
import PyPDF2
from typing import List, Any
from dotenv import load_dotenv
from neo4j import GraphDatabase
from backend import db
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA, RetrievalQAWithSourcesChain
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain.vectorstores.neo4j_vector import Neo4jVector

# ========== ENV & LOGGER ==========
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence_transformer")
LLM = os.getenv("LLM", "llama2")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# ========== UTILS ==========

def extract_title_and_question(input_string):
    lines = input_string.strip().split("\n")
    title = ""
    question = ""
    is_question = False
    for line in lines:
        if line.startswith("Title:"):
            title = line.split("Title: ", 1)[1].strip()
        elif line.startswith("Question:"):
            question = line.split("Question: ", 1)[1].strip()
            is_question = True
        elif is_question:
            question += "\n" + line.strip()
    return title, question

def create_vector_index(driver, dimension: int) -> None:
    index_query = "CALL db.index.vector.createNodeIndex('stackoverflow', 'Question', 'embedding', $dimension, 'cosine')"
    try:
        driver.query(index_query, {"dimension": dimension})
    except:
        pass
    index_query = "CALL db.index.vector.createNodeIndex('top_answers', 'Answer', 'embedding', $dimension, 'cosine')"
    try:
        driver.query(index_query, {"dimension": dimension})
    except:
        pass

def create_constraints(driver):
    driver.query(
        "CREATE CONSTRAINT question_id IF NOT EXISTS FOR (q:Question) REQUIRE (q.id) IS UNIQUE"
    )
    driver.query(
        "CREATE CONSTRAINT answer_id IF NOT EXISTS FOR (a:Answer) REQUIRE (a.id) IS UNIQUE"
    )
    driver.query(
        "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE (u.id) IS UNIQUE"
    )
    driver.query(
        "CREATE CONSTRAINT tag_name IF NOT EXISTS FOR (t:Tag) REQUIRE (t.name) IS UNIQUE"
    )

# ========== EMBEDDINGS & LLM LOADING ==========

def load_embedding_model():
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

embeddings, _ = load_embedding_model()

def load_llm():
    from langchain.chat_models import ChatOpenAI, ChatOllama, BedrockChat
    if LLM.lower().startswith("gpt"):
        return ChatOpenAI(model=LLM)
    elif LLM.lower() == "ollama":
        return ChatOllama(base_url=OLLAMA_BASE_URL)
    elif LLM.lower() == "bedrock":
        return BedrockChat()
    else:
        return ChatOllama(base_url=OLLAMA_BASE_URL)  # fallback

llm = load_llm()

# ========== VECTORSTORE HELPERS ==========

def get_vectorstore():
    logger.info(f"Connecting to Neo4j at {NEO4J_URI} with user {NEO4J_USERNAME}")
    return Neo4jVector(
        url=NEO4J_URI,
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD,
        embedding=embeddings,
        index_name="pdf_bot",
        node_label="PdfBotChunk",
    )

# ========== PDF INGESTION ==========

async def ingest_pdf(pdf_id: int):
    doc = db.get_document_by_id(pdf_id)
    if not doc:
        logger.warning(f"No document found with id: {pdf_id}")
        return {"success": False, "error": "Document not found"}
    upload_dir = os.path.join(os.getcwd(), 'uploads')
    file_name = doc.get("name", "")
    file_path = os.path.join(upload_dir, file_name)
    logger.info(f"Processing PDF: {file_path}")
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return {"success": False, "error": "File not found"}
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text
    if not text:
        logger.warning(f"No text extracted from: {file_path}")
        return {"success": False, "error": "No text extracted"}
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_text(text)
    logger.info(f"Extracted {len(chunks)} chunks from {file_path}")
    metadatas = [{"class_id": doc.get("class_id"), "source": file_path}] * len(chunks)
    if chunks:
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
    else:
        logger.warning("No chunks to upload.")
        return {"success": False, "error": "No chunks to upload"}

# Optionally, keep the old ingest_pdfs for batch/class ingestion if needed.

async def ingest_pdfs(class_id: int):
    pdfs = db.get_pdfs_for_class(class_id)
    all_texts = []
    metadatas = []
    upload_dir = os.path.join(os.getcwd(), 'uploads')
    for doc in pdfs:
        file_name = doc.get("name", "")
        file_path = os.path.join(upload_dir, file_name)
        logger.info(f"Processing PDF: {file_path}")
        if not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            continue
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text
        if not text:
            logger.warning(f"No text extracted from: {file_path}")
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = splitter.split_text(text)
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

async def chat_with_class(class_id: int, prompt: str):
    vectorstore = get_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"filter": {"class_id": class_id}})

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
    qa_prompt = ChatPromptTemplate.from_messages(messages)

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
        "sources": result.get("sources")
    }

def delete_vectors_for_pdf(pdf_id: int):
    """Delete all vectors/embeddings for a specific PDF from Neo4j"""
    try:
        doc = db.get_document_by_id(pdf_id)
        if not doc:
            logger.warning(f"No document found with id: {pdf_id}")
            return False
        
        file_name = doc.get("name", "")
        file_path = os.path.join(os.getcwd(), 'uploads', file_name)
        
        # Connect to Neo4j and delete all nodes with this source
        vectorstore = get_vectorstore()
        driver = vectorstore._driver
        
        with driver.session() as session:
            result = session.run(
                """
                MATCH (n:PdfBotChunk {source: $source})
                DETACH DELETE n
                """,
                source=file_path
            )
            
            # Get the count of deleted nodes
            summary = result.consume()
            deleted_count = summary.counters.nodes_deleted
            
            logger.info(f"Deleted {deleted_count} vector nodes for PDF: {file_path}")
            
        return True
        
    except Exception as e:
        logger.error(f"Error deleting vectors for PDF {pdf_id}: {str(e)}")
        return False

# ========== GENERATE TICKET ==========

def generate_ticket(neo4j_graph, llm_chain, input_question):
    records = neo4j_graph.query(
        "MATCH (q:Question) RETURN q.title AS title, q.body AS body ORDER BY q.score DESC LIMIT 3"
    )
    questions = []
    for i, question in enumerate(records, start=1):
        questions.append((question["title"], question["body"]))
    questions_prompt = ""
    for i, question in enumerate(questions, start=1):
        questions_prompt += f"{i}. \n{question[0]}\n----\n\n"
        questions_prompt += f"{question[1][:150]}\n\n"
        questions_prompt += "----\n\n"

    gen_system_template = f"""
    You're an expert in formulating high quality questions. 
    Formulate a question in the same style and tone as the following example questions.
    {questions_prompt}
    ---

    Don't make anything up, only use information in the following question.
    Return a title for the question, and the question post itself.

    Return format template:
    ---
    Title: This is a new title
    Question: This is a new question
    ---
    """
    system_prompt = SystemMessagePromptTemplate.from_template(
        gen_system_template, template_format="jinja2"
    )
    chat_prompt = ChatPromptTemplate.from_messages(
        [
            system_prompt,
            SystemMessagePromptTemplate.from_template(
                """
                Respond in the following template format or you will be unplugged.
                ---
                Title: New title
                Question: New question
                ---
                """
            ),
            HumanMessagePromptTemplate.from_template("{question}"),
        ]
    )
    llm_response = llm_chain(
        f"Here's the question to rewrite in the expected format: ```{input_question}```",
        [],
        chat_prompt,
    )
    new_title, new_question = extract_title_and_question(llm_response["answer"])
    return (new_title, new_question)