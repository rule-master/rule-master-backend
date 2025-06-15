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
import json
import argparse
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import (
    PointStruct,
)
from dotenv import load_dotenv
import uuid
import numpy as np

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


# def english_action_title(filename: str) -> str:
#     """Convert filename to English action title."""
#     mapping = {
#         "regla-ventas-previstas-totales.gdst": "Recommend staffing levels based on total sales forecast",
#         "regla-ventas-previstas-por-franja.gdst": "Recommend staffing levels based on time-slot sales forecast",
#         "regla-tamaño-restaurante.gdst": "Recommend staffing levels based on restaurant size",
#         "regla-media-empleados-HD.gdst": "Recommend home-delivery staffing levels based on medium order volumes",
#         "regla-larga-empleados-HD.gdst": "Recommend home-delivery staffing levels based on high order volumes",
#         "regla-extra-restaurantes.gdst": "Recommend additional restaurant staffing levels",
#         "regla-desglose-empleados-sin-autoking.gdst": "Recommend staffing breakdown without autoking",
#         "regla-desglose-empleados-con-autoking.gdst": "Recommend staffing breakdown with autoking",
#         "regla-desglose-cierre.gdst": "Recommend staffing breakdown at closing",
#         "regla-desglose-apertura.gdst": "Recommend staffing breakdown at opening",
#         "regla-corta-empleados-HD.gdst": "Recommend home-delivery staffing levels based on low order volumes",
#         "regla-cierre.gdst": "Recommend staffing levels at restaurant closing",
#         "regla-autoking.gdst": "Recommend staffing adjustments based on autoking status",
#         "init.inicializacion-salida.drl": "Initialize system output parameters",
#         "init.entrada-salida.drl": "Initialize system input-output parameters",
#     }
#     return mapping.get(filename, filename)


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

        matrix = np.vstack(vecs)  # shape (N, 1536)
        avg = np.mean(matrix, axis=0)  # shape (1536,)
        return avg.tolist()


def reindex_single_point(
    client: OpenAI, collection_name: str, file_title: str, rules_dir: str
):
    """
    Reindex a single point in the collection by file title.

    Args:
        client (OpenAI): OpenAI client instance
        collection_name (str): Name of the collection
        file_title (str): Title of the file to reindex (without extension)
        rules_dir (str): Directory containing the rule files
    """
    # Initialize Qdrant client
    qdrant_client = QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY"),
    )

    # Try both .drl and .gdst extensions
    for ext in [".drl", ".gdst"]:
        file_path = os.path.join(rules_dir, f"{file_title}{ext}")
        if os.path.exists(file_path):
            # Read the rule content
            with open(file_path, "r", encoding="utf-8") as f:
                rule_content = f.read()

            # Try to load metadata if it exists
            metadata_path = os.path.join(rules_dir, f"{file_title}_metadata.json")
            refined_prompt = rule_content
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, "r") as f:
                        metadata = json.load(f)
                        refined_prompt = metadata.get(
                            "refined_user_prompt", rule_content
                        )
                except Exception as e:
                    print(f"Warning: Could not load metadata for {file_path}: {str(e)}")

            # Create the embedding
            emb = embed_text(rule_content, client)

            # Prepare the metadata
            payload = {
                "filesystem_filename": os.path.basename(file_path),
                "refined_prompt": refined_prompt,
            }

            # Create a unique ID for the point
            point_id = str(uuid.uuid4())

            # Upsert the point
            qdrant_client.upsert(
                collection_name=collection_name,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=emb,
                        payload=payload,
                    )
                ],
            )

            print(
                f"Successfully reindexed rule {file_title} into collection {collection_name}"
            )
            return

    print(f"Warning: Could not find rule file for {file_title} in {rules_dir}")


def reindex_collection(
    client: OpenAI, collection_name: str, rule_content: str, metadata: dict
):
    """
    Index a single rule with its metadata into the collection.

    Args:
        client (OpenAI): OpenAI client instance
        collection_name (str): Name of the collection to index into
        rule_content (str): The content of the rule to index
        metadata (dict): Metadata for the rule, containing at least:
            - filesystem_filename: Name of the rule file
            - refined_user_prompt: The refined user prompt
    """
    # Initialize Qdrant client
    qdrant_client = QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY"),
    )

    # Create the embedding for the rule content
    emb = embed_text(rule_content, client)

    # Get the filesystem-friendly version
    filesystem_filename = metadata["filesystem_filename"].replace(" ", "_")

    # Prepare the metadata with the correct format
    payload = {
        "filesystem_filename": filesystem_filename,
        "refined_prompt": metadata["refined_user_prompt"],
    }

    # Create a unique ID for the point
    point_id = str(uuid.uuid4())

    # Upsert the point
    qdrant_client.upsert(
        collection_name=collection_name,
        points=[
            PointStruct(
                id=point_id,
                vector=emb,
                payload=payload,
            )
        ],
    )

    print(
        f"Successfully indexed rule {filesystem_filename} into collection {collection_name}"
    )


def index_new_rule(
    client: OpenAI, 
    collection_name: str, 
    rule_content: str, 
    file_path: str,
    refined_prompt: str
):
    """
    Index a newly created rule file into the collection.

    Args:
        client (OpenAI): OpenAI client instance
        collection_name (str): Name of the collection
        rule_content (str): The content of the rule to index
        file_path (str): Path to the rule file
        refined_prompt (str): The refined user prompt
    """
    # Initialize Qdrant client
    qdrant_client = QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY"),
    )

    # Create the embedding
    emb = embed_text(rule_content, client)

    # Get the filesystem-friendly filename
    filesystem_filename = os.path.basename(file_path)

    # Prepare the metadata
    payload = {
        "filesystem_filename": filesystem_filename,
        "refined_prompt": refined_prompt,
    }

    # Create a unique ID for the point
    point_id = str(uuid.uuid4())

    # Upsert the point
    qdrant_client.upsert(
        collection_name=collection_name,
        points=[
            PointStruct(
                id=point_id,
                vector=emb,
                payload=payload,
            )
        ],
    )

    print(
        f"Successfully indexed new rule {filesystem_filename} into collection {collection_name}"
    )
