from datasets import load_dataset
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import re
import os

# File paths for persistence
EMBEDDING_FILE = "rag_files/assistant_embeddings.npy"
FAISS_INDEX_FILE = "rag_files/faiss_index.index"
TEXTS_FILE = "rag_files/assistant_texts.npy"


# --- Load & preprocess datasets ---
def load_heliosbrahma():
    dataset = load_dataset("heliosbrahma/mental_health_chatbot_dataset", split="train")
    responses = []
    for row in dataset:
        text = row["text"]
        match = re.search(r"<ASSISTANT>:\s*(.+)", text, re.DOTALL)
        if match:
            responses.append(match.group(1).strip())
    return responses


def load_amod_counseling():
    dataset = load_dataset("Amod/mental_health_counseling_conversations", split="train")
    return [row["Response"].strip() for row in dataset if "Response" in row]


def load_mpingale():
    dataset = load_dataset("mpingale/mental-health-chat-dataset", split="train")
    return [
        row["answerText"].strip()
        for row in dataset
        if row.get("answerText") and isinstance(row["answerText"], str)
    ]


def load_all_responses():
    print("📥 Loading and combining datasets...")
    responses = []
    responses += load_heliosbrahma()
    responses += load_amod_counseling()
    responses += load_mpingale()
    print(f"✅ Total responses loaded: {len(responses)}")
    return responses


# --- Save/load FAISS and embeddings ---
def save_embeddings_index_texts(embeddings, index, texts):
    np.save(EMBEDDING_FILE, embeddings)
    faiss.write_index(index, FAISS_INDEX_FILE)
    np.save(TEXTS_FILE, np.array(texts))
    print("💾 Saved embeddings, index, and texts.")


def load_embeddings_index_texts():
    embeddings = np.load(EMBEDDING_FILE)
    index = faiss.read_index(FAISS_INDEX_FILE)
    texts = np.load(TEXTS_FILE, allow_pickle=True).tolist()
    print("📂 Loaded embeddings, index, and texts from disk.")
    return embeddings, index, texts


# --- RAG Retriever ---
class RAGRetriever:
    def __init__(self, texts, embeddings=None, index=None, embedding_model_name="all-MiniLM-L6-v2"):
        self.texts = texts
        self.model = SentenceTransformer(embedding_model_name)
        if embeddings is None or index is None:
            print("🔄 Creating new embeddings and FAISS index...")
            self.embeddings = self.model.encode(texts, show_progress_bar=True)
            self.index = self._build_faiss_index(self.embeddings)
            save_embeddings_index_texts(self.embeddings, self.index, self.texts)
        else:
            self.embeddings = embeddings
            self.index = index

    def _build_faiss_index(self, embeddings):
        dim = embeddings.shape[1]
        index = faiss.IndexFlatL2(dim)
        index.add(np.array(embeddings))
        return index

    def get_context(self, query, top_k=5):
        query_embedding = self.model.encode([query])
        D, I = self.index.search(np.array(query_embedding), top_k)
        return [self.texts[i] for i in I[0]]


def load_rag_retriver():
    """
    Load or create a RAG retriever.
    Returns:
        RAGRetriever: A retriever instance
    """
    # Load RAG components

    # Ensure the output directory exists
    output_dir = os.path.dirname(EMBEDDING_FILE)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"📂 Created directory: {output_dir}")

    if (
        os.path.exists(EMBEDDING_FILE)
        and os.path.exists(FAISS_INDEX_FILE)
        and os.path.exists(TEXTS_FILE)
    ):
        embeddings, index, assistant_texts = load_embeddings_index_texts()
    else:
        assistant_texts = load_all_responses()
        embeddings, index = None, None

    retriever = RAGRetriever(assistant_texts, embeddings, index)
    return retriever


def get_context_from_rag(retriever, query):
    """
    Get context from RAG retriever based on user input.
    Args:
        retriever (RAGRetriever): The retriever instance
        query (str): User input/query text
    Returns:
        str: Context retrieved from RAG
    """
    if not query:
        return None
    print("🔍 Retrieving context for query:", query)

    context_chunks = retriever.get_context(query, top_k=2)  # Reduced from 5 to 3
    if not context_chunks:
        return None

    context = "\n\n".join(context_chunks)
    return context


# --- Main execution ---
if __name__ == "__main__":
    retriever = load_rag_retriver()

    query = "What happens during a panic attack?"
    context = get_context_from_rag(retriever, query)

    print(f"\n🔍 Top relevant responses for: '{query}'")
    print(context)
