# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "llama-index-core",
# ]
# ///

import json
from pathlib import Path
from llama_index.core import StorageContext, load_index_from_storage

def main():
    persist_dir = "./storage/fyi_pdf_index"
    if not Path(persist_dir).exists():
        print(f"Error: Storage directory {persist_dir} not found.")
        return

    print(f"Loading local LlamaIndex from {persist_dir}...")
    storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
    
    # Extract the vector store
    vector_store = storage_context.vector_store
    
    # We can access the raw dict of embeddings and nodes if we load the json manually,
    # or use the vector store's internal data.
    # LlamaIndex's default SimpleVectorStore stores data in `vector_store.json`.
    vector_json_path = Path(persist_dir) / "default__vector_store.json"
    
    if not vector_json_path.exists():
        print("Could not find default__vector_store.json")
        return
        
    print(f"Reading vectors from {vector_json_path}...")
    with open(vector_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    embedding_dict = data.get("embedding_dict", {})
    text_id_to_ref_doc_id = data.get("text_id_to_ref_doc_id", {})
    
    # We also need the metadata from the docstore
    docstore_path = Path(persist_dir) / "docstore.json"
    with open(docstore_path, 'r', encoding='utf-8') as f:
        doc_data = json.load(f)
    
    doc_info = doc_data.get("docstore/data", {})

    out_file = "fyi_vectors.ndjson"
    print(f"Exporting to Cloudflare Vectorize NDJSON format: {out_file}")
    
    count = 0
    with open(out_file, 'w', encoding='utf-8') as f:
        for node_id, embedding in embedding_dict.items():
            # Find the node's metadata
            node = doc_info.get(node_id, {})
            metadata = node.get("__data__", {}).get("metadata", {})
            text = node.get("__data__", {}).get("text", "")
            
            # Vectorize metadata must be simple strings, numbers, or booleans.
            # We'll attach the raw text if it's not too long, or at least the fyi_id/title.
            clean_metadata = {
                "text": text[:1000] # Vectorize metadata has a size limit
            }
            for k, v in metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    clean_metadata[k] = v
                else:
                    clean_metadata[k] = str(v)
            
            # Format for Cloudflare Vectorize
            vectorize_row = {
                "id": node_id,
                "values": embedding,
                "metadata": clean_metadata
            }
            
            f.write(json.dumps(vectorize_row) + "\n")
            count += 1
            
    print(f"Successfully exported {count} vectors to {out_file}!")
    print("\nTo upload to Cloudflare Vectorize:")
    print("1. Ensure your CLOUDFLARE_API_TOKEN has 'Vectorize: Edit' permissions")
    print("2. Create the index: wrangler vectorize create fyi_index --dimensions=1024 --metric=cosine")
    print(f"3. Upload the data: wrangler vectorize insert fyi_index --file={out_file}")

if __name__ == "__main__":
    main()
