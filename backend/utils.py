# import requests, json
# from backend.config import OLLAMA_HOST


# def ollama_embed(model: str, text: str):
#     r = requests.post(f"{OLLAMA_HOST}/api/embeddings", json={"model": model, "prompt": text})
#     r.raise_for_status()
#     return r.json()["embedding"]


# def ollama_generate(model: str, prompt: str):
#     r = requests.post(f"{OLLAMA_HOST}/api/generate", json={"model": model, "prompt": prompt, "stream": False})
#     r.raise_for_status()
#     return r.json()["response"]

from groq import Groq
from sentence_transformers import SentenceTransformer
from backend.config import GROQ_API_KEY, EMBED_MODEL, LLM_MODEL

# Initialize Groq client
groq_client = Groq(api_key=GROQ_API_KEY)

# Initialize sentence transformer for embeddings (lazy load)
_embed_model = None

def get_embed_model():
    """Lazy load the embedding model."""
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer(EMBED_MODEL)
    return _embed_model


def ollama_embed(model: str, text: str):
    """
    Generate embeddings using sentence-transformers.
    Returns a list of floats (768-dimensional vector).
    Note: model parameter is kept for backward compatibility but not used.
    """
    embed_model = get_embed_model()
    embedding = embed_model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


def ollama_generate(model: str, prompt: str):
    """
    Generate text using Groq API.
    Returns the generated text as a string.
    Note: model parameter is kept for backward compatibility but uses LLM_MODEL from config.
    """
    try:
        response = groq_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful NBA statistics assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent responses
            max_tokens=2048
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling Groq API: {e}")
        return "I'm sorry, I encountered an error processing your request."
    