"""
RAG Pipeline - Multi-file Ingestion & Interactive Retrieval Test

This script loads all markdown content files in /outputs/pages/,
splits them into chunks, vectorizes using OpenAI embeddings,
and stores them in a local Chroma DB. After ingestion, you can
chat with the vector store and test retrieval results in a loop.

Dynamic settings like persist_directory and collection_name are
driven by the `site_key` in `site_config.json` generated during the
crawl phase.
"""

import os
import glob
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

# Step 2: Load all markdown documents
print("[STEP 2] Loading markdown content files from outputs/pages/...\n")
markdown_files = sorted(glob.glob("outputs/pages/*.md"))
if not markdown_files:
    print("[ERROR] No markdown files found in outputs/pages/")
    exit(1)

all_documents = []
for path in markdown_files:
    print(f"[INFO] Loading: {path}")
    loader = UnstructuredMarkdownLoader(path)
    docs = loader.load()
    print(f"        -> Loaded {len(docs)} document(s)")
    all_documents.extend(docs)
print(f"[INFO] Total loaded documents: {len(all_documents)}")

# Step 3: Chunk the documents
print("[STEP 3] Splitting documents into chunks...")
text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200)
chunked_docs = text_splitter.split_documents(all_documents)
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

# Optional: Interactive retrieval test block
if __name__ == "__main__":
    print("\n[TEST] Entering interactive retrieval chat. Type 'exit' to quit.")
    # retriever = vector_store.as_retriever()
    retriever = vector_store.as_retriever(
    search_type="mmr",        # or "similarity"
    search_kwargs={"k": 5}    # get 5 results instead of 3
)

    while True:
        query = input("\n[Your Query]> ").strip()
        if query.lower() in ("exit", "quit", "q"): 
            print("Exiting interactive chat. Bye, boss!")
            break
        results = retriever.get_relevant_documents(query)
        print("\n[TOP RESULTS]")
        for i, doc in enumerate(results[:5]):
            print(f"Result {i+1}:")
            print(doc.page_content[:500])  # Print a snippet of each
            print("-" * 40)
