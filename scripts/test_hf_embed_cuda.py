# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "torch",
#   "sentence-transformers",
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

import torch
from sentence_transformers import SentenceTransformer
import time

def test():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    
    model_name = "Qwen/Qwen3-Embedding-0.6B"
    print(f"Loading {model_name} on {device}...")
    
    # Enable tf32 for Ampere+ GPUs (like A100/H100) for faster processing
    torch.backends.cuda.matmul.allow_tf32 = True
    
    model = SentenceTransformer(model_name, model_kwargs={"torch_dtype": torch.float16}, device=device)
    
    text = "This is a test of the emergency broadcasting system."
    print("Generating embedding...")
    
    # Warmup
    model.encode([text])
    
    start = time.time()
    embeddings = model.encode([text])
    end = time.time()
    
    embed_list = embeddings[0].tolist()
    print("Success. Dimensions:", len(embed_list))
    print(f"First 5 values: {embed_list[:5]}")
    print(f"Inference time: {(end - start) * 1000:.2f} ms")

if __name__ == "__main__":
    test()
