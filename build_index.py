import os
import shutil
import logging
from typing import List, Tuple, Dict, Any
from dotenv import load_dotenv

from pypdf import PdfReader
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

DATA_DIR = os.getenv("DATA_DIR", "data")
DB_DIR = os.getenv("CHROMA_DB_PATH", "chroma_db")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))


def load_pdf_texts() -> Tuple[List[str], List[Dict[str, Any]]]:
    """Load text from all PDFs in the data/ folder."""
    texts: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    if not os.path.exists(DATA_DIR):
        logger.error("Data folder '%s' not found.", DATA_DIR)
        return texts, metadatas

    if not os.path.isdir(DATA_DIR):
        logger.error("'%s' is not a directory.", DATA_DIR)
        return texts, metadatas

    pdf_files = [f for f in os.listdir(DATA_DIR) if f.lower().endswith(".pdf")]
    
    if not pdf_files:
        logger.warning("No PDF files found in '%s'.", DATA_DIR)
        return texts, metadatas

    for filename in pdf_files:
        path = os.path.join(DATA_DIR, filename)
        logger.info("Loading: %s", path)
        
        try:
            reader = PdfReader(path)
        except Exception as e:
            logger.error("Failed to read PDF '%s': %s", path, e)
            continue

        for page_num, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text() or ""
            except Exception as e:
                logger.warning("Failed to extract text from page %d of '%s': %s", 
                              page_num + 1, filename, e)
                page_text = ""

            page_text = page_text.strip()
            if not page_text:
                continue

            texts.append(page_text)
            metadatas.append(
                {
                    "source": filename,
                    "page": page_num + 1,
                }
            )

    return texts, metadatas


def split_texts(texts: List[str], metadatas: List[Dict[str, Any]], 
                chunk_size: int = 1000, chunk_overlap: int = 200) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Split texts into chunks using LangChain's RecursiveCharacterTextSplitter."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    
    all_chunks: List[str] = []
    all_chunk_metadatas: List[Dict[str, Any]] = []
    
    for text, metadata in zip(texts, metadatas):
        chunks = text_splitter.split_text(text)
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_chunk_metadatas.append(
                {
                    "source": metadata["source"],
                    "page": metadata["page"],
                    "chunk": i,
                }
            )
    
    return all_chunks, all_chunk_metadatas


def main() -> None:
    """Main function to build the Chroma vector database from PDFs."""
    logger.info("Loading texts from PDFs in '%s'...", DATA_DIR)
    raw_texts, raw_metadatas = load_pdf_texts()

    if not raw_texts:
        logger.error("No PDF text found in '%s'. Add some PDFs and try again.", DATA_DIR)
        return

    logger.info("Loaded %d pages of text", len(raw_texts))

    logger.info("Splitting texts into chunks (size=%d, overlap=%d)...", 
                CHUNK_SIZE, CHUNK_OVERLAP)
    all_chunks, all_metadatas = split_texts(raw_texts, raw_metadatas, 
                                            CHUNK_SIZE, CHUNK_OVERLAP)

    logger.info("Created %d chunks", len(all_chunks))

    logger.info("Creating embeddings with Gemini...")
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
    except Exception as e:
        logger.error("Failed to initialize embeddings: %s", e)
        return

    logger.info("Building Chroma DB in '%s'...", DB_DIR)
    if os.path.exists(DB_DIR):
        logger.info("Existing DB found, deleting it first...")
        try:
            shutil.rmtree(DB_DIR)
        except Exception as e:
            logger.error("Failed to delete existing DB: %s", e)
            return

    try:
        Chroma.from_texts(
            texts=all_chunks,
            embedding=embeddings,
            metadatas=all_metadatas,
            persist_directory=DB_DIR,
        )
        logger.info("✅ Done! Chroma DB built successfully.")
    except Exception as e:
        logger.error("Failed to build Chroma DB: %s", e)
        raise


if __name__ == "__main__":
    main()

