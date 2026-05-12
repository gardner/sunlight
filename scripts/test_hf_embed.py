import json
import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

model_name = "Qwen/Qwen3-Embedding-0.6B"
print(f"Loading {model_name}...")
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModel.from_pretrained(model_name)

text = "This is a test of the emergency broadcasting system."

print(f"Tokenizing...")
inputs = tokenizer(text, return_tensors="pt")

print(f"Generating embedding...")
with torch.no_grad():
    outputs = model(**inputs)

# Use mean pooling (or whatever Qwen3 recommends)
# Often Qwen3 uses the last hidden state of the first token (CLS) or mean pooling.
# For dense embeddings, let's just use mean pooling.
embeddings = outputs.last_hidden_state.mean(dim=1)
embeddings = F.normalize(embeddings, p=2, dim=1)

embed_list = embeddings[0].tolist()

print("Success. Dimensions:", len(embed_list))
print("First 5 values:", embed_list[:5])
