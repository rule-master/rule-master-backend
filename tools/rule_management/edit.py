"""
Edit tool implementation for Drools LLM Agent.

This module provides functionality to edit existing Drools rules (DRL or GDST)
from natural language descriptions using the NL-to-JSON-to-Drools pipeline.
"""

import os
import json
import shutil
import datetime
import re
from typing import Dict, Any, Optional, List, Tuple
from logger_utils import logger
from openai import OpenAI
from rag_setup import index_new_rule
from pathlib import Path
from qdrant_client import QdrantClient


# Import the NL to JSON extractor
from nl_to_json_extractor import NLToJsonExtractor

# Import the JSON to Drools converter
from json_to_drools_converter import convert_json_to_drools

def find_json_file(rules_directory: str, file_name: str) -> str:
    """
    Find the JSON file in the rules directory based on the file name.
    
    Args:
        rules_directory: Directory containing the rules
        file_name: Name of the file to edit (can be .gdst or .json)
        
    Returns:
        Path to the JSON file
    """
    logger.info(f"Looking for JSON file for {file_name} in {rules_directory}")
    
    # If file_name already ends with .json, use it directly
    if file_name.lower().endswith('.json'):
        json_path = os.path.join(rules_directory, file_name)
        if os.path.exists(json_path):
            logger.info(f"Found JSON file: {json_path}")
            return json_path
        
    # If file_name ends with .gdst, look for corresponding .json
    if file_name.lower().endswith('.gdst'):
        base_name = os.path.splitext(file_name)[0]
        json_path = os.path.join(rules_directory, f"{base_name}.json")
        if os.path.exists(json_path):
            logger.info(f"Found JSON file: {json_path}")
            return json_path
    
    # If file_name has no extension, try both .json and .gdst
    base_name = os.path.splitext(file_name)[0]
    json_path = os.path.join(rules_directory, f"{base_name}.json")
    if os.path.exists(json_path):
        logger.info(f"Found JSON file: {json_path}")
        return json_path
    
    # If no JSON file found, raise an exception
    logger.error(f"JSON file for {file_name} not found in {rules_directory}")
    raise FileNotFoundError(f"JSON file for {file_name} not found in {rules_directory}")

def identify_rule_type(json_data: Dict[str, Any]) -> str:
    """
    Identify the rule type (GDST or DRL) based on the JSON structure.
    
    Args:
        json_data: The JSON data
        
    Returns:
        Rule type: "gdst" or "drl"
    """
    logger.info("Identifying rule type from JSON structure")
    
    # Check if the JSON has tableName attribute (GDST)
    if "tableName" in json_data:
        logger.info("Rule type identified as GDST")
        return "gdst"
    # Check if the JSON has ruleName attribute (DRL)
    elif "ruleName" in json_data:
        logger.info("Rule type identified as DRL")
        return "drl"
    else:
        logger.error("Unable to identify rule type from JSON structure")
        raise ValueError("Unable to identify rule type from JSON structure")

def find_prompt_file(rules_prompt_directory: str, file_name: str) -> str:
    """
    Find the prompt file in the rules_prompt directory based on the file name.
    
    Args:
        rules_prompt_directory: Directory containing the rule prompts
        file_name: Name of the file to edit (can be .gdst, .json, or .txt)
        
    Returns:
        Path to the prompt file
    """
    logger.info(f"Looking for prompt file for {file_name} in {rules_prompt_directory}")
    
    # Get the base name without extension
    base_name = os.path.splitext(file_name)[0]
    
    # Try with .txt extension
    prompt_path = os.path.join(rules_prompt_directory, f"{base_name}.txt")
    if os.path.exists(prompt_path):
        logger.info(f"Found prompt file: {prompt_path}")
        return prompt_path
    
    # Try without extension
    prompt_path = os.path.join(rules_prompt_directory, base_name)
    if os.path.exists(prompt_path):
        logger.info(f"Found prompt file: {prompt_path}")
        return prompt_path
    
    # If no prompt file found, raise an exception
    logger.error(f"Prompt file for {file_name} not found in {rules_prompt_directory}")
    raise FileNotFoundError(f"Prompt file for {file_name} not found in {rules_prompt_directory}")

def create_consolidated_update_prompt(original_prompt: str, update_input: str) -> str:
    """
    Create a consolidated update prompt by combining the original prompt and the update input.
    
    Args:
        original_prompt: The original prompt generated from the JSON
        update_input: The user's update input
        
    Returns:
        Consolidated update prompt
    """
    logger.info("Creating consolidated update prompt")
    
    # Initialize OpenAI client
    api_key = os.environ.get("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)
    
    # Create system prompt for consolidating the prompts
    system_prompt = """You are a Drools rule assistant that works entirely in plain English.

Your task: given  
  1. an **original rule description** in natural language, and  
  2. a **user update instruction** (e.g. "make the lower bound 8 instead of 5," "add a new condition for holiday hours," "change salience to 80," etc.),  

you must emit a **single, revised rule description**—still in English—that applies exactly that change (and only that change), preserving everything else exactly as before.

**How to handle conditions and actions:**  
- **Users will describe conditions and actions in plain English.** You don't need to know any Drools internals—just find the sentence(s) that mention that condition or action and update or insert accordingly.  
- **To update an existing condition**, locate its English phrasing ("If sales are between 5 and 10…" → "If sales are between 8 and 10…") (if restaurant size is large then set employees to 5 -> if restaurant size is large then set employees to 10) and rewrite just that part.  
- **To add a new condition**, append it in the same style: "If [field] [operator] [value], then [action]."  
- **To change an action**, find the clause ("assign 2 extra employees") and swap in the new verb or number.  
- **To change salience**, find "Salience is X" (or "priority X") and replace X.  
- **Never re‐explain or re‐order** other parts of the rule—only inject or adjust the exact piece the user asked for.  

**Examples**

_Example A_  
- **Original:**  
  "Create a rule that assigns 5 employees if sales are between 0 and 5, and 2 employees if sales are between 5 and 10. Salience is 50."  
- **Instruction:** "Make the lower bound of the second range 6 instead of 5."  
- **Output:**  
  "Create a rule that assigns 5 employees if sales are between 0 and 5, and 2 employees if sales are between 6 and 10. Salience is 50."

_Example B_  
- **Original:**  
  "Create a rule named HolidayStaffing that adds 3 extra employees for holiday hours. Salience is 60."  
- **Instruction:** "Also add a condition for weekend hours to add 2 extra employees."  
- **Output:**  
  "Create a rule named HolidayStaffing that adds 3 extra employees for holiday hours, and adds 2 extra employees for weekend hours. Salience is 60."
"""
    
    # Create user prompt with the original prompt and update input
    user_prompt = f"""Original rule description:
{original_prompt}

Requested changes:
{update_input}

Create a consolidated prompt that incorporates the original rule and the requested changes:"""
    
    # Call the OpenAI API
    try:
        logger.info("Calling OpenAI API to create consolidated update prompt")
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using the same model as in NLToJsonExtractor
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        # Extract the consolidated prompt
        consolidated_prompt = response.choices[0].message.content.strip()
        logger.info(f"Created consolidated update prompt: {consolidated_prompt}")
        return consolidated_prompt
        
    except Exception as e:
        logger.error(f"Error creating consolidated update prompt: {str(e)}", exc_info=True)
        raise Exception(f"Error creating consolidated update prompt: {str(e)}")

def generate_file_name_with_llm(updated_prompt: str, java_classes_map: Dict[str, Dict]) -> str:
    """
    Generate a file name using LLM based on the updated prompt.
    
    Args:
        updated_prompt: The consolidated update prompt
        java_classes_map: Dictionary mapping class names to package, class name, and methods
        
    Returns:
        Generated file name
    """
    logger.info("Generating file name with LLM")
    
    # Initialize OpenAI client
    api_key = os.environ.get("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)
    
    # Create system prompt for file name generation
    system_prompt = """You are a specialized AI that generates file names for Drools rules.
Your task is to create a file name based on the rule description following these guidelines:

1. Use PascalCase (no spaces or punctuation).
2. Start with the action (verb + object), e.g. AssignExtraEmployees.
3. Then add By followed by the field names (the Java-bean property names) used in your conditions, joined with And.
4. Format: <ActionVerb><Object>By<FieldName1>And<FieldName2>
5. If there's only one field, omit the And….
6. Always convert each field name to PascalCase.

Examples:
* Conditions on timeSlotExpectedSales only: "AssignExtraEmployeesByTimeSlotExpectedSales"
* Conditions on both restaurantSize and dayOfWeek: "SetEmployeesCountByRestaurantSizeAndDayOfWeek"

Return ONLY the file name, nothing else.
"""
    
    # Add Java classes information to the system prompt
    if java_classes_map:
        system_prompt += "\n\nAvailable Java classes and their fields:\n"
        for class_name, class_info in java_classes_map.items():
            if "fields" in class_info:
                system_prompt += f"\n{class_name} fields:\n"
                for field in class_info["fields"]:
                    system_prompt += f"- {field}\n"
    
    # Create user prompt with the updated prompt
    user_prompt = f"Generate a file name for this Drools rule:\n\n{updated_prompt}\n\nFile name:"
    
    # Call the OpenAI API
    try:
        logger.info("Calling OpenAI API to generate file name")
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using the same model as in NLToJsonExtractor
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        # Extract the generated file name
        file_name = response.choices[0].message.content.strip()
        logger.info(f"Generated file name: {file_name}")
        return file_name
        
    except Exception as e:
        logger.error(f"Error generating file name: {str(e)}", exc_info=True)
        # Fallback to a default file name
        default_name = "UpdatedRule"
        logger.info(f"Using fallback file name: {default_name}")
        return default_name
    
def version_file(src: Path, archive_dir: Path) -> Optional[Path]:
    """
    Move src into archive_dir, renaming it with a timestamp suffix.
    Returns the archive path, or None if src didn't exist.
    """
    if not src.exists():
        logger.debug(f"No file to archive at {src}")
        return None

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    dest = archive_dir / f"{src.stem}_{ts}{src.suffix}"
    shutil.move(str(src), str(dest))
    logger.info(f"old version moved {src.name} → {dest}")
    return dest

def edit_rule(user_input: str, java_classes_map: Dict[str, Dict], file_name: str) -> Dict[str, Any]:
    """
    Edit an existing Drools rule from natural language description.
    
    Args:
        user_input (str): Natural language description of the changes
        java_classes_map (dict): Dictionary mapping class name to package, class name and methods
        file_name (str): Name of the file to edit
        
    Returns:
        dict: Result of the operation
    """
    logger.info(f"Starting edit operation for file: {file_name}")
    logger.info(f"User input: {user_input}")
    
    # Get API key from environment variables
    api_key = os.environ.get("OPENAI_API_KEY")
    
    # Get directories from environment variables
    rules_directory = os.environ.get("RULES_DIRECTORY", "./rules/active_rules")
    old_rules_directory = os.environ.get("OLD_RULES_DIRECTORY", "./rules/old_rules")
    rules_prompt_directory = os.environ.get("RULES_PROMPT_DIRECTORY", "./rules/active_rules_prompt")
    old_rules_prompt_directory = os.environ.get("OLD_RULES_PROMPT_DIRECTORY", "./rules/old_rules_prompt")
    
    logger.info(f"API key: {api_key}")
    logger.info(f"Rules directory: {rules_directory}")
    logger.info(f"Old rules directory: {old_rules_directory}")
    logger.info(f"Rules prompt directory: {rules_prompt_directory}")
    logger.info(f"Old rules prompt directory: {old_rules_prompt_directory}")
    
    # Create directories if they don't exist
    os.makedirs(rules_directory, exist_ok=True)
    os.makedirs(old_rules_directory, exist_ok=True)
    os.makedirs(rules_prompt_directory, exist_ok=True)
    os.makedirs(old_rules_prompt_directory, exist_ok=True)
    
    try:
        
        # Find the JSON file
        json_file_path = find_json_file(rules_directory, file_name)
        
        # Load the JSON data
        with open(json_file_path, 'r') as f:
            json_data = json.load(f)
        
        # Identify the rule type
        rule_type = identify_rule_type(json_data)
        
        # For DRL files, raise not implemented error
        if rule_type == "drl":
            logger.error("Editing DRL files is not supported yet")
            return {
                "success": False,
                "message": "Editing DRL files is not supported yet"
            }
        
        # Find the original prompt file
        prompt_file_path = find_prompt_file(rules_prompt_directory, file_name)
        
        # Read the original prompt
        with open(prompt_file_path, 'r') as f:
            original_prompt = f.read()
        
        # Create consolidated update prompt
        updated_prompt = create_consolidated_update_prompt(original_prompt, user_input)
        
        # Generate new file name
        new_file_base = generate_file_name_with_llm(updated_prompt, java_classes_map)
        
        # Initialize the NL to JSON extractor
        logger.info("Initializing NL to JSON extractor")
        extractor = NLToJsonExtractor(api_key=api_key)
        
        # Extract JSON schema from the updated prompt
        logger.info("Extracting JSON schema from updated prompt")
        new_json_data = extractor.extract_to_json(updated_prompt, rule_type, java_classes_map)
        
        # Update table name or rule name with the base file name
        if rule_type == "gdst":
            new_json_data["tableName"] = file_name
            logger.info(f"Updated tableName to: {file_name}")
        else:  # drl
            new_json_data["ruleName"] = file_name
            logger.info(f"Updated ruleName to: {file_name}")
        
        # Increment the version number
        original_version = json_data.get("version", 1)
        new_json_data["version"] = original_version + 1
        logger.info(f"Incremented version from {original_version} to {new_json_data['version']}")
        
        # Update the old JSON file with new_version_name
        json_data["new_version_name"] = new_file_base
        
        # Move the old JSON to old_rules_directory
        old_json_path = version_file(Path(json_file_path), Path(old_rules_directory))
        if old_json_path:
            logger.info(f"Moved old JSON file {json_file_path} to: {old_json_path}")
        
        # Save the new JSON file
        new_json_path = os.path.join(rules_directory, f"{new_file_base}.json")
        with open(new_json_path, 'w') as f:
            json.dump(new_json_data, f, indent=2)
        logger.info(f"Saved new JSON file to: {new_json_path}")
        
        # Move the old drools file to old_rules_directory
        original_base_name = os.path.splitext(os.path.basename(json_file_path))[0]
        logger.info(f"Original base name: {original_base_name}")
        
        # Find and move the old Drools file
        if rule_type == "gdst":
            old_drools_file = os.path.join(rules_directory, f"{original_base_name}.gdst")
        else:
            old_drools_file = os.path.join(rules_directory, f"{original_base_name}.drl")
        
        old_drools_path = version_file(Path(old_drools_file), Path(old_rules_directory))
        if old_drools_path:
            logger.info(f"Moved old {rule_type.upper()} file {old_drools_file} to: {old_drools_path}")
        
        # Convert the new JSON to Drools file
        logger.info(f"Converting new JSON to {rule_type.upper()} file")
        new_drools_path = convert_json_to_drools(new_json_data, rules_directory, rule_type, new_file_base)
        logger.info(f"Saved new {rule_type.upper()} file to: {new_drools_path}")
        
        # Move old prompt file to old_rules_prompt_directory
        old_prompt_path = version_file(Path(prompt_file_path), Path(old_rules_prompt_directory))
        if old_prompt_path:
            logger.info(f"Moved old prompt file {prompt_file_path} to: {old_prompt_path}")
            
        # Save the new prompt file
        new_prompt_path = os.path.join(rules_prompt_directory, f"{new_file_base}.txt")
        with open(new_prompt_path, 'w') as f:
            f.write(updated_prompt)
        logger.info(f"Saved new prompt file to: {new_prompt_path}")
        
        # Determine rule name for the response
        if rule_type == "drl":
            rule_name = new_json_data.get("ruleName", "unnamed_rule")
        else:  # gdst
            rule_name = new_json_data.get("tableName", "unnamed_table")
        
        logger.info(f"Edit operation completed successfully for rule: {rule_name}")

        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)

        # Reindex the updated rule (update existing point instead of creating new one)
        collection_name = "rule-master-dev"
        
        # First, find and delete the old index entry
        qdrant_client = QdrantClient(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            api_key=os.getenv("QDRANT_API_KEY"),
        )
        
        # Determine the old filename that should be in the index
        # Use the original file_name parameter (which could be with or without extension)
        old_filename = file_name
        if not old_filename.lower().endswith(('.gdst', '.drl')):
            # Add the appropriate extension based on rule type
            old_filename = f"{old_filename}.{rule_type}"
        
        logger.info(f"Looking for old index entry with filename: {old_filename}")
        
        # Search for the old rule entry
        search_result = qdrant_client.scroll(
            collection_name=collection_name,
            limit=100,
            with_payload=True,
            with_vectors=False
        )
        
        # Find the point with matching filename
        point_id = None
        logger.info(f"Found {len(search_result[0])} total points in collection")
        
        for point in search_result[0]:
            payload_filename = point.payload.get("filesystem_filename", "")
            logger.info(f"Checking payload filename: {payload_filename} against: {old_filename}")
            
            # Try exact match first
            if payload_filename == old_filename:
                point_id = point.id
                logger.info(f"Found exact matching point with ID: {point_id}")
                break
            
            # Try matching without extension
            if payload_filename and old_filename:
                payload_base = os.path.splitext(payload_filename)[0]
                old_base = os.path.splitext(old_filename)[0]
                if payload_base == old_base:
                    point_id = point.id
                    logger.info(f"Found base name matching point with ID: {point_id}")
                    break
        
        if point_id is not None:
            # Delete the old entry
            qdrant_client.delete(
                collection_name=collection_name,
                points_selector=[point_id]
            )
            logger.info(f"Deleted old index entry for: {old_filename}")
        else:
            logger.warning(f"No old index entry found for: {old_filename}")
            logger.info("Available filenames in collection:")
            for point in search_result[0]:
                logger.info(f"  - {point.payload.get('filesystem_filename', 'NO_FILENAME')}")
        
        # Now add the new entry with updated content
        index_new_rule(
            client=client,
            collection_name=collection_name,
            file_path=new_drools_path,
            refined_prompt=updated_prompt
        )
        
        # Return success response
        return {
            "success": True,
            "rule_type": rule_type.upper(),
            "rule_name": rule_name,
            "original_file": str(old_drools_path),
            "new_file": str(new_drools_path),
            "original_prompt": str(old_prompt_path),
            "new_prompt": str(new_prompt_path),
            "version": new_json_data["version"],
            "download_url": f"https://capstone.burhan.ai/rules/{os.path.basename(new_drools_path)}",
            "message": f"Successfully edited {rule_type.upper()} rule '{rule_name}' (version {new_json_data['version']}). Download: https://capstone.burhan.ai/rules/{os.path.basename(new_drools_path)}"
        }
    
    except Exception as e:
        logger.error(f"Error editing rule: {str(e)}", exc_info=True)
        # Return error response
        return {
            "success": False,
            "message": f"Error editing rule: {str(e)}"
        }