from sentence_transformers import SentenceTransformer

model_name = "Qwen/Qwen3-Embedding-0.6B"
print(f"Loading {model_name}...")
model = SentenceTransformer(model_name)

text = "This is a test of the emergency broadcasting system."
print("Generating embedding...")
embeddings = model.encode([text])

embed_list = embeddings[0].tolist()
print("Success. Dimensions:", len(embed_list))
print("First 5 values:", embed_list[:5])
