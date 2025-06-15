"""
Add functionality for creating new Drools rules.

This module provides functionality to add new Drools rules (DRL or GDST)
from natural language descriptions using the NL-to-JSON-to-Drools pipeline.
"""

import os
import json
from typing import Dict, Any, Optional
from openai import OpenAI
from nl_to_json_extractor import NLToJsonExtractor
from json_to_drools_converter import convert_json_to_drools
from rag_setup import index_new_rule

def save_json_to_file(json_data, output_dir, filename=None):
    """
    Save the extracted JSON data to a file.
    
    Args:
        json_data: The JSON data to save
        output_dir: Directory to save the file (default: ./output)
        filename: Optional filename (without extension)
        
    Returns:
        Path to the saved file
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Use rule name or table name as filename if not provided
    if not filename:
        if "ruleName" in json_data:
            filename = json_data["ruleName"]
        elif "tableName" in json_data:
            filename = json_data["tableName"]
        else:
            filename = "extracted_rule"
    
    # Replace spaces with underscores in filename
    filename = filename.replace(" ", "_")
    
    # Save to file
    file_path = os.path.join(output_dir, f"{filename}.json")
    with open(file_path, "w") as f:
        json.dump(json_data, indent=2, fp=f)
    
    print(f"JSON saved to: {file_path}")
    return file_path


def add_rule(
    user_input: str,
    java_classes_map: Dict[str, str],
    rules_dir: str,
    api_key: Optional[str] = None,
    client: Optional[OpenAI] = None,
    collection_name: str = "rules"
) -> Dict[str, Any]:
    """
    Add a new Drools rule from natural language description.

    Args:
        user_input (str): Natural language description of the rule
        java_classes_map (dict): Dictionary mapping class name to package, class name and methods
        rules_dir (str): Directory to store the rule
        api_key (str, optional): OpenAI API key
        client (OpenAI, optional): OpenAI client instance
        collection_name (str): Name of the collection to add the rule to

    Returns:
        dict: Result of the operation
    """
    try:
        # Initialize the NL to JSON extractor
        extractor = NLToJsonExtractor(api_key=api_key)
        
        # Extract JSON schema from natural language
        json_schema = extractor.extract_to_json(user_input, "gdst", java_classes_map)
        
        # Save the JSON file first
        json_path = save_json_to_file(json_schema, rules_dir)
        
        # Convert JSON schema to GDST format
        output_path = convert_json_to_drools(json_schema, rules_dir, "gdst")
        
        # Get the GDST content for indexing
        try:
            # First try UTF-8
            with open(output_path, "r", encoding="utf-8") as f:
                gdst_content = f.read()
        except UnicodeDecodeError:
            try:
                # If UTF-8 fails, try latin-1 (which can read any byte)
                with open(output_path, "r", encoding="latin-1") as f:
                    gdst_content = f.read()
            except Exception as e:
                raise Exception(f"Failed to read GDST file with both UTF-8 and latin-1 encodings: {str(e)}")

        # Initialize OpenAI client if not provided
        if client is None:
            client = OpenAI(api_key=api_key)

        # Index the new rule
        index_new_rule(
            client=client,
            collection_name=collection_name,
            rule_content=gdst_content,
            file_path=output_path,
            refined_prompt=user_input
        )

        return {
            "success": True,
            "message": f"Successfully created GDST rule '{os.path.basename(output_path)}'",
            "file_path": output_path,
            "json_path": json_path
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error creating rule: {str(e)}",
            "error": str(e)
        } 