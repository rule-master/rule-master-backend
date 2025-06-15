"""
Delete functionality for Drools rules.

This module provides functionality to delete rules from both the filesystem and Qdrant.
"""

import os
from typing import Dict, Any
from logger_utils import logger, log_decorator
from .search import search_rules
from qdrant_client import QdrantClient

@log_decorator("delete_rule")
def delete_rule(
    rule_name: str,
    rules_dir: str = "rules",
    api_key: str = None,
    confirm: bool = True
) -> Dict[str, Any]:
    """
    Delete a rule from both the filesystem and Qdrant.

    Args:
        rule_name (str): Name of the rule to delete
        rules_dir (str): Directory containing the rules
        api_key (str, optional): OpenAI API key. If not provided, will use environment variable.
        confirm (bool): If True, skip confirmation prompt
        search_results (Dict, optional): Pre-computed search results. If not provided, will search for the rule.

    Returns:
        dict: Status of the deletion operation
    """
    try:
        logger.info(f"Starting delete rule: {rule_name}")
        
        # Use provided search results or search for the rule
        search_results = search_rules(rule_name, api_key=api_key)
        logger.info(f"Raw search results: {search_results}")
        
        # Extract results from the nested structure
        results = search_results.get("results", [])
        logger.info(f"Extracted results: {results}")
        
        if not results:
            logger.warning(f"No results found in search_results: {search_results}")
            return {
                "success": False,
                "message": f"Could not find any rules matching '{rule_name}'. Please check the rule name and try again."
            }
            
        # Get the base name without extension for matching
        rule_base_name = os.path.splitext(results[0]["filesystem_filename"])[0]
        logger.info(f"Looking for rule with base name: {rule_base_name}")
        
        # Find the matching rule by base name
        matching_rule = None
        for result in results:
            logger.info(f"Checking result: {result}")
            # Get the filesystem name and remove extension for comparison
            result_filename = result.get("filesystem_filename", "")
            result_base_name = os.path.splitext(result_filename)[0]
            logger.info(f"Comparing {rule_base_name} with {result_base_name}")
            if result_base_name.lower() == rule_base_name.lower():
                matching_rule = result
                logger.info(f"Found matching rule: {matching_rule}")
                break
                
        if not matching_rule:
            logger.warning(f"No matching rule found for base name: {rule_base_name}")
            return {
                "success": False,
                "message": f"Could not find any rules matching '{rule_name}'. Please check the rule name and try again."
            }

        # Get confirmation from user unless confirm flag is set
        if not confirm:
            response = input(
                f"Are you sure you want to delete the rule '{matching_rule['filesystem_filename']}'? (y/N): "
            )
            if response.lower() != "y":
                return {
                    "success": False,
                    "message": "Deletion cancelled by user."
                }

        # Ensure deleted_rules directory exists
        deleted_rules_dir = os.path.join(rules_dir, "deleted_rules")
        os.makedirs(deleted_rules_dir, exist_ok=True)

        # Move both GDST and JSON files to deleted_rules directory
        base_name = os.path.splitext(matching_rule["filesystem_filename"])[0]
        gdst_path = os.path.join(rules_dir, f"{base_name}.gdst")
        json_path = os.path.join(rules_dir, f"{base_name}.json")
        
        moved_files = []
        
        # Move GDST file
        if os.path.exists(gdst_path):
            dest_gdst = os.path.join(deleted_rules_dir, f"{base_name}.gdst")
            os.rename(gdst_path, dest_gdst)
            moved_files.append(f"{base_name}.gdst")
            logger.info(f"Moved GDST file from {gdst_path} to {dest_gdst}")
        
        # Move JSON file
        if os.path.exists(json_path):
            dest_json = os.path.join(deleted_rules_dir, f"{base_name}.json")
            os.rename(json_path, dest_json)
            moved_files.append(f"{base_name}.json")
            logger.info(f"Moved JSON file from {json_path} to {dest_json}")

        if not moved_files:
            logger.warning(f"No files found to move for rule: {matching_rule['filesystem_filename']}")
            return {
                "success": False,
                "message": f"No files found to move for rule: {matching_rule['filesystem_filename']}"
            }

        # Delete the rule from Qdrant
        try:
            qdrant_client = QdrantClient(
                url=os.getenv("QDRANT_URL", "http://localhost:6333"),
                api_key=os.getenv("QDRANT_API_KEY"),
            )
            
            # First search for the point using a payload filter
            search_result = qdrant_client.scroll(
                collection_name="drools-rule-examples",
                limit=100,  # Get a reasonable number of points
                with_payload=True,
                with_vectors=False
            )
            
            # Find the point with matching filename
            point_id = None
            for point in search_result[0]:
                if point.payload.get("filesystem_filename") == matching_rule["filesystem_filename"]:
                    point_id = point.id
                    break
            
            if point_id is not None:
                # Delete using the point ID
                qdrant_client.delete(
                    collection_name="drools-rule-examples",
                    points_selector=[point_id]
                )
                logger.info(f"Deleted rule from Qdrant: {matching_rule['filesystem_filename']}")
            else:
                logger.warning(f"No matching point found in Qdrant for {matching_rule['filesystem_filename']}")
            
        except Exception as e:
            logger.error(f"Error deleting from Qdrant: {str(e)}")
            return {
                "success": False,
                "message": f"Error deleting rule from Qdrant: {str(e)}"
            }

        return {
            "success": True,
            "message": f"Successfully moved rule files to deleted_rules directory: {', '.join(moved_files)}"
        }

    except Exception as e:
        logger.error(f"Error deleting rule: {str(e)}")
        return {
            "success": False,
            "message": f"Error deleting rule: {str(e)}"
        } 