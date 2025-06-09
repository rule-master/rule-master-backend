"""
Search tool for finding similar Drools rules based on user input.

This module provides functionality to search through rule files and find the most
similar ones using Qdrant vector search with OpenAI embeddings.
"""

import os
import json
import socket
import time
import uuid
from typing import List, Dict, Tuple
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models
from pathlib import Path
from logger_utils import logger, log_operation, log_decorator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Qdrant configuration from environment
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = (
    "drools-rule-examples"  # Use the same collection name as other parts of the app
)

# Constants
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
OPERATION_TIMEOUT = 30  # seconds


def check_qdrant_connection(url: str = None) -> bool:
    """
    Check if Qdrant server is accessible.

    Args:
        url (str): Qdrant server URL

    Returns:
        bool: True if server is accessible, False otherwise
    """
    try:
        if not url:
            url = QDRANT_URL

        if not url:
            logger.error("QDRANT_URL environment variable is not set")
            return False

        # Extract host and port from URL
        if url.startswith("http://"):
            url = url[7:]
        elif url.startswith("https://"):
            url = url[8:]

        host, port = url.split(":")
        port = int(port)

        # Try to connect to the server
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)  # 2 second timeout
        result = sock.connect_ex((host, port))
        sock.close()

        return result == 0
    except Exception as e:
        logger.error(f"Error checking Qdrant connection: {str(e)}")
        return False


def get_embedding(
    text: str, client: OpenAI, model: str = "text-embedding-3-large"
) -> List[float]:
    """
    Get embedding for text using OpenAI's embedding model.

    Args:
        text (str): Text to get embedding for
        client (OpenAI): OpenAI client instance
        model (str): OpenAI embedding model to use

    Returns:
        List[float]: Embedding vector
    """
    try:
        logger.debug(
            f"Getting embedding for text of length {len(text)} using model {model}"
        )
        response = client.embeddings.create(input=text, model=model)
        logger.debug("Successfully generated embedding")
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {str(e)}")
        raise


@log_decorator("init_qdrant")
def init_qdrant_collection(
    client: QdrantClient, collection_name: str = COLLECTION_NAME
):
    """
    Initialize or get the Qdrant collection for rule storage.

    Args:
        client (QdrantClient): Qdrant client instance
        collection_name (str): Name of the collection
    """
    try:
        logger.info(f"Initializing Qdrant collection: {collection_name}")
        # Check if collection exists
        collections = client.get_collections().collections
        collection_names = [collection.name for collection in collections]

        if collection_name not in collection_names:
            logger.info(f"Creating new collection: {collection_name}")
            # Create collection if it doesn't exist
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=3072,  # OpenAI text-embedding-3-large dimension
                    distance=models.Distance.COSINE,
                ),
            )
            logger.info(f"Successfully created collection: {collection_name}")
        else:
            logger.info(f"Collection {collection_name} already exists")
    except Exception as e:
        logger.error(f"Error initializing Qdrant collection: {str(e)}")
        raise Exception(f"Error initializing Qdrant collection: {str(e)}")


@log_decorator("load_rules")
def load_rule_files(rules_dir: str) -> Dict[str, str]:
    """
    Load all rule files from the rules directory.

    Args:
        rules_dir (str): Path to the rules directory

    Returns:
        Dict[str, str]: Dictionary mapping rule filenames to their content
    """
    try:
        logger.info(f"Loading rule files from directory: {rules_dir}")
        rule_files = {}
        for file in Path(rules_dir).glob("*.drl"):
            logger.debug(f"Loading rule file: {file.name}")
            with open(file, "r", encoding="utf-8") as f:
                rule_files[file.name] = f.read()
        logger.info(f"Successfully loaded {len(rule_files)} rule files")
        return rule_files
    except Exception as e:
        logger.error(f"Error loading rule files: {str(e)}")
        raise


@log_decorator("index_rules")
def index_rules(
    client: QdrantClient,
    rules_dir: str,
    openai_client: OpenAI,
    collection_name: str = COLLECTION_NAME,
):
    """
    Index rule files in Qdrant.

    Args:
        client (QdrantClient): Qdrant client instance
        rules_dir (str): Path to the rules directory
        openai_client (OpenAI): OpenAI client instance
        collection_name (str): Name of the collection
    """
    try:
        logger.info("Starting rule indexing process")
        # Initialize collection
        init_qdrant_collection(client, collection_name)

        # Load rule files
        rule_files = load_rule_files(rules_dir)
        if not rule_files:
            logger.warning("No rule files found to index")
            return

        logger.info(f"Generating embeddings for {len(rule_files)} rules")
        # Prepare points for indexing
        points = []
        for rule_name, content in rule_files.items():
            logger.debug(f"Processing rule: {rule_name}")
            # Generate embedding using OpenAI
            embedding = get_embedding(content, openai_client)

            # Create point with UUID
            point = models.PointStruct(
                id=str(uuid.uuid4()),  # Generate a unique UUID for each point
                vector=embedding,
                payload={
                    "rule_name": rule_name,
                    "content": content,
                    "type": "rule_example",  # Add type for filtering
                    "format": "drl",  # Add format for filtering
                },
            )
            points.append(point)

        logger.info(f"Uploading {len(points)} points to Qdrant")
        # Upload points to Qdrant
        client.upsert(collection_name=collection_name, points=points)
        logger.info("Successfully indexed all rules")

    except Exception as e:
        logger.error(f"Error indexing rules: {str(e)}")
        raise Exception(f"Error indexing rules: {str(e)}")


def wait_for_operation(operation_func, *args, **kwargs):
    """
    Wait for an operation to complete with retries.

    Args:
        operation_func: Function to execute
        *args: Arguments for the function
        **kwargs: Keyword arguments for the function

    Returns:
        The result of the operation
    """
    start_time = time.time()
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            if time.time() - start_time > OPERATION_TIMEOUT:
                raise TimeoutError(
                    f"Operation timed out after {OPERATION_TIMEOUT} seconds"
                )

            result = operation_func(*args, **kwargs)
            return result

        except Exception as e:
            last_error = e
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

    raise last_error or Exception("Operation failed after all retries")


@log_decorator("search_rules")
def search_rules(query: str, rules_dir: str, api_key: str) -> Dict[str, any]:
    """
    Search for similar rules using Qdrant.

    Args:
        query (str): User's search query
        rules_dir (str): Path to the rules directory
        api_key (str): OpenAI API key

    Returns:
        Dict[str, any]: Search results with status and data
    """
    try:
        logger.info(f"Starting search for query: {query}")

        if not QDRANT_URL or not QDRANT_API_KEY:
            error_msg = "Qdrant configuration is missing. Please set QDRANT_URL and QDRANT_API_KEY environment variables."
            logger.error(error_msg)
            return {"success": False, "message": error_msg}

        # Check if Qdrant is accessible
        if not check_qdrant_connection(QDRANT_URL):
            error_msg = f"Qdrant server is not accessible at {QDRANT_URL}. Please ensure the server is running."
            logger.error(error_msg)
            return {"success": False, "message": error_msg}

        # Initialize clients
        logger.debug("Initializing Qdrant and OpenAI clients")
        qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        openai_client = OpenAI(api_key=api_key)

        # Generate query embedding using OpenAI
        logger.debug("Generating query embedding")
        try:
            query_embedding = wait_for_operation(get_embedding, query, openai_client)
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            return {
                "success": False,
                "message": f"Error processing search query: {str(e)}",
            }

        # Search in Qdrant
        logger.debug("Performing vector search in Qdrant")
        try:
            search_result = wait_for_operation(
                qdrant_client.search,
                collection_name=COLLECTION_NAME,
                query_vector=query_embedding,
                limit=3,  # Return top 3 most similar rules
            )
            logger.debug(f"Search returned {len(search_result)} results")
        except Exception as e:
            logger.error(f"Error performing search: {str(e)}")
            return {"success": False, "message": f"Error searching rules: {str(e)}"}

        if not search_result:
            logger.info("No matching rules found")
            return {"success": False, "message": "No rules found matching your query."}

        # Format results
        logger.debug("Formatting search results")
        rules = []
        for hit in search_result:
            try:
                # Log the full payload for debugging
                logger.debug(f"Search result payload: {hit.payload}")
                logger.debug(f"Search result score: {hit.score}")

                # Safely get payload fields with defaults
                payload = hit.payload or {}
                if not payload:
                    logger.warning("Empty payload in search result")
                    continue

                # Get source as rule_name if rule_name is not present
                rule_name = payload.get("rule_name") or payload.get("source")
                if not rule_name:
                    logger.warning("Missing both rule_name and source in payload")
                    continue

                # Get content from payload first, then try file
                content = payload.get("content")
                if not content:
                    # Try to read the file content
                    try:
                        file_path = os.path.join(rules_dir, rule_name)
                        if os.path.exists(file_path):
                            with open(file_path, "r", encoding="utf-8") as f:
                                content = f.read()
                        else:
                            logger.warning(f"File not found for rule: {rule_name}")
                            # If file not found but we have other metadata, still include the rule
                            if (
                                payload.get("type")
                                or payload.get("format")
                                or payload.get("title")
                            ):
                                content = f"Rule file not found: {rule_name}"
                            else:
                                continue
                    except Exception as e:
                        logger.warning(
                            f"Error reading file for rule {rule_name}: {str(e)}"
                        )
                        continue

                score = float(hit.score) if hasattr(hit, "score") else 0.0
                logger.debug(f"Processing rule: {rule_name} with score {score}")

                rules.append(
                    {
                        "rule_name": rule_name,
                        "content": content,
                        "similarity_score": score,
                        "type": payload.get("type", "unknown"),
                        "format": payload.get("format", "unknown"),
                        "title": payload.get("title", rule_name),
                    }
                )
                logger.debug(f"Successfully processed rule: {rule_name}")
            except Exception as e:
                logger.warning(f"Error processing search result: {str(e)}")
                continue

        if not rules:
            logger.info("No valid rules found in search results")
            return {
                "success": False,
                "message": "No valid rules found matching your query.",
            }

        logger.info(f"Found {len(rules)} matching rules")
        return {
            "success": True,
            "message": f"Found {len(rules)} similar rules",
            "rules": rules,
        }

    except Exception as e:
        logger.error(f"Error searching rules: {str(e)}")
        return {"success": False, "message": f"Error searching rules: {str(e)}"}


@log_decorator("ensure_rules_indexed")
def ensure_rules_indexed(rules_dir: str, api_key: str) -> bool:
    """
    Ensure that all rules are indexed in Qdrant. This should be called when:
    1. The system is first initialized
    2. New rules are added
    3. Existing rules are modified

    Args:
        rules_dir (str): Path to the rules directory
        api_key (str): OpenAI API key

    Returns:
        bool: True if indexing was successful, False otherwise
    """
    try:
        if not QDRANT_URL or not QDRANT_API_KEY:
            logger.error("Qdrant configuration is missing")
            return False

        # Initialize clients
        qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        openai_client = OpenAI(api_key=api_key)

        # Index rules
        try:
            wait_for_operation(index_rules, qdrant_client, rules_dir, openai_client)
            return True
        except Exception as e:
            logger.error(f"Error indexing rules: {str(e)}")
            return False

    except Exception as e:
        logger.error(f"Error ensuring rules are indexed: {str(e)}")
        return False


def delete_rule(rule_name: str, confirm: bool = False) -> str:
    """
    Delete a rule from the rules directory and Qdrant.

    Args:
        rule_name (str): Name of the rule to delete
        confirm (bool): Whether to confirm deletion without asking

    Returns:
        str: Status message
    """
    try:
        # First search for the rule to confirm
        search_results = search_rules(rule_name)
        if not search_results or "No valid rules found" in search_results:
            return f"Error: No rules found matching '{rule_name}'"

        # Get the best match
        best_match = search_results[0]
        if not confirm:
            print(f"\nFound matching rule:")
            print(f"Name: {best_match['rule_name']}")
            print(f"Content: {best_match['content']}")
            print(f"Similarity: {best_match['similarity']:.2f}")

            confirm = input("\nDo you want to delete this rule? (y/N): ").lower() == "y"
            if not confirm:
                return "Deletion cancelled by user"

        # Delete from filesystem
        rule_path = os.path.join(RULES_DIR, f"{best_match['rule_name']}.drl")
        if os.path.exists(rule_path):
            os.remove(rule_path)
            logger.info(f"Deleted rule file: {rule_path}")
        else:
            logger.warning(f"Rule file not found: {rule_path}")

        # Delete from Qdrant
        qdrant = get_qdrant_client()
        if not qdrant:
            return "Error: Could not connect to Qdrant"

        # Search for the point ID
        search_result = qdrant.search(
            collection_name=COLLECTION_NAME, query_vector=best_match["vector"], limit=1
        )

        if search_result and len(search_result) > 0:
            point_id = search_result[0].id
            qdrant.delete(
                collection_name=COLLECTION_NAME,
                points_selector=PointIdsList(points=[point_id]),
            )
            logger.info(f"Deleted rule from Qdrant: {best_match['rule_name']}")

        return f"Successfully deleted rule: {best_match['rule_name']}"

    except Exception as e:
        logger.error(f"Error deleting rule: {str(e)}")
        return f"Error deleting rule: {str(e)}"
