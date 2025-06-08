"""
Add tool implementation for Drools LLM Agent.

This module provides functionality to add new Drools rules (DRL or GDST)
from natural language descriptions using the NL-to-JSON-to-Drools pipeline.
"""

import os
import json
from typing import Dict, Any, Optional

# Import the NL to JSON extractor
from nl_to_json_extractor import NLToJsonExtractor

# Import the JSON to Drools converter
from json_to_drools_converter import convert_json_to_drools

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
    import os
    import json
    
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
    
    # Save to file
    file_path = os.path.join(output_dir, f"{filename}.json")
    with open(file_path, "w") as f:
        json.dump(json_data, indent=2, fp=f)
    
    print(f"JSON saved to: {file_path}")
    return file_path


def add_rule(user_input: str, java_classes_map: Dict[str, str], rules_dir: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Add a new Drools rule from natural language description.
    
    Args:
        user_input (str): Natural language description of the rule
        java_classes_map (dict): Dictionary mapping class name to package, class name and methods
        rules_dir (str): Directory to store the rule
        api_key (str, optional): OpenAI API key
        
    Returns:
        dict: Result of the operation
    """
    try:
        # Initialize the NL to JSON extractor
        extractor = NLToJsonExtractor(api_key=api_key)
        
        # Detect rule type
        rule_type = extractor.detect_rule_type(user_input)
        
        # Extract JSON schema from natural language
        json_schema = extractor.extract_to_json(user_input, rule_type, java_classes_map)
        
        json_file_path = save_json_to_file(json_schema, rules_dir)
        
        # Convert JSON schema to Drools file
        output_path = convert_json_to_drools(json_schema, rules_dir)
        
        # Determine rule name for the response
        if rule_type == "drl":
            rule_name = json_schema.get("ruleName", "unnamed_rule")
        else:  # gdst
            rule_name = json_schema.get("tableName", "unnamed_table")
        
        # Return success response
        return {
            "success": True,
            "rule_type": rule_type.upper(),
            "rule_name": rule_name,
            "file_path": output_path,
            "message": f"Successfully created {rule_type.upper()} rule '{rule_name}'"
        }
    
    except Exception as e:
        # Return error response
        return {
            "success": False,
            "message": f"Error creating rule: {str(e)}"
        }
