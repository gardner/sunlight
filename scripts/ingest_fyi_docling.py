# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "torch",
#   "sentence-transformers",
#   "llama-index-core",
#   "llama-index-embeddings-huggingface",
#   "llama-index-readers-docling",
#   "docling",
# ]
#
# [tool.uv]
# index-strategy = "unsafe-best-match"
#
# [[tool.uv.index]]
# name = "pytorch-cu130"
# url = "https://download.pytorch.org/whl/cu130"
# explicit = true
#
# [tool.uv.sources]
# torch = { index = "pytorch-cu130" }
# ///

import os
from pathlib import Path
from llama_index.core import VectorStoreIndex, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.readers.docling import DoclingReader
import torch
import time

def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    
    if device == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True

    print("Setting up Qwen embedding model...")
    embed_model = HuggingFaceEmbedding(
        model_name="Qwen/Qwen3-Embedding-0.6B",
        device=device,
        model_kwargs={"torch_dtype": torch.float16}
    )
    Settings.embed_model = embed_model
    Settings.llm = None  # We only want to embed and index right now

    print("Initializing Docling PDF Reader...")
    reader = DoclingReader()
    
    data_dir = "/mnt/dgx-ssd/src/sunlight_nz/fyi/data/request"
    print(f"Finding PDF files in {data_dir}...")
    
    # Grab just 3 PDFs to test the pipeline (Docling is powerful but OCR/Layout parsing takes time)
    pdf_files = list(Path(data_dir).rglob("*.pdf"))[:3]
    print(f"Found {len(pdf_files)} PDF files to process for this test.")

    all_docs = []
    
    for file_path in pdf_files:
        print(f"\n--- Parsing with Docling: {file_path.name} ---")
        start = time.time()
        try:
            # Docling handles OCR, layout analysis, tables, etc. seamlessly
            docs = reader.load_data(file_path=str(file_path))
            end = time.time()
            print(f"Successfully extracted {len(docs)} document chunks in {end - start:.2f}s.")
            all_docs.extend(docs)
        except Exception as e:
            print(f"Error reading {file_path.name}: {e}")

    if not all_docs:
        print("No documents to index.")
        return

    print(f"\nLoaded {len(all_docs)} total chunks. Generating embeddings & VectorStoreIndex...")
    index = VectorStoreIndex.from_documents(all_docs, show_progress=True)
    
    persist_dir = "./storage/fyi_pdf_index"
    print(f"Persisting PDF index to {persist_dir}...")
    index.storage_context.persist(persist_dir=persist_dir)
    print("Done! PDFs successfully ingested into LlamaIndex via Docling.")

if __name__ == "__main__":
    main()
