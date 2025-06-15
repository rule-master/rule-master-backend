"""
Search functionality for finding similar Drools rules based on user input.

This module provides functionality to search through rules using Qdrant vector search.
"""

import os
from typing import List, Dict, Any
from openai import OpenAI
from qdrant_client import QdrantClient
from logger_utils import logger, log_decorator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Qdrant configuration from environment
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = "drools-rule-examples"

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

@log_decorator("search_rules")
def search_rules(
    query: str,
    api_key: str = None,
    client: OpenAI = None,
    collection_name: str = COLLECTION_NAME,
) -> Dict[str, Any]:
    """
    Search for rules using semantic search.

    Args:
        query (str): The search query
        api_key (str, optional): OpenAI API key. If not provided, will use environment variable.
        client (OpenAI, optional): OpenAI client instance. If not provided, will create one.
        collection_name (str): Name of the Qdrant collection to search in

    Returns:
        dict: Search results containing matching rules and their metadata
    """
    # Initialize OpenAI client if not provided
    if client is None:
        client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    # Initialize Qdrant client
    qdrant_client = QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY"),
    )

    # Get the embedding for the query
    query_embedding = get_embedding(query, client)

    # Search the collection
    search_results = qdrant_client.search(
        collection_name=collection_name,
        query_vector=query_embedding,
        limit=5,  # Return top 5 matches
    )

    # Format the results
    formatted_results = []
    for result in search_results:
        payload = result.payload
        filesystem_filename = payload["filesystem_filename"]
        # Create filesystem-friendly name by replacing spaces with underscores
        filesystem_filename = filesystem_filename.replace(" ", "_")
        
        formatted_results.append({
            "filesystem_filename": filesystem_filename,  # Use filesystem name for operations
            "refined_prompt": payload["refined_prompt"],
            "relevance_score": result.score
        })

    return {
        "status": "success",
        "message": f"Found {len(formatted_results)} matching rules",
        "results": formatted_results
    } 