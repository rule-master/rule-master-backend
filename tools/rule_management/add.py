"""
Add tool implementation for Drools LLM Agent.

This module provides functionality to add new Drools rules (DRL or GDST)
from natural language descriptions using the NL-to-JSON-to-Drools pipeline.
"""

import os
import json
import datetime
import re
from typing import Dict, Any, Optional
from logger_utils import logger
from openai import OpenAI
from rag_setup import index_new_rule

# Import the NL to JSON extractor
from nl_to_json_extractor import NLToJsonExtractor

# Import the JSON to Drools converter
from json_to_drools_converter import convert_json_to_drools

def generate_file_name_with_llm(user_input: str, java_classes_map: Dict[str, Dict]) -> str:
    """
    Generate a file name using LLM based on the user input.
    
    Args:
        user_input: The user's natural language description of the rule
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
    
    # Create user prompt with the user input
    user_prompt = f"Generate a file name for this Drools rule:\n\n{user_input}\n\nFile name:"
    
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
        default_name = "NewRule"
        logger.info(f"Using fallback file name: {default_name}")
        return default_name

def get_base_file_name(file_name: str) -> str:
    """
    Get the base file name without timestamp.
    
    Args:
        file_name: The file name with timestamp
        
    Returns:
        Base file name without timestamp
    """
    # Remove timestamp pattern (_YYYYMMDD_HHMM)
    base_name = re.sub(r'_\d{8}_\d{4}$', '', file_name)
    logger.info(f"Base file name (without timestamp): {base_name}")
    return base_name

def save_json_to_file(json_data: Dict[str, Any], output_dir: str, filename: str) -> str:
    """
    Save the extracted JSON data to a file.
    
    Args:
        json_data: The JSON data to save
        output_dir: Directory to save the file
        filename: Filename (without extension)
        
    Returns:
        Path to the saved file
    """
    logger.info(f"Saving JSON to file: {filename}.json in directory: {output_dir}")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Save to file
    file_path = os.path.join(output_dir, f"{filename}.json")
    with open(file_path, "w") as f:
        json.dump(json_data, indent=2, fp=f)
    
    logger.info(f"JSON saved to: {file_path}")
    return file_path

def save_prompt_to_file(prompt: str, prompt_dir: str, filename: str) -> str:
    """
    Save the user prompt to a file.
    
    Args:
        prompt: The user prompt
        prompt_dir: Directory to save the prompt file
        filename: Filename (without extension)
        
    Returns:
        Path to the saved file
    """
    logger.info(f"Saving prompt to file: {filename}.txt in directory: {prompt_dir}")
    
    # Create prompt directory if it doesn't exist
    os.makedirs(prompt_dir, exist_ok=True)
    
    # Save to file
    file_path = os.path.join(prompt_dir, f"{filename}.txt")
    with open(file_path, "w") as f:
        f.write(prompt)
    
    logger.info(f"Prompt saved to: {file_path}")
    return file_path

def add_rule(user_input: str, java_classes_map: Dict[str, Dict]) -> Dict[str, Any]:
    """
    Add a new Drools rule from natural language description.
    
    Args:
        user_input (str): Natural language description of the rule
        java_classes_map (dict): Dictionary mapping class name to package, class name and methods
        
    Returns:
        dict: Result of the operation
    """
    logger.info(f"Starting add operation with user input: {user_input}")
    
    # Get API key from environment variables
    api_key = os.environ.get("OPENAI_API_KEY")
    
    # Get directories from environment variables
    rules_directory = os.environ.get("RULES_DIRECTORY", "./rules/active_rules")
    rules_prompt_directory = os.environ.get("RULES_PROMPT_DIRECTORY", "./rules/active_rules_prompt")
    
    logger.info(f"API key: {api_key}")
    logger.info(f"Rules directory: {rules_directory}")
    logger.info(f"Rules prompt directory: {rules_prompt_directory}")
    
    try:
        # Generate file name with LLM
        file_name = generate_file_name_with_llm(user_input, java_classes_map)
        
        # Initialize the NL to JSON extractor
        logger.info("Initializing NL to JSON extractor")
        extractor = NLToJsonExtractor(api_key=api_key)
        
        # Detect rule type
        logger.info("Detecting rule type")
        rule_type = extractor.detect_rule_type(user_input)
        logger.info(f"Detected rule type: {rule_type}")
        
        # Extract JSON schema from natural language
        logger.info("Extracting JSON schema from natural language")
        json_schema = extractor.extract_to_json(user_input, rule_type, java_classes_map)
        
        # Update table name or rule name with the base file name
        if rule_type == "gdst":
            json_schema["tableName"] = file_name
            logger.info(f"Updated tableName to: {file_name}")
        else:  # drl
            json_schema["ruleName"] = file_name
            logger.info(f"Updated ruleName to: {file_name}")
        
        # Save JSON to file
        json_file_path = save_json_to_file(json_schema, rules_directory, file_name)
        
        # Save user prompt to file
        prompt_file_path = save_prompt_to_file(user_input, rules_prompt_directory, file_name)
        
        # Convert JSON schema to Drools file
        logger.info(f"Converting JSON schema to {rule_type.upper()} file")
        output_path = convert_json_to_drools(json_schema, rules_directory, rule_type,file_name)
        logger.info(f"Drools file saved to: {output_path}")
        
        # Determine rule name for the response
        if rule_type == "drl":
            rule_name = json_schema.get("ruleName", "unnamed_rule")
        else:  # gdst
            rule_name = json_schema.get("tableName", "unnamed_table")
        
        logger.info(f"Add operation completed successfully for rule: {rule_name}")

        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)

        # Index the new rule
        collection_name = "rule-master-dev"
        index_new_rule(
            client=client,
            collection_name=collection_name,
            file_path=output_path,
            refined_prompt=user_input
        )
        
        # Return success response
        return {
            "success": True,
            "rule_type": rule_type.upper(),
            "rule_name": rule_name,
            "file_path": output_path,
            "json_path": json_file_path,
            "prompt_path": prompt_file_path,
            "download_url": f"https://capstone.burhan.ai/rules/{os.path.basename(output_path)}",
            "message": f"Successfully created {rule_type.upper()} rule '{rule_name}'.  Download: https://capstone.burhan.ai/rules/{os.path.basename(output_path)}"
        }
    
    except Exception as e:
        logger.error(f"Error creating rule: {str(e)}", exc_info=True)
        # Return error response
        return {
            "success": False,
            "message": f"Error creating rule: {str(e)}"
        }