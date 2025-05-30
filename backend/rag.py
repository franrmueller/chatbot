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
            pre_delete_collection=True,
        )
        logger.info("Upload complete.")
    else:
        logger.warning("No chunks to upload.")
    return {"success": True}

async def chat_with_class(class_id: int, prompt: str):
    vectorstore = get_vectorstore()
    retriever = vectorstore.as_retriever()

    general_system_template = """ 
    Du bist Professor für den Bachelor-Studiengang Wirtschaftsinformatik - Business Engineering an der Dualen Hochschule Baden-Württemberg (DHBW).
    Deine Aufgabe ist es, Studierende individuell bei ihren Fragen zu unterstützen, indem du ausschließlich auf die vom echten Professor bereitgestellten Dokumente zugreifst.
    Antworte klar, präzise und fachlich korrekt auf Deutsch. 
    Wenn du Informationen aus den Dokumenten verwendest, gib bitte immer an, aus welchem Dokument und ggf. aus welchem Abschnitt oder Seite die Information stammt, damit die Studierenden diese selbst nachschlagen können.
    Falls du eine Frage nicht beantworten kannst, weil die Information nicht in den Dokumenten enthalten ist, sage ehrlich, dass du dazu keine Auskunft geben kannst.
    ----
       {summaries}
    ----
    Jede Antwort soll am Ende eine Quellenangabe enthalten, damit die Studierenden nachvollziehen können, woher die Information stammt.
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

# async def configure_qa_rag_chain(llm):
#     general_system_template = """ 
#     Use the following pieces of context to answer the question at the end.
#     The context contains question-answer pairs and their links from Stackoverflow.
#     You should prefer information from accepted or more upvoted answers.
#     Make sure to rely on information from the answers and not on questions to provide accuate responses.
#     When you find particular answer in the context useful, make sure to cite it in the answer using the link.
#     If you don't know the answer, just say that you don't know, don't try to make up an answer.
#     ----
#     {summaries}
#     ----
#     Each answer you generate should contain a section at the end of links to 
#     Stackoverflow questions and answers you found useful, which are described under Source value.
#     You can only use links to StackOverflow questions that are present in the context and always
#     add links to the end of the answer in the style of citations.
#     Generate concise answers with references sources section of links to 
#     relevant StackOverflow questions only at the end of the answer.
#     """
#     general_user_template = "Question:```{query}```"
#     messages = [
#         SystemMessagePromptTemplate.from_template(general_system_template),
#         HumanMessagePromptTemplate.from_template(general_user_template),
#     ]
#     qa_prompt = ChatPromptTemplate.from_messages(messages)

#     qa = RetrievalQA.from_chain_type(
#         llm=llm,
#         chain_type="stuff",
#         retriever=get_vectorstore().as_retriever(),
#         return_source_documents=True,
#         chain_type_kwargs={"prompt": qa_prompt, "document_variable_name": "summaries"},
#     )
#     result = qa.invoke({"query": prompt})
#     return {
#         "answer": result.get("result") or result.get("answer"),
#         "sources": result.get("sources")
#     }

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