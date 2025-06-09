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
import argparse
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, PayloadSchemaType
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
VECTOR_SIZE = 3072  # Dimension of the chosen embedding model


def parse_args():
    parser = argparse.ArgumentParser(description="Setup RAG for Drools Rules")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without making changes",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Apply the changes (delete and reindex)"
    )
    return parser.parse_args()


def english_action_title(filename: str) -> str:
    """Convert filename to English action title."""
    mapping = {
        "regla-ventas-previstas-totales.gdst": "Recommend staffing levels based on total sales forecast",
        "regla-ventas-previstas-por-franja.gdst": "Recommend staffing levels based on time-slot sales forecast",
        "regla-tamaño-restaurante.gdst": "Recommend staffing levels based on restaurant size",
        "regla-media-empleados-HD.gdst": "Recommend home-delivery staffing levels based on medium order volumes",
        "regla-larga-empleados-HD.gdst": "Recommend home-delivery staffing levels based on high order volumes",
        "regla-extra-restaurantes.gdst": "Recommend additional restaurant staffing levels",
        "regla-desglose-empleados-sin-autoking.gdst": "Recommend staffing breakdown without autoking",
        "regla-desglose-empleados-con-autoking.gdst": "Recommend staffing breakdown with autoking",
        "regla-desglose-cierre.gdst": "Recommend staffing breakdown at closing",
        "regla-desglose-apertura.gdst": "Recommend staffing breakdown at opening",
        "regla-corta-empleados-HD.gdst": "Recommend home-delivery staffing levels based on low order volumes",
        "regla-cierre.gdst": "Recommend staffing levels at restaurant closing",
        "regla-autoking.gdst": "Recommend staffing adjustments based on autoking status",
        "init.inicializacion-salida.drl": "Initialize system output parameters",
        "init.entrada-salida.drl": "Initialize system input-output parameters",
    }
    return mapping.get(filename, filename)


def embed_text(text: str, client: OpenAI = None) -> list:
    """
    Get embedding for text using OpenAI's embedding model.

    Args:
        text (str): Text to get embedding for
        client (OpenAI, optional): OpenAI client instance. If not provided, uses global oai client.

    Returns:
        list: Embedding vector
    """
    try:
        # Use provided client or fall back to global oai client
        client_to_use = client or oai
        res = client_to_use.embeddings.create(input=text, model=EMBEDDING_MODEL)
        return res.data[0].embedding
    except Exception:
        print("Falling back to chunked embedding…")
        max_chars = 8192 * 4
        chunks = [text[i : i + max_chars] for i in range(0, len(text), max_chars)]
        vecs = []
        for chunk in chunks:
            r = client_to_use.embeddings.create(input=chunk, model=EMBEDDING_MODEL)
            vecs.append(r.data[0].embedding)  # ← must be append, never extend!
        # now average N × 1536 → one 1536 vector
        import numpy as np

        matrix = np.vstack(vecs)  # shape (N, 1536)
        avg = np.mean(matrix, axis=0)  # shape (1536,)
        return avg.tolist()


def prepare_points(rules_dir, java_dir, client: OpenAI):
    """
    Prepare points for indexing without actually indexing them.

    Args:
        rules_dir (str): Directory containing rule files
        java_dir (str): Directory containing Java files
        client (OpenAI): OpenAI client instance

    Returns:
        list: List of points ready for indexing
    """
    points = []

    # 1) Drools rule examples
    for path in glob.glob(os.path.join(rules_dir, "*.drl")) + glob.glob(
        os.path.join(rules_dir, "*.gdst")
    ):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        print("Using embedding model:", EMBEDDING_MODEL)
        print("File length (chars):", len(content))
        emb = embed_text(content, client)
        print(f"→ Got embedding of length {len(emb)} for {os.path.basename(path)}")
        fmt = os.path.splitext(path)[1].lstrip(".")
        tc = "EmployeeRecommendation"
        title = english_action_title(os.path.basename(path))
        rule_type = "simple" if fmt == "drl" else "complex"
        meta = {
            "source": os.path.basename(path),
            "format": fmt,
            "type": "rule_example",
            "target_class": tc,
            "title": title,
            "rule_type": rule_type,
        }
        drools_point_id = str(uuid.uuid4())
        points.append({"id": drools_point_id, "vector": emb, "payload": meta})

    # 2) Java classes for target APIs
    for path in glob.glob(os.path.join(java_dir, "*.java")):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        emb = embed_text(content, client)
        classname = os.path.splitext(os.path.basename(path))[0]
        title = classname
        meta = {
            "source": os.path.basename(path),
            "format": "java",
            "type": "java_class",
            "target_class": classname,
            "title": title,
            "rule_type": "schema",
        }
        java_point_id = str(uuid.uuid4())
        points.append({"id": java_point_id, "vector": emb, "payload": meta})

    return points


def main():
    args = parse_args()

    if not args.dry_run and not args.apply:
        print("Please specify either --dry-run or --apply")
        return

    # Load environment variables
    load_dotenv()
    openai_key = os.getenv("OPENAI_API_KEY")
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_key = os.getenv("QDRANT_API_KEY")
    RULES_DIR = os.getenv("RULES_DIR")
    JAVA_DIR = os.getenv("JAVA_DIR")

    if not all([openai_key, qdrant_url, qdrant_key, RULES_DIR, JAVA_DIR]):
        raise RuntimeError(
            "Please set OPENAI_API_KEY, QDRANT_URL, QDRANT_API_KEY, RULES_DIR, and JAVA_DIR environment variables"
        )

    # Initialize clients
    oai = OpenAI(api_key=openai_key)
    qdrant = QdrantClient(url=qdrant_url, prefer_grpc=False, api_key=qdrant_key)

    # Prepare points
    print("Preparing points for indexing...")
    points = prepare_points(RULES_DIR, JAVA_DIR, oai)
    print(f"Prepared {len(points)} points for indexing")

    if args.dry_run:
        print("\n=== DRY RUN MODE ===")
        print("The following actions would be taken:")
        print(f"1. Delete collection '{COLLECTION_NAME}' if it exists")
        print(f"2. Create new collection '{COLLECTION_NAME}'")
        print(
            "3. Create payload indexes for: source, format, type, target_class, title, rule_type"
        )
        print(f"4. Index {len(points)} points in batches of 5")
        print("\nFiles to be indexed:")
        for point in points:
            print(f"- {point['payload']['source']} ({point['payload']['type']})")
        return

    if args.apply:
        print("\n=== APPLYING CHANGES ===")
        # Delete existing collection if it exists
        if qdrant.collection_exists(collection_name=COLLECTION_NAME):
            print(f"Deleting existing collection '{COLLECTION_NAME}'...")
            qdrant.delete_collection(collection_name=COLLECTION_NAME)
            print(f"Collection '{COLLECTION_NAME}' deleted")

        # Create new collection
        print(f"Creating new collection '{COLLECTION_NAME}'...")
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={"size": VECTOR_SIZE, "distance": "Cosine"},
        )
        print(f"Collection '{COLLECTION_NAME}' created successfully")

        # Create payload indexes
        print("Creating payload indexes...")
        for field in ["source", "format", "type", "target_class", "title", "rule_type"]:
            qdrant.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
            print(f"Indexed '{field}'")
        print("All payload indexes created successfully")

        # Upsert points
        BATCH_SIZE = 5
        for i in range(0, len(points), BATCH_SIZE):
            batch = points[i : i + BATCH_SIZE]
            print(f"Upserting points {i}–{i+len(batch)-1}...")
            qdrant.upsert(collection_name=COLLECTION_NAME, points=batch)
        print("Upsert complete.")

        # Verify with a sample query
        print("\nVerifying index with sample query...")
        sample_payload = {
            "intent": "add",
            "target_class": "EmployeeRecommendation",
            "input_class": "RestaurantData",
            "rule_name": "TestRule",
            "salience": 1,
            "conditions": [
                {"condition": "sales > 5000", "actions": ["set employees to 10"]},
                {"condition": "sales > 8000", "actions": ["set employees to 15"]},
                {"condition": "sales > 12000", "actions": ["set employees to 20"]},
            ],
        }
        query_text = json.dumps(sample_payload)
        print(f"Embedding sample JSON payload for retrieval...")
        query_vec = embed_text(query_text, oai)

        metadata_filter = Filter(
            must=[
                FieldCondition(key="rule_type", match=MatchValue(value="complex")),
                FieldCondition(key="format", match=MatchValue(value="gdst")),
            ]
        )

        hits = qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vec,
            limit=5,
            query_filter=metadata_filter,
        )
        print("\nTop 5 RAG hits:")
        for hit in hits:
            p = hit.payload
            print(
                f"- {p['type']} '{p['source']}' (tc={p['target_class']}, score={hit.score:.3f})"
            )


if __name__ == "__main__":
    main()
