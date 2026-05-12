# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "torch",
#   "sentence-transformers",
#   "llama-index-core",
#   "llama-index-embeddings-huggingface",
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
import json
from pathlib import Path
from llama_index.core import Document, VectorStoreIndex, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import torch

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

    data_dir = "fyi/data"
    documents = []
    
    print(f"Reading JSON files from {data_dir}...")
    json_files = list(Path(data_dir).glob("*.json"))
    print(f"Found {len(json_files)} JSON files.")
    
    for file_path in json_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            # Create a simple text representation
            text = f"Title: {data.get('title', '')}\n"
            text += f"Public Body: {data.get('public_body', {}).get('name', '')}\n"
            text += f"Status: {data.get('display_status', '')}\n"
            text += f"Tags: {', '.join(data.get('tags', []))}\n"
            
            doc = Document(
                text=text,
                metadata={
                    "fyi_id": data.get("id"),
                    "title": data.get("title"),
                    "public_body": data.get("public_body", {}).get("name")
                }
            )
            documents.append(doc)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    if not documents:
        print("No documents to index.")
        return

    print(f"Loaded {len(documents)} documents. Creating VectorStoreIndex...")
    index = VectorStoreIndex.from_documents(documents, show_progress=True)
    
    persist_dir = "./storage/fyi_index"
    print(f"Persisting index to {persist_dir}...")
    index.storage_context.persist(persist_dir=persist_dir)
    print("Done!")

if __name__ == "__main__":
    main()