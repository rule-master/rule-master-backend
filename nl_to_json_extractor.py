"""
LLM-driven Natural Language to JSON Schema Extractor for Drools Rules

This module provides functionality to extract structured JSON schemas from natural language
descriptions of Drools rules, which can then be converted to DRL or GDST files.
"""

import os
import re
import json
from typing import Dict, List, Any, Optional
import openai
from openai import OpenAI

class NLToJsonExtractor:
    """
    Extracts structured JSON schemas from natural language descriptions of Drools rules.
    """
    
    def __init__(self, api_key: str = None, model: str = "gpt-4o"):
        """
        Initialize the extractor with OpenAI API key and model.
        
        Args:
            api_key (str): OpenAI API key
            model (str): OpenAI model to use
        """
        self.api_key = api_key
        self.model = model
        self.client = OpenAI(api_key=api_key)
        
    def detect_rule_type(self, user_input: str) -> str:
        """
        Detect whether the natural language description should generate a DRL or GDST rule.
        
        Args:
            user_input (str): Natural language description of the rule
            
        Returns:
            str: "drl" or "gdst"
        """
        # Convert to lowercase for case-insensitive matching
        input_lower = user_input.lower()
        
        # Check for explicit mentions of decision table or GDST
        if any(term in input_lower for term in ["decision table", "gdst", "guided decision", "decision matrix"]):
            return "gdst"
        
        # Check for multiple ranges or thresholds
        range_patterns = [
            r'between\s+\d+\s+and\s+\d+',
            r'\d+\s*-\s*\d+',
            r'from\s+\d+\s+to\s+\d+',
            r'less than\s+\d+.*?greater than\s+\d+',
            r'if\s+.*?\d+.*?else if\s+.*?\d+'
        ]
        
        range_count = 0
        for pattern in range_patterns:
            range_count += len(re.findall(pattern, input_lower))
        
        # If multiple ranges are found, it's likely a GDST
        if range_count >= 2:
            return "gdst"
        
        # Check for multiple similar conditions
        condition_indicators = ["if", "when", "condition"]
        condition_count = sum(input_lower.count(indicator) for indicator in condition_indicators)
        
        # Check for multiple similar actions
        action_indicators = ["then", "assign", "set", "add"]
        action_count = sum(input_lower.count(indicator) for indicator in action_indicators)
        
        # If there are multiple conditions and actions, it's likely a GDST
        if condition_count >= 3 and action_count >= 3:
            return "gdst"
        
        # Check for multiple rows or entries
        if any(term in input_lower for term in ["row", "rows", "entry", "entries"]) and any(number in input_lower for number in ["multiple", "several", "many"]):
            return "gdst"
        
        # Default to DRL for simpler rules
        return "drl"
    
    def extract_to_json(self, user_input: str, rule_type: str = None, java_classes_map: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Extract structured JSON schema from natural language description.
        
        Args:
            user_input (str): Natural language description of the rule
            rule_type (str): "drl" or "gdst", if None will be auto-detected
            java_classes_map (dict): Dictionary mapping class names to package names
            
        Returns:
            dict: Structured JSON schema for the rule
        """
        # Auto-detect rule type if not provided
        if rule_type is None:
            rule_type = self.detect_rule_type(user_input)
        
        # Extract JSON schema based on rule type
        if rule_type == "drl":
            return self._extract_drl_json(user_input, java_classes_map)
        else:  # gdst
            return self._extract_gdst_json(user_input, java_classes_map)
    
    def _extract_drl_json(self, user_input: str, java_classes_map: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Extract DRL JSON schema from natural language description.
        
        Args:
            user_input (str): Natural language description of the rule
            java_classes_map (dict): Dictionary mapping class names to package names
            
        Returns:
            dict: Structured JSON schema for DRL rule
        """
        # Prepare the system prompt for DRL extraction
        system_prompt = """You are a specialized AI that extracts structured information from natural language descriptions of Drools rules to create a JSON schema. 

Your task is to extract ONLY the dynamic elements from the user's description and fill them into a predefined JSON structure for a Drools Rule Language (DRL) file.

The JSON schema for a DRL rule has the following structure:
```json
{
  "ruleName": "string",
  "packageName": "string",
  "imports": ["string"],
  "attributes": {
    "salience": number,
    "noLoop": boolean,
    "agenda-group": "string"
  },
  "globals": ["string"],
  "conditions": ["string"],
  "actions": ["string"]
}
```

IMPORTANT GUIDELINES:
1. Extract ONLY the dynamic elements mentioned in the user's description
2. For any fields not explicitly mentioned, use these defaults:
   - packageName: "com.myspace.rules"
   - imports: ["com.myspace.restopsrecomms.RestaurantData", "com.myspace.restopsrecomms.EmployeeRecommendation"]
   - salience: 10
   - conditions: ["$restaurant : RestaurantData()"]
   - actions: ["$recommendation : EmployeeRecommendation()"]
3. If the rule name is not specified, generate a descriptive one based on the rule's purpose
4. Format conditions and actions as valid Drools syntax
5. Return ONLY the JSON object, nothing else

Example:
User: "Create a rule that adds 2 employees when a restaurant has AutoKing and the restaurant size is Large. The rule should have a salience of 90."

Your response should be:
```json
{
  "ruleName": "recommend_extra_staff_for_autoking",
  "packageName": "com.myspace.rules",
  "imports": ["com.myspace.restopsrecomms.RestaurantData", "com.myspace.restopsrecomms.EmployeeRecommendation"],
  "attributes": {
    "salience": 90
  },
  "globals": [],
  "conditions": [
    "$restaurant : RestaurantData()",
    "$restaurant.hasAutoKing == true",
    "$restaurant.size == \"LARGE\""
  ],
  "actions": [
    "$recommendation : EmployeeRecommendation()",
    "$recommendation.setEmployees(2);"
  ]
}
```"""

        # Prepare the user prompt
        user_prompt = f"Extract the structured JSON schema for a DRL rule from this description: {user_input}"
        
        # Call the OpenAI API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Extract and parse the JSON response
        json_str = response.choices[0].message.content
        json_data = json.loads(json_str)
        
        # Update package name if Java classes are provided
        if java_classes_map:
            # Look for class names in the conditions and actions
            for class_name, package in java_classes_map.items():
                # Check if the class is used in conditions or actions
                conditions_str = " ".join(json_data.get("conditions", []))
                actions_str = " ".join(json_data.get("actions", []))
                
                if class_name in conditions_str or class_name in actions_str:
                    # Update package name and imports
                    json_data["packageName"] = package.rsplit(".", 1)[0]
                    
                    # Add import if not already present
                    full_class_path = f"{package}.{class_name}"
                    if full_class_path not in json_data.get("imports", []):
                        json_data.setdefault("imports", []).append(full_class_path)
        
        return json_data
    
    def _extract_gdst_json(self, user_input: str, java_classes_map: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Extract GDST JSON schema from natural language description.
        
        Args:
            user_input (str): Natural language description of the rule
            java_classes_map (dict): Dictionary mapping class names to package names
            
        Returns:
            dict: Structured JSON schema for GDST rule
        """
        # Prepare the system prompt for GDST extraction
        system_prompt = """You are a specialized AI that extracts structured information from natural language descriptions of Drools rules to create a JSON schema.

Your task is to extract ONLY the dynamic elements from the user's description and fill them into a predefined JSON structure for a Drools Guided Decision Table (GDST) file.

The JSON schema for a GDST rule has the following structure:
```json
{
  "tableName": "string",
  "packageName": "string",
  "imports": ["string"],
  "tableFormat": "EXTENDED_ENTRY",
  "hitPolicy": "NONE",
  "version": 1,
  "attributes": [
    {
      "name": "salience",
      "value": number,
      "dataType": "NUMERIC_INTEGER"
    }
  ],
  "conditionPatterns": [
    {
      "type": "Pattern",
      "factType": "string",
      "boundName": "string",
      "conditions": [
        {
          "header": "string",
          "factField": "string",
          "operator": "string",
          "fieldType": "string",
          "hidden": false,
          "width": 100
        }
      ]
    }
  ],
  "actionColumns": [
    {
      "type": "BRLAction",
      "header": "string",
      "definition": ["string"],
      "hidden": false
    }
  ],
  "data": [
    {
      "rowNumber": number,
      "description": "string",
      "values": [
        {
          "columnName": "string",
          "value": any,
          "dataType": "string"
        }
      ]
    }
  ]
}
```

IMPORTANT GUIDELINES:
1. Extract ONLY the dynamic elements mentioned in the user's description
2. For any fields not explicitly mentioned, use these defaults:
   - packageName: "com.myspace.rules"
   - imports: ["com.myspace.restopsrecomms.RestaurantData", "com.myspace.restopsrecomms.EmployeeRecommendation"]
   - tableFormat: "EXTENDED_ENTRY"
   - hitPolicy: "NONE"
   - version: 1
   - salience: 10
3. If the table name is not specified, generate a descriptive one based on the table's purpose
4. Convert table name to kebab-case (e.g., "staff-recommendation-table")
5. For conditions involving ranges (e.g., sales between X and Y), create two condition columns: one for ">=" and one for "<"
6. For each range mentioned, create a corresponding data row with the appropriate values
7. Return ONLY the JSON object, nothing else

Example:
User: "Create a staffing rule for restaurants based on total expected sales. If sales are between 0 and 100 dollars, assign 2 employees. If sales are between 100 and 200 dollars, assign 3 employees. If sales are between 200 and 300 dollars, assign 4 employees."

Your response should be:
```json
{
  "tableName": "restaurant-staffing-by-sales",
  "packageName": "com.myspace.rules",
  "imports": ["com.myspace.restopsrecomms.RestaurantData", "com.myspace.restopsrecomms.EmployeeRecommendation"],
  "tableFormat": "EXTENDED_ENTRY",
  "hitPolicy": "NONE",
  "version": 1,
  "attributes": [
    {
      "name": "salience",
      "value": 10,
      "dataType": "NUMERIC_INTEGER"
    }
  ],
  "conditionPatterns": [
    {
      "type": "Pattern",
      "factType": "RestaurantData",
      "boundName": "$restaurant",
      "conditions": [
        {
          "header": "Min Sales",
          "factField": "totalExpectedSales",
          "operator": ">=",
          "fieldType": "Double",
          "hidden": false,
          "width": 100
        },
        {
          "header": "Max Sales",
          "factField": "totalExpectedSales",
          "operator": "<",
          "fieldType": "Double",
          "hidden": false,
          "width": 100
        }
      ]
    }
  ],
  "actionColumns": [
    {
      "type": "BRLAction",
      "header": "Employees",
      "definition": ["$recommendation : EmployeeRecommendation()", "$recommendation.setEmployees(@{Employees})"],
      "hidden": false
    }
  ],
  "data": [
    {
      "rowNumber": 1,
      "description": "0-100 sales",
      "values": [
        {
          "columnName": "salience",
          "value": 10,
          "dataType": "NUMERIC_INTEGER"
        },
        {
          "columnName": "Min Sales",
          "value": 0.0,
          "dataType": "NUMERIC_DOUBLE"
        },
        {
          "columnName": "Max Sales",
          "value": 100.0,
          "dataType": "NUMERIC_DOUBLE"
        },
        {
          "columnName": "Employees",
          "value": "2",
          "dataType": "STRING"
        }
      ]
    },
    {
      "rowNumber": 2,
      "description": "100-200 sales",
      "values": [
        {
          "columnName": "salience",
          "value": 10,
          "dataType": "NUMERIC_INTEGER"
        },
        {
          "columnName": "Min Sales",
          "value": 100.0,
          "dataType": "NUMERIC_DOUBLE"
        },
        {
          "columnName": "Max Sales",
          "value": 200.0,
          "dataType": "NUMERIC_DOUBLE"
        },
        {
          "columnName": "Employees",
          "value": "3",
          "dataType": "STRING"
        }
      ]
    },
    {
      "rowNumber": 3,
      "description": "200-300 sales",
      "values": [
        {
          "columnName": "salience",
          "value": 10,
          "dataType": "NUMERIC_INTEGER"
        },
        {
          "columnName": "Min Sales",
          "value": 200.0,
          "dataType": "NUMERIC_DOUBLE"
        },
        {
          "columnName": "Max Sales",
          "value": 300.0,
          "dataType": "NUMERIC_DOUBLE"
        },
        {
          "columnName": "Employees",
          "value": "4",
          "dataType": "STRING"
        }
      ]
    }
  ]
}
```"""

        # Prepare the user prompt
        user_prompt = f"Extract the structured JSON schema for a GDST rule from this description: {user_input}"
        
        # Call the OpenAI API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Extract and parse the JSON response
        json_str = response.choices[0].message.content
        json_data = json.loads(json_str)
        
        # Update package name if Java classes are provided
        if java_classes_map:
            # Look for class names in the condition patterns and action columns
            for class_name, package in java_classes_map.items():
                # Check if the class is used in condition patterns
                for pattern in json_data.get("conditionPatterns", []):
                    if pattern.get("factType") == class_name:
                        # Update package name and imports
                        json_data["packageName"] = package.rsplit(".", 1)[0]
                        
                        # Add import if not already present
                        full_class_path = f"{package}.{class_name}"
                        if full_class_path not in json_data.get("imports", []):
                            json_data.setdefault("imports", []).append(full_class_path)
                
                # Check if the class is used in action columns
                for action in json_data.get("actionColumns", []):
                    definition_str = " ".join(action.get("definition", []))
                    if class_name in definition_str:
                        # Update package name and imports
                        json_data["packageName"] = package.rsplit(".", 1)[0]
                        
                        # Add import if not already present
                        full_class_path = f"{package}.{class_name}"
                        if full_class_path not in json_data.get("imports", []):
                            json_data.setdefault("imports", []).append(full_class_path)
        
        return json_data
