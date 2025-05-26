from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from backend.rag.chains import load_embedding_model, load_llm
from langchain.chains import RetrievalQA
from langchain.vectorstores.neo4j_vector import Neo4jVector
import os

# Load RAG models once at startup (adjust as needed)
embedding_model_name = os.getenv("EMBEDDING_MODEL", "SentenceTransformer")
llm_name = os.getenv("LLM", "llama2")
ollama_base_url = os.getenv("OLLAMA_BASE_URL")
neo4j_url = os.getenv("NEO4J_URI")
neo4j_username = os.getenv("NEO4J_USERNAME")
neo4j_password = os.getenv("NEO4J_PASSWORD")

embeddings, dimension = load_embedding_model(
    embedding_model_name, config={"ollama_base_url": ollama_base_url}
)
llm = load_llm(llm_name, config={"ollama_base_url": ollama_base_url})

@app.post("/api/chat/{class_id}")
async def chat_api(class_id: int, body: dict):
    prompt = body.get("prompt")
    if not prompt:
        return JSONResponse({"error": "No prompt provided"}, status_code=400)

    # Get all documents for this class
    pdfs = db.get_pdfs_for_class(class_id)
    chunks = []
    from PyPDF2 import PdfReader
    from langchain.text_splitter import RecursiveCharacterTextSplitter

    # Extract and split text from all PDFs
    for pdf in pdfs:
        file_path = os.path.join("uploads", pdf["file_path"])
        try:
            with open(file_path, "rb") as f:
                reader = PdfReader(f)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000, chunk_overlap=200, length_function=len
                )
                chunks.extend(text_splitter.split_text(text=text))
        except Exception as e:
            continue  # Optionally log

    # Create vectorstore (optionally cache this for performance)
    vectorstore = Neo4jVector.from_texts(
        chunks,
        url=neo4j_url,
        username=neo4j_username,
        password=neo4j_password,
        embedding=embeddings,
        index_name="pdf_bot",
        node_label="PdfBotChunk",
        pre_delete_collection=False,  # Don't delete existing data!
    )

    qa = RetrievalQA.from_chain_type(
        llm=llm, chain_type="stuff", retriever=vectorstore.as_retriever()
    )

    answer = qa.run(prompt)
    # Optionally, add source info if available
    return {"answer": answer, "source": None}