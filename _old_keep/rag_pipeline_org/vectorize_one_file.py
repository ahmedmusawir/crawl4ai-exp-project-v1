"""
RAG Pipeline - Step 1: Vectorize a Single Markdown File

This script loads a pre-discovered markdown content file,
splits it into chunks, vectorizes it using OpenAI embeddings,
and stores it in a local Chroma DB.

Dynamic settings like persist_directory and collection_name are
driven by the `site_key` in `site_config.json` generated during the
crawl phase.
"""

import os
import json
from dotenv import load_dotenv
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

# Step 0: Load environment variables (for OpenAI API key)
load_dotenv()

# Step 1: Load site config
print("[STEP 1] Loading site configuration from site_config.json...")
with open("site_config.json", "r") as f:
    config = json.load(f)

site_key = config["site_key"]  # e.g., cyberizegroup-com
persist_directory = os.path.join("_vector-dbs", f"{site_key}-vdb")
collection_name = site_key.replace("-", "_") + "_collection"
print(f"[INFO] Site Key: {site_key}")
print(f"[INFO] Persist Directory: {persist_directory}")
print(f"[INFO] Collection Name: {collection_name}")

# Step 2: Load markdown document
print("[STEP 2] Loading markdown content file...")
markdown_path = "outputs/pages/cyberizegroup-com.md"  # Hardcoded for now
loader = UnstructuredMarkdownLoader(markdown_path)
documents = loader.load()
print(f"[INFO] Loaded {len(documents)} document(s) from: {markdown_path}")

# Step 3: Chunk the document
print("[STEP 3] Splitting document into chunks...")
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
chunked_docs = text_splitter.split_documents(documents)
print(f"[INFO] Created {len(chunked_docs)} chunks")

# Step 4: Embed and persist into Chroma
print("[STEP 4] Vectorizing chunks and saving to Chroma...")
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

vector_store = Chroma(
    collection_name=collection_name,
    embedding_function=embeddings,
    persist_directory=persist_directory,
)

vector_store.add_documents(chunked_docs)

print(f"[SUCCESS] Vector store saved to: {persist_directory}")
print(f"[INFO] Collection name: {collection_name}")

# Optional: Local testing block
if __name__ == "__main__":
    print("\n[TEST] Running retrieval test on local vector store...")
    retriever = vector_store.as_retriever()
    query = "What does Cyberize Group specialize in?"
    results = retriever.get_relevant_documents(query)

    print("\n[TOP RESULTS]")
    for i, doc in enumerate(results[:3]):
        print(f"Result {i+1}:")
        print(doc.page_content[:500])  # Print a snippet of each
        print("-" * 40)
