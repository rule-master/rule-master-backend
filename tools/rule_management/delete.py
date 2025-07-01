"""
Delete functionality for Drools rules.

This module provides functionality to delete rules from both the filesystem and Qdrant.
"""

import os
import shutil
import datetime
from typing import Dict, Any
from logger_utils import logger, log_decorator
from .search import search_rules
from qdrant_client import QdrantClient

@log_decorator("delete_rule")
def delete_rule(
    rule_name: str,
    rules_dir: str = None,
    api_key: str = None,
    confirm: bool = True
) -> Dict[str, Any]:
    """
    Delete a rule from both the filesystem and Qdrant.

    Args:
        rule_name (str): Name of the rule to delete
        rules_dir (str): Directory containing the rules (if None, uses RULES_DIRECTORY env var)
        api_key (str, optional): OpenAI API key. If not provided, will use environment variable.
        confirm (bool): If True, skip confirmation prompt
        search_results (Dict, optional): Pre-computed search results. If not provided, will search for the rule.

    Returns:
        dict: Status of the deletion operation
    """
    try:
        logger.info(f"Starting delete rule: {rule_name}")
    
        rules_directory = os.environ.get("RULES_DIRECTORY", "./rules/active_rules")
        old_rules_directory = os.environ.get("OLD_RULES_DIRECTORY", "./rules/old_rules")
        rules_prompt_directory = os.environ.get("RULES_PROMPT_DIRECTORY", "./rules/active_rules_prompt")
        old_rules_prompt_directory = os.environ.get("OLD_RULES_PROMPT_DIRECTORY", "./rules/old_rules_prompt")
        
        logger.info(f"Using rules directory: {rules_directory}")
        logger.info(f"Using old rules directory: {old_rules_directory}")
        logger.info(f"Using rules prompt directory: {rules_prompt_directory}")
        logger.info(f"Using old rules prompt directory: {old_rules_prompt_directory}")
        
        # Create directories if they don't exist (same as edit.py)
        os.makedirs(rules_directory, exist_ok=True)
        os.makedirs(old_rules_directory, exist_ok=True)
        os.makedirs(rules_prompt_directory, exist_ok=True)
        os.makedirs(old_rules_prompt_directory, exist_ok=True)
        
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

        # Proceed with deletion (confirmation handled at agent level)
        logger.info(f"Proceeding with deletion of rule: {matching_rule['filesystem_filename']}")
        
        # Get the base name for file operations (same as edit.py)
        base_name = os.path.splitext(matching_rule["filesystem_filename"])[0]
        logger.info(f"Base name for file operations: {base_name}")
        
        moved_files = []
        
        # Move GDST file to old_rules_directory (same pattern as edit.py)
        gdst_path = os.path.join(rules_directory, f"{base_name}.gdst")
        if os.path.exists(gdst_path):
            # Use version_file pattern but with old directory
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            dest_gdst = os.path.join(old_rules_directory, f"{base_name}_{ts}.gdst")
            shutil.move(gdst_path, dest_gdst)
            moved_files.append(f"{base_name}.gdst")
            logger.info(f"Moved GDST file from {gdst_path} to {dest_gdst}")
        else:
            logger.warning(f"GDST file not found at: {gdst_path}")
        
        # Move JSON file to old_rules_directory (same pattern as edit.py)
        json_path = os.path.join(rules_directory, f"{base_name}.json")
        if os.path.exists(json_path):
            # Use version_file pattern but with old directory
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            dest_json = os.path.join(old_rules_directory, f"{base_name}_{ts}.json")
            shutil.move(json_path, dest_json)
            moved_files.append(f"{base_name}.json")
            logger.info(f"Moved JSON file from {json_path} to {dest_json}")
        else:
            logger.warning(f"JSON file not found at: {json_path}")
        
        # Move prompt file to old_rules_prompt_directory (same pattern as edit.py)
        prompt_path = os.path.join(rules_prompt_directory, f"{base_name}.txt")
        if os.path.exists(prompt_path):
            # Use version_file pattern but with old directory
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            dest_prompt = os.path.join(old_rules_prompt_directory, f"{base_name}_{ts}.txt")
            shutil.move(prompt_path, dest_prompt)
            moved_files.append(f"{base_name}.txt")
            logger.info(f"Moved prompt file from {prompt_path} to {dest_prompt}")
        else:
            logger.warning(f"Prompt file not found at: {prompt_path}")

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
                collection_name="rule-master-dev",
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
                    collection_name="rule-master-dev",
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
            "message": f"Successfully moved rule files to old_rules directory: {', '.join(moved_files)}"
        }

    except Exception as e:
        logger.error(f"Error deleting rule: {str(e)}")
        return {
            "success": False,
            "message": f"Error deleting rule: {str(e)}"
        } 