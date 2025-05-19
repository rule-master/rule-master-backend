# RAG Setup for Drools Rule Examples in Qdrant Cloud
# ---------------------------------------------------
# This script:
# 1. Connects to Qdrant Cloud using API key & endpoint.
# 2. Creates a collection for rule examples if it doesn't exist.
# 3. Reads .drl and .gdst files from the `examples/` directory.
# 4. Embeds each file's text with OpenAI embeddings.
# 5. Upserts embeddings + metadata into Qdrant.
# 6. Verifies the index by running a sample similarity query.

import os
import glob
import json
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from dotenv import load_dotenv
import uuid

# --------------- Configuration ---------------
# Environment variables:
#   OPENAI_API_KEY   - your OpenAI API key
#   QDRANT_URL       - your Qdrant Cloud REST endpoint (e.g. https://<..>.us-qdrant.cloud)
#   QDRANT_API_KEY   - your Qdrant Cloud API key
# Constants:
COLLECTION_NAME = "drools-rule-examples"
EMBEDDING_MODEL = "text-embedding-3-large"  # OpenAI embedding model
VECTOR_SIZE = 3072                            # Dimension of the chosen embedding model

# --------------- Initialization ---------------
# Load environment variables
load_dotenv()
openai_key = os.getenv("OPENAI_API_KEY")
qdrant_url = os.getenv("QDRANT_URL")
qdrant_key = os.getenv("QDRANT_API_KEY")
RULES_DIR = os.getenv("RULES_DIR")
JAVA_DIR = os.getenv("JAVA_DIR")

if not openai_key or not qdrant_url or not qdrant_key:
    raise RuntimeError(
        "Please set OPENAI_API_KEY, QDRANT_URL, and QDRANT_API_KEY environment variables"
    )

# --------------- Clients ---------------
oai = OpenAI(api_key=openai_key)
qdrant = QdrantClient(url=qdrant_url, prefer_grpc=False, api_key=qdrant_key)


def embed_text(text: str) -> list:
    try:
        res = oai.embeddings.create(input=text, model=EMBEDDING_MODEL)
        return res.data[0].embedding
    except Exception:
        print("Falling back to chunked embedding…")
        max_chars = 8192 * 4
        chunks = [text[i:i+max_chars] for i in range(0, len(text), max_chars)]
        vecs = []
        for chunk in chunks:
            r = oai.embeddings.create(input=chunk, model=EMBEDDING_MODEL)
            vecs.append(r.data[0].embedding)    # ← must be append, never extend!
        # now average N × 1536 → one 1536 vector
        import numpy as np
        matrix = np.vstack(vecs)              # shape (N, 1536)
        avg = np.mean(matrix, axis=0)         # shape (1536,)
        return avg.tolist()


# --------------- Verification Query ---------------
sample_payload = {
    "intent": "add",
    "target_class": "EmployeeRecommendation",
    "input_class": "RestaurantData",
    "rule_name": "TestRule",
    "salience": 1,
    "conditions": [{"condition": "expected sales > 5000", "actions": ["set employees to 10"]},
                   {"condition": "expected sales > 8000", "actions": ["set employees to 15"]},
                   {"condition": "expected sales > 12000", "actions": ["set employees to 20"]}]
}
query_text = json.dumps(sample_payload)
print(f"Embedding sample JSON payload for retrieval...")
query_vec = embed_text(query_text)

# Build a boolean “must” filter on your metadata fields
metadata_filter = Filter(
    must=[
        FieldCondition(
            key="rule_type",
            match=MatchValue(value="complex")
        ),
        FieldCondition(
            key="format",
            match=MatchValue(value="gdst")
        )
    ]
)

# Retrieve top K
hits = qdrant.search(
    collection_name=COLLECTION_NAME,
    query_vector=query_vec,
    limit=5,
    query_filter=metadata_filter
)
print("Top 5 RAG hits:")
for hit in hits:
    p = hit.payload
    print(f"- {p['type']} '{p['source']}' (tc={p['target_class']}, score={hit.score:.3f})")