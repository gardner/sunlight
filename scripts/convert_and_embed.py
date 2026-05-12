# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "torch",
#   "sentence-transformers",
#   "llama-index-core",
#   "llama-index-embeddings-huggingface",
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
import time
from pathlib import Path
from docling.document_converter import DocumentConverter
from llama_index.core import Document, VectorStoreIndex, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import torch

def main():
    data_dir = Path("fyi/data/request")
    md_out_dir = Path("fyi/markdown")
    md_out_dir.mkdir(parents=True, exist_ok=True)
    
    print("Initializing Docling DocumentConverter...")
    converter = DocumentConverter()

    # Grab 5 PDFs to test the pipeline
    pdf_files = list(data_dir.rglob("*.pdf"))[:5]
    print(f"Found {len(pdf_files)} PDF files to process.")

    documents = []

    for file_path in pdf_files:
        # Create a clean filename for the markdown output
        safe_name = file_path.name.replace(" ", "_").replace("%20", "_")
        md_file_path = md_out_dir / f"{safe_name}.md"
        
        # 1. Convert PDF to Markdown
        print(f"\n--- Converting to Markdown: {file_path.name} ---")
        start = time.time()
        try:
            result = converter.convert(str(file_path))
            md_text = result.document.export_to_markdown()
            end = time.time()
            print(f"Successfully converted to markdown in {end - start:.2f}s.")
            
            # Save markdown to disk
            with open(md_file_path, "w", encoding="utf-8") as f:
                f.write(md_text)
            print(f"Saved markdown to {md_file_path}")
            
            # Add to documents list
            doc = Document(
                text=md_text,
                metadata={
                    "source_file": str(file_path),
                    "file_name": file_path.name
                }
            )
            documents.append(doc)
            
        except Exception as e:
            print(f"Error reading {file_path.name}: {e}")

    if not documents:
        print("No documents to index.")
        return

    # 2. Calculate Embeddings
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\nUsing device: {device}")
    
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

    print(f"\nGenerating embeddings & VectorStoreIndex for {len(documents)} documents...")
    index = VectorStoreIndex.from_documents(documents, show_progress=True)
    
    persist_dir = "./storage/fyi_markdown_index"
    print(f"Persisting markdown-based index to {persist_dir}...")
    index.storage_context.persist(persist_dir=persist_dir)
    print("Done! PDFs successfully converted to markdown and embedded.")

if __name__ == "__main__":
    main()
