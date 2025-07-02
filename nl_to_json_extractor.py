"""
LLM-driven Natural Language to JSON Schema Extractor for Drools Rules - Modular Prompt-Driven Version

This module provides functionality to extract structured JSON schemas from natural language
descriptions of Drools rules, which can then be converted to DRL or GDST files.

Key features:
1. Dynamic Java class support with package and method extraction
2. Separation of condition patterns and BRL conditions
3. Clear guidelines for when to use each condition type
4. No hard-coding - all schema generation is driven by the LLM prompt
5. Complete schema adherence through prompt engineering
6. Modular prompt structure for better maintainability
"""

import os
import re
import json
from typing import Dict, List, Any, Optional
from openai import OpenAI

class NLToJsonExtractor:
    """
    Extracts structured JSON schemas from natural language descriptions of Drools rules.
    """
    
    def __init__(self, api_key: str = None, model: str = "gpt-4o-mini"):
        """
        Initialize the extractor with OpenAI API key and model.
        
        Args:
            api_key (str): OpenAI API key
            model (str): OpenAI model to use
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.client = OpenAI(api_key=self.api_key)
        # self.package = os.environ.get("DROOLS_PACKAGE_NAME", "com.myspace.resopsrecomms")
        self.package = "com.myspace.resopsrecomms"
        print(f"Using package name: {self.package}")
        
    def detect_rule_type(self, user_input: str) -> str:
        """
        Detect whether the natural language description should generate a DRL or GDST rule.
        
        Args:
            user_input (str): Natural language description of the rule
            
        Returns:
            str: "drl" or "gdst"
        """
        # # Convert to lowercase for case-insensitive matching
        # input_lower = user_input.lower()
        
        # # Check for explicit mentions of decision table or GDST
        # if any(term in input_lower for term in ["decision table", "gdst", "guided decision", "decision matrix"]):
        #     return "gdst"
        
        # # Check for multiple ranges or thresholds
        # range_patterns = [
        #     r'between\s+\d+\s+and\s+\d+',
        #     r'\d+\s*-\s*\d+',
        #     r'from\s+\d+\s+to\s+\d+',
        #     r'less than\s+\d+.*?greater than\s+\d+',
        #     r'if\s+.*?\d+.*?else if\s+.*?\d+'
        # ]
        
        # range_count = 0
        # for pattern in range_patterns:
        #     range_count += len(re.findall(pattern, input_lower))
        
        # # If multiple ranges are found, it's likely a GDST
        # if range_count >= 2:
        #     return "gdst"
        
        # # Check for multiple similar conditions
        # condition_indicators = ["if", "when", "condition"]
        # condition_count = sum(input_lower.count(indicator) for indicator in condition_indicators)
        
        # # Check for multiple similar actions
        # action_indicators = ["then", "assign", "set", "add"]
        # action_count = sum(input_lower.count(indicator) for indicator in action_indicators)
        
        # # If there are multiple conditions and actions, it's likely a GDST
        # if condition_count >= 3 and action_count >= 3:
        #     return "gdst"
        
        # # Check for multiple rows or entries
        # if any(term in input_lower for term in ["row", "rows", "entry", "entries"]) and any(number in input_lower for number in ["multiple", "several", "many"]):
        #     return "gdst"
        
        # # # Default to DRL for simpler rules
        # # return "drl" 
        # # Default to GDST for all cases since drl is not supported
        return "gdst"
    
    def extract_to_json(self, user_input: str, rule_type: str = "gdst", java_classes_map: Dict[str, Dict] = None) -> Dict[str, Any]:
        """
        Extract structured JSON schema from natural language description.
        
        Args:
            user_input (str): Natural language description of the rule
            rule_type (str): "drl" or "gdst", defaults to "gdst"
            java_classes_map (dict): Dictionary mapping class names to package, class name, and methods
            
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
          
    def _extract_drl_json(self, user_input: str, java_classes_map: Dict[str, Dict] = None) -> Dict[str, Any]:
        """
        Extract DRL JSON schema from natural language description.
        
        Args:
            user_input (str): Natural language description of the rule
            java_classes_map (dict): Dictionary mapping class names to package, class name, and methods
            
        Returns:
            dict: Structured JSON schema for DRL rule
        """
        # Prepare the system prompt for DRL extraction
        system_prompt = self._create_drl_system_prompt(java_classes_map)
        
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
        
        return json_data
      
    def _create_drl_system_prompt(self, java_classes_map: Dict[str, Dict] = None) -> str:
        """
        Create the system prompt for DRL extraction.
        
        Args:
            java_classes_map (dict): Dictionary mapping class names to package, class name, and methods
            
        Returns:
            str: System prompt for DRL extraction
        """
        # Base system prompt
        system_prompt = f"""You are a specialized AI that extracts structured information from natural language descriptions of Drools rules to create a JSON schema. 

Your task is to extract ONLY the dynamic elements from the user's description and fill them into a predefined JSON structure for a Drools Rule Language (DRL) file.

The JSON schema for a DRL rule has the following structure:
```json
{{
  "ruleName": "string",
  "packageName": "string",
  "imports": ["string"],
  "salience": number,
  "conditions": ["string"],
  "actions": ["string"]
}}
```

IMPORTANT GUIDELINES:
1. use "{self.package}" as the package name.
2. "imports" must be an array of Java package strings needed by this rule. Always include:
  - Any Java-bean classes referenced in conditions or actions (e.g. com.myspace.restaurant_staffing.RestaurantSales, com.myspace.restaurant_staffing.EmployeeRecommendation).
  - If any condition or action uses LocalTime or calls .toLocalTime(), LocalTime.parse(...), or similar, you must also include "java.time.LocalTime".
  - If the user provided additional Java library names in their input, append those here as well.
3. Extract ONLY the dynamic elements mentioned in the user's description such as conditions, actions, salience, and rule name (if provided).
4. If the rule name is not specified, generate a descriptive one based on the rule's purpose
5. If the user does not provide a salience, use 10 as the default salience.
6. Format conditions and actions as valid Drools drl syntax
7. Return ONLY the JSON object, nothing else
"""
        java_classes_prompt = "\n\n**Java Class Information:**\n"
        java_classes_prompt += "You have access to the following Java class definitions:\n"
        
        for class_name, class_info in java_classes_map.items():
            package = class_info.get("package", "")
            methods = class_info.get("methods", [])
            fields = class_info.get("fields", [])
            
            java_classes_prompt += f"\nClass: {class_name}\n"
            java_classes_prompt += f"Package: {package}\n"
            
            if fields:
                java_classes_prompt += "Fields:\n"
                for field in fields:
                    java_classes_prompt += f"- {field}\n"
            
            if methods:
                java_classes_prompt += "Methods:\n"
                for method in methods:
                    java_classes_prompt += f"- {method}\n"
        
        java_classes_prompt += "\n**IMPORTANT INSTRUCTIONS FOR JAVA CLASSES:**\n"
        java_classes_prompt += "1. Use the correct package names for imports based on the Java class definitions\n"
        java_classes_prompt += "2. When writing conditions and actions, select the appropriate Java-bean properties and methods based on the user's intent:\n"
        java_classes_prompt += "   - For 'add' operations, use methods starting with 'add'\n"
        java_classes_prompt += "   - For 'set' operations, use methods starting with 'set'\n"
        java_classes_prompt += "   - for properties, use the appropriate property name\n"
        java_classes_prompt += "   - Match the method signature with the appropriate parameters\n"
        java_classes_prompt += "3. Always place '$recommendation : EmployeeRecommendation()' instantiation in the conditions section\n"
        
        system_prompt += java_classes_prompt
        
        # Add example
        system_prompt += """

Example:
User: "Create a rule that adds 2 employees when a restaurant has AutoKing and the restaurant size is Large. The rule should have a salience of 90."

Your response should be:
```json
{
  "ruleName": "recommend_extra_staff_for_autoking",
  "packageName": "com.myspace.rules",
  "imports": ["com.myspace.restopsrecomms.RestaurantData", "com.myspace.restopsrecomms.EmployeeRecommendation"],
  "salience": 90,
  "conditions": [
    "$restaurant : RestaurantData(hasAutoKing == true, size == \"LARGE\")",
    "$recommendation : EmployeeRecommendation()"
  ],
  "actions": [
    "$recommendation.addRestaurantExtraEmployees(2);"
  ]
}
```
another example:
User: "Create a rule that adds 2 employees when a restaurant has AutoKing and the restaurant size is Large. The rule should have a salience of 90."

Your response should be:
```json
{
  "ruleName": "recommend_staffing_based_on_sales",
  "packageName": "com.myspace.rules",
  "imports": ["com.myspace.restopsrecomms.RestaurantData", "com.myspace.restopsrecomms.EmployeeRecommendation"],
  "salience": 80,
  "conditions": [
    "$restaurant : RestaurantData(totalExpectedSales > 5000)",
    "$recommendation : EmployeeRecommendation()"
  ],
  "actions": [
    "$recommendation.addRestaurantEmployees(2);"
  ]
}
```
another example:
User: "Create a rule that adds 3 employees when a restaurant size is Large. The rule should have a salience of 80."

Your response should be:
```json
{
  "ruleName": "recommend_extra_staff_for_large_restaurant",
  "packageName": "com.myspace.rules",
  "imports": ["com.myspace.restopsrecomms.RestaurantData", "com.myspace.restopsrecomms.EmployeeRecommendation"],  
  "salience": 80,
  "conditions": [
    "$restaurant : RestaurantData(restaurantSize == \"L\")",
    "$recommendation : EmployeeRecommendation()"
  ],
  "actions": [
    "$recommendation.addRestaurantEmployees(3);"
  ]
}
```
another example:
User: "Create a rule that adds 2 employees when a restaurant's time slot expected sales is greater than 4000. The rule should have a salience of 75."

Your response should be:
```json
{
  "ruleName": "recommend_staff_for_peak_time_slot",
  "packageName": "com.myspace.rules",
  "imports": ["com.myspace.restopsrecomms.RestaurantData", "com.myspace.restopsrecomms.EmployeeRecommendation"],
  "salience": 75,
  "conditions": [
    "$restaurant : RestaurantData(timeSlotExpectedSales > 4000)",
    "$recommendation : EmployeeRecommendation()"
  ],
  "actions": [
    "$recommendation.addRestaurantEmployees(2);"
  ]
}
```
"""

        return system_prompt
    
    def _extract_gdst_json(self, user_input: str, java_classes_map: Dict[str, Dict] = None) -> Dict[str, Any]:
        """
        Extract GDST JSON schema from natural language description.
        
        Args:
            user_input (str): Natural language description of the rule
            java_classes_map (dict): Dictionary mapping class names to package, class name, and methods
            
        Returns:
            dict: Structured JSON schema for GDST rule
        """
        # Prepare the system prompt for GDST extraction using the modular approach
        system_prompt = self._create_gdst_system_prompt(java_classes_map)
        
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
        try:
            json_data = json.loads(json_str)
            
            # # Fix key naming if needed - ensure conditionsBRL is used instead of conditionPatterns
            # if "conditionPatterns" in json_data and "conditionsBRL" not in json_data:
            #     # Extract BRLCondition entries
            #     brl_conditions = []
            #     pattern_conditions = []
                
            #     # Check if conditionPatterns is a list
            #     if isinstance(json_data["conditionPatterns"], list):
            #         for cond in json_data["conditionPatterns"]:
            #             if isinstance(cond, dict) and cond.get("type") == "BRLCondition":
            #                 brl_conditions.append(cond)
            #             elif isinstance(cond, dict) and cond.get("type") == "Pattern":
            #                 pattern_conditions.append(cond)
                
            #     # Set the correct keys
            #     json_data["conditionsBRL"] = brl_conditions
            #     if pattern_conditions:
            #         json_data["conditionPatterns"] = pattern_conditions
            #     else:
            #         json_data["conditionPatterns"] = []
                    
            # # Ensure conditionsBRL exists
            # if "conditionsBRL" not in json_data:
            #     json_data["conditionsBRL"] = []
                
            # # Ensure conditionPatterns exists
            # if "conditionPatterns" not in json_data:
            #     json_data["conditionPatterns"] = []
                
            return json_data
            
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from LLM: {e}")
            print(f"Received content: {json_str}")
            # Return an empty dict or raise an error, depending on desired handling
            return {}
            
        return json_data

    def _create_gdst_system_prompt(self, java_classes_map: Dict[str, Dict] = None) -> str:
        """
        Create the system prompt for GDST extraction using a modular approach.
        
        Args:
            java_classes_map (dict): Dictionary mapping class names to package, class name, and methods
            
        Returns:
            str: System prompt for GDST extraction
        """
        # Combine all prompt sections
        system_prompt = "You are a specialized AI that extracts structured information from natural language descriptions of Drools rules to create a JSON schema.\n\n"
        system_prompt += "Your task is to extract ONLY the dynamic elements from the user's description and fill them into a predefined JSON structure for a Drools Guided Decision Table (GDST) file. Follow the instructions precisely.\n\n"
        system_prompt += "**JSON Schema Structure and Instructions:**\n\n"
        
        # Add each section
        system_prompt += self._create_base_structure_prompt()
        system_prompt += self._create_brl_condition_prompt()
        system_prompt += self._create_pattern_condition_prompt()
        system_prompt += self._create_brl_action_prompt()
        system_prompt += self._create_data_list_prompt()
        system_prompt += self._create_guidelines_prompt()
        
        # Add Java class information if available
        if java_classes_map:
            system_prompt += self._create_java_classes_prompt(java_classes_map)
        
        return system_prompt
    
    def _create_base_structure_prompt(self) -> str:
        """
        Create the prompt section for the base structure.
        
        Returns:
            str: Prompt section for base structure
        """
        return f"""**1. Top-Level Structure:**
```json
{{
  "tableName":       "<string of table name>",
  "packageName":     "<string of package name>",
  "imports":         [ ... ],
  "tableFormat":     "EXTENDED_ENTRY",
  "hitPolicy":       "NONE",
  "version":         739,
  "attributes":      [ ... ],
  "conditionsBRL":   [ ... ],
  "conditionPatterns": [ ... ],
  "actionColumns":   [ ... ],
  "data":            [ ... ]
}}
```
- "tableName" and "packageName" come directly from the user's input. If not provided, infer a suitable tableName and use "{self.package}" for packageName.
- "imports" must be an array of Java package strings needed by this table. Always include:
  - Any Java-bean classes referenced in BRLCondition or BRLAction (e.g. com.myspace.restaurant_staffing.RestaurantSales, com.myspace.restaurant_staffing.EmployeeRecommendation).
  - If any condition or action uses LocalTime or calls .toLocalTime(), LocalTime.parse(...), or similar, you must also include "java.time.LocalTime".
  - If the user provided additional Java library names in their input, append those here as well.
- "tableFormat" is always "EXTENDED_ENTRY".
- "hitPolicy" is always "NONE".
- "version" is always 739.
- "attributes" is an array containing exactly one objects in this order:
  1. {{ "name": "salience", "value": <number>, "dataType": "NUMERIC_INTEGER", "hideColumn": false, "reverseOrder": false, "useRowNumber": false }}
  - Use the salience value provided by the user. If not provided, use a default of 10.
  - Always include "reverseOrder": false and "useRowNumber": false for the salience attribute.

"""
    
    def _create_brl_condition_prompt(self) -> str:
        """
        Create the prompt section for BRL conditions.
        
        Returns:
            str: Prompt section for BRL conditions
        """
        return """**2. BRLConditionColumn:**
You must always create two BRLCondition entries for instantiation the requisite Java bean instances.

*   **EmployeeRecommendation instantiation (Required):**
    ```json
    {
      "type": "BRLCondition",
      "width": -1,
      "header": "Employee Recommendation",
      "hidden": false,
      "constraintValueType": 1,
      "parameters": "",
      "definition": [
        {"text": "recommendation : EmployeeRecommendation()"}
      ],
      "childColumns": {
        "BRLConditionVariableColumn": {
          "typedDefaultValue": { "valueBoolean": true, "valueString": "", "dataType": "BOOLEAN", "isOtherwise": false },
          "hideColumn": true,
          "width": 100,
          "header": "Employee Recommendation",
          "constraintValueType": 1,
          "fieldType": "Boolean",
          "parameters": "",
          "varName": "recommendation"
        }
      }
    }
    ```
*   **RestaurantData binding instantiation (Required):**
    ```json
    {
      "type": "BRLCondition",
      "width": -1,
      "header": "Restaurant Data",
      "hidden": false,
      "constraintValueType": 1,
      "parameters": "",
      "definition": [
         {"text": "restaurantData : RestaurantData()"}
      ],
      "childColumns": {
        "BRLConditionVariableColumn": {
          "typedDefaultValue": { "valueBoolean": true, "valueString": "", "dataType": "BOOLEAN", "isOtherwise": false },
          "hideColumn": true,
          "width": 100,
          "header": "Restaurant Data",
          "constraintValueType": 1,
          "fieldType": "Boolean",
          "parameters": "",
          "varName": "restaurantData"
        }
      }
    }
    ```
*   **Complex BRL Condition (use it only if the user provides a condition with complex boolean expression (e.g. arithmetic, custom utility calls, Java `LocalTime` comparisons or parsing e.g. LocalTime.parse()) requiring `eval(...)`. never use for simple field comparisons conditions that doesn't require arithmetic calculation or custom utility calls):**
    ```json
    {
      "type": "BRLCondition",
      "width": -1,
      "header": "<a short description of what this Boolean test does>",
      "hidden": false,
      "constraintValueType": 1,
      "parameters": "",
      "definition": [
        {"text": "eval(<YOUR_COMPLEX_BOOLEAN_EXPRESSION_HERE>)"}
      ],
      "childColumns": {
        "BRLConditionVariableColumn": {
          "typedDefaultValue": {
            "valueBoolean": true,
            "valueString": "",
            "dataType": "BOOLEAN",
            "isOtherwise": false
          },
          "hideColumn": false,
          "width": 100,
          "header": "<a name that describes this test in human-readable form>",
          "constraintValueType": 1,
          "fieldType": "Boolean",
          "parameters": "",
          "varName": "<VARIABLE_NAME>"
        }
      }
    }
    ```
    - **IMPORTANT GUIDELINES:**
      - if the condition provided by user only includes a Java-bean field with no arithmetic calculation, then this shouldn't be converted to BRLCondition, instead it should be converted to Pattern condition.
        > e.g. if condition provided by user is (totalExpected is between 100 and 300), then this shouldn't be converted to BRLCondition, instead it should be converted to Pattern condition.
        > e.g. if condition provided by user is (totalExpected is greater than 100), then this shouldn't be converted to BRLCondition, instead it should be converted to Pattern condition.
        > e.g. if condition provided by user is (restaurantSize == "M"), then this shouldn't be converted to BRLCondition, instead it should be converted to Pattern condition.
        > e.g. if condition provided by user is (totalExpectedSales % 2 == 0), then this should be converted to BRLCondition because there is arithmetic calculation involved.
        > e.g. if condition provided by user is (getcalculationDateTime().toLocalTime() &gt;= LocalTime.parse(&quot;@{targetTime}&quot;)), then this should be converted to BRLCondition because there is complex comparison involved using external library `LocalTime`.
    - **Field Explanations:**
      - `type`: Always set "type": "BRLCondition".
      - `width`, `hidden`, `constraintValueType`, `parameters`: Always use exactly "width": -1, "hidden": false, "constraintValueType": 1, and "parameters": "".
      - `header`: Fill in a brief description of what this condition does.
      - `definition.text`: Must start with eval( and end with )—the entire complex Boolean expression goes inside (e.g. arithmetic, custom utility calls, Java `LocalTime` comparisons or parsing e.g. LocalTime.parse()). use resturantData binding when calling getter method e.g. eval(restaurantData.getCalculationDateTime().toLocalTime() &gt;= LocalTime.parse(&quot;@{targetTime}&quot;))
      - `childColumns.BRLConditionVariableColumn`: Always include a single BRLConditionVariableColumn with appropriate typedDefaultValue.
      - `varName`: Must match exactly any placeholder used inside your eval(...) string. If no placeholder is used, choose any meaningful varName.

"""
    
    def _create_pattern_condition_prompt(self) -> str:
        """
        Create the prompt section for pattern conditions.
        
        Returns:
            str: Prompt section for pattern conditions
        """
        return """**3. Pattern Conditions:**
Whenever you need to create a "Pattern" entry (i.e., a standard Drools Pattern52 for a POJO's property constraints), follow this exact JSON schema and fill in each field according to the user's description:
```json
{
  "type": "Pattern",
  "factType": "<Java-bean/class name>",
  "boundName": "<same as factType>",
  "isNegated": false,
  "conditions": [
    {
      "typedDefaultValue": {
        "valueString": "<always include this tag; leave empty unless user gave a default>",
        "valueNumeric": {
          "class": "<\"int\" or \"double\", matching fieldType>",
          "value": "<omit this object entirely if no default, otherwise put e.g. 1 or 3.14>"
        },
        "valueBoolean": "<omit if no default, otherwise true or false>",
        "dataType": "<exact Drools dataType for this field: \"NUMERIC_INTEGER\", \"NUMERIC_DOUBLE\", \"STRING\" or \"BOOLEAN\">",
        "isOtherwise": false
      },
      "header": "<column header text describing the condition operator")>",
      "constraintValueType": 1,
      "factField": "<exact Java-bean property name (e.g. \"totalExpectedSales\")>",
      "operator": "<one of \"&lt;=\", \"&gt;=\", \"&lt;\", \"&gt;\", \"==\">",
      "fieldType": "<Java property type: e.g. \"Double\", \"Integer\", \"String\", or \"Boolean\">",
      "hidden": false,
      "width": 100,
      "parameters": "",
      "binding": ""
    }
  ],
  "window": {
    "parameters": ""
  }
}
```
- **IMPORTANT GUIDELINES:**
  **1. Do **not** repeat the pattern dictionary for every row for the same factField.**
  For Example, don not do this (multiple dictionaries for timeSlotExpectedSales):
  ```json
  "conditionPatterns": [
    {
      "type": "Pattern",
      "factType": "RestaurantData",
      "boundName": "RestaurantData",
      "isNegated": false,
      "conditions": [
        {
          "typedDefaultValue": {
            "valueString": "",
            "dataType": "NUMERIC_DOUBLE",
            "isOtherwise": false
          },
          "header": "Max Time Slot Sales",
          "factField": "timeSlotExpectedSales",
          "operator": "<",
          "fieldType": "Double",
          "hidden": false,
          "width": 100,
          "parameters": "",
          "binding": ""
        },
        {
          "typedDefaultValue": {
            "valueString": "",
            "dataType": "NUMERIC_DOUBLE",
            "isOtherwise": false
          },
          "header": "Min Time Slot Sales",
          "factField": "timeSlotExpectedSales",
          "operator": ">=",
          "fieldType": "Double",
          "hidden": false,
          "width": 100,
          "parameters": "",
          "binding": ""
        }
      ],
      "window": {
        "parameters": ""
      }
    },
    {
      "type": "Pattern",
      "factType": "RestaurantData",
      "boundName": "RestaurantData",
      "isNegated": false,
      "conditions": [
        {
          "typedDefaultValue": {
            "valueString": "",
            "dataType": "NUMERIC_DOUBLE",
            "isOtherwise": false
          },
          "header": "Max Partial Sales",
          "factField": "timeSlotExpectedSales",
          "operator": "<",
          "fieldType": "Double",
          "hidden": false,
          "width": 100,
          "parameters": "",
          "binding": ""
        },
        {
          "typedDefaultValue": {
            "valueString": "",
            "dataType": "NUMERIC_DOUBLE",
            "isOtherwise": false
          },
          "header": "Min Partial Sales",
          "factField": "timeSlotExpectedSales",
          "operator": ">=",
          "fieldType": "Double",
          "hidden": false,
          "width": 100,
          "parameters": "",
          "binding": ""
        }
      ],
      "window": {
        "parameters": ""
      }
    },
    {
      "type": "Pattern",
      "factType": "RestaurantData",
      "boundName": "RestaurantData",
      "isNegated": false,
      "conditions": [
        {
          "typedDefaultValue": {
            "valueString": "",
            "dataType": "NUMERIC_DOUBLE",
            "isOtherwise": false
          },
          "header": "Max Additional Sales",
          "factField": "timeSlotExpectedSales",
          "operator": "<",
          "fieldType": "Double",
          "hidden": false,
          "width": 100,
          "parameters": "",
          "binding": ""
        },
        {
          "typedDefaultValue": {
            "valueString": "",
            "dataType": "NUMERIC_DOUBLE",
            "isOtherwise": false
          },
          "header": "Min Additional Sales",
          "factField": "timeSlotExpectedSales",
          "operator": ">=",
          "fieldType": "Double",
          "hidden": false,
          "width": 100,
          "parameters": "",
          "binding": ""
        }
      ],
      "window": {
        "parameters": ""
      }
    }
  ]
  ```
  instead do this (one dictionary for timeSlotExpectedSales):
  ```json
  "conditionPatterns": [
    {
      "type": "Pattern",
      "factType": "RestaurantData",
      "boundName": "RestaurantData",
      "isNegated": false,
      "conditions": [
        {
          "typedDefaultValue": {
            "valueString": "",
            "dataType": "NUMERIC_DOUBLE",
            "isOtherwise": false
          },
          "header": "Max Time Slot Sales",
          "factField": "timeSlotExpectedSales",
          "operator": "<",
          "fieldType": "Double",
          "hidden": false,
          "width": 100,
          "parameters": "",
          "binding": ""
        },
        {
          "typedDefaultValue": {
            "valueString": "",
            "dataType": "NUMERIC_DOUBLE",
            "isOtherwise": false
          },
          "header": "Min Time Slot Sales",
          "factField": "timeSlotExpectedSales",
          "operator": ">=",
          "fieldType": "Double",
          "hidden": false,
          "width": 100,
          "parameters": "",
          "binding": ""
        }
      ],
      "window": {
        "parameters": ""
      }
    }
  ]
  ```
  **2. Range Conditions (Two Operators)**
    - **One Pattern per field**: whenever the user gives a numeric range for the same property (e.g. expected total sales between 300 and 500), emit exactly one Pattern entry.
    - Within that Pattern: define **two** "conditions" entries:
      a. One with "operator": ">="
      b. One with "operator": "<"
    - **Do not** repeat the Pattern for each interval; intervals are driven by data rows.
    - Leave every typedDefaultValue empty (valueNumeric/valueString fields as null or empty) so that specific numbers will be filled in later by data rows.
    - Example → Range Condition for totalExpectedSales on RestaurantSales:
```json
{
  "type": "Pattern",
  "factType": "RestaurantSales",
  "boundName": "RestaurantSales",
  "isNegated": false,
  "conditions": [
    {
      "typedDefaultValue": {
        "valueNumeric": null,
        "valueString": "",
        "dataType": "NUMERIC_DOUBLE",
        "isOtherwise": false
      },
      "header": "Max Sales",
      "factField": "dailySales",
      "operator": "<",
      "fieldType": "Double",
      "hidden": false,
      "width": 100,
      "parameters": {},
      "binding": ""
    },
    {
      "typedDefaultValue": {
        "valueNumeric": null,
        "valueString": "",
        "dataType": "NUMERIC_DOUBLE",
        "isOtherwise": false
      },
      "header": "Min Sales",
      "factField": "dailySales",
      "operator": ">=",
      "fieldType": "Double",
      "hidden": false,
      "width": 100,
      "parameters": {},
      "binding": ""
    }
  ],
  "window": {
    "parameters": {}
  }
}
```
    - In this JSON, there is one Pattern for “dailySales” with two conditions (>= and <), and both valueNumeric fields are left null/empty. Do not create separate Patterns for “0–100,” “100–200,” etc.
  3. Single‐Operator Conditions (Equality or Other Single Operators)
    - Rule: Whenever a user describes a condition with exactly one operator (e.g. “restaurantSize == X,” “employeeCount > Y,” “status != ‘Closed’”), you must emit exactly one Pattern object containing a single "conditions" entry.
    - Leave its typedDefaultValue empty so that each data row can fill in the actual value (e.g. “S,” “M,” “L,” or any other literal).
    - Do not repeat this Pattern for every distinct literal; keep it generic with an empty value placeholder.
    - Example → Equality Condition for restaurantSize on RestaurantData:
```json
{
  "type": "Pattern",
  "factType": "RestaurantData",
  "boundName": "RestaurantData",
  "isNegated": false,
  "conditions": [
    {
      "header": "Size",
      "factField": "restaurantSize",
      "operator": "==",
      "fieldType": "String",
      "hidden": false,
      "width": 100,
      "parameters": {},
      "binding": "",
      "typedDefaultValue": {
        "valueString": "",
        "dataType": "STRING",
        "isOtherwise": false
      }
    }
  ],
  "window": {
    "parameters": {}
  }
}
```
    - Here, there is one Pattern for “restaurantSize == …” with valueString left empty. Do not output separate Patterns for “== S,” “== M,” “== L.” Each row’s data will supply "valueString": "S" or "M" or "L" later.
    
- **Field Explanations:**
  - `type`: Always hard-code "type": "Pattern" for any fact-field constraint.
  - `factType` and `boundName`: Use the name of the Java class whose fields you are constraining. Typically both are the same.
  - `isNegated`: Leave as false unless the user explicitly asks "negate this pattern."
  - `conditions`: Each element corresponds to one condition-column52 in the guided decision table.
  - `typedDefaultValue`: ALWAYS include this object with all its fields for EVERY condition:
    - valueString: Always include this tag. If the user did not supply a default, set it to "".
    - valueNumeric: Include this object only if the fieldType is numeric, with appropriate class and value, otherwise omit.
    - valueBoolean: Include this only if the fieldType is Boolean, otherwise omit.
    - dataType: Must be one of "NUMERIC_INTEGER", "NUMERIC_DOUBLE", "STRING", or "BOOLEAN" matching the Java field's type.
    - isOtherwise: Always set to false unless the user specifically asks for an otherwise clause.
  - `header`: The visible column header label (e.g. "Min Sales" or "Max Sales").
  - `constraintValueType`: Always 1 for a simple field-comparison column.
  - `factField`: The exact Java-bean property name you are comparing against.
  - `operator`: One of '&lt;=', '&gt;=', '&lt;', '&gt;', or '=='.
  - `fieldType`: Must match the Java type of that factField (e.g., "Double", "Integer", "String", "Boolean").
  - `hidden`, `width`, `parameters`, `binding`: Usually set to false, 100, "", and "" respectively unless specified otherwise.
  - `window`: Always "window": { "parameters": "" } unless the user specifically asks for a sliding window or timed window.

"""
    
    def _create_brl_action_prompt(self) -> str:
        """
        Create the prompt section for BRL actions.
        
        Returns:
            str: Prompt section for BRL actions
        """
        return """**4. BRLActionColumn:**
```json
{
  "actionColumns": [
    {
      "type": "BRLAction",
      "width": 100,
      "header": "<column header text describing action or property, e.g. \"Employee Count\">",
      "hidden": false,
      "definition": [
        {"text": "<the DRL/Java snippet to invoke on your recommendation object—always include \"@{varName}\" for the argument. For example: \"recommendation.addRestaurantEmployees(@{count})\". >"}
      ],
      "childColumns": {
        "BRLActionVariableColumn": {
          "typedDefaultValue": {
            "valueString": "<if your method takes a String and you want a default, put it here; otherwise \"\">",
            "valueNumeric": {
              "class": "<\"int\" or \"double\" depending on your Java-bean method's parameter type>",
              "value": "<numeric default literal if any, e.g. 0 or 0.0, or omit this entire object if none>"
            },
            "valueBoolean": "<true or false only if your method's parameter type is Boolean and you want a default; otherwise omit>",
            "dataType": "<the Drools dataType matching the argument: \"NUMERIC_INTEGER\" if your method expects an int, \"NUMERIC_DOUBLE\" if double, \"STRING\" if String, or \"BOOLEAN\" if Boolean>",
            "isOtherwise": false
          },
          "hidden": false,
          "width": 100,
          "header": "<any visible header, e.g. \"Restaurant Employees\" or \"Delivery Employees\">",
          "varName": "<this must exactly match the token you used inside definition's \"@{…}\". For example, if your definition text is \"recommendation.addRestaurantEmployees(@{count})\", then varName must be \"count\">",
          "fieldType": "<the Java type of the argument: \"Integer\", \"Double\", \"String\", or \"Boolean\">"
        }
      }
    }
  ]
}
```
- **IMPORTANT GUIDELINES**
  - **One BRLAction per method**: 
    - For each RestaurantRecommendation Java-bean action method (e.g. `addRestaurantEmployees` or `setRestaurantEmployees`), emit exactly one entry under `"actionColumns"`.
    - **Never** repeat that actionColumns entry for each data row.
    - Do not replicate the same <definition> + <childColumns> block for every row; define it once under "actionColumns" and then supply each row’s argument in "data.values".
  - **BRLAction Columns** must **never** contain conditional or branching logic.
  – Do **not** repeat or inline any `if(...)` statements inside `actionColumns.definition`.
  - **How to choose the correct method**:
    Based on the provided user intent, determine which method to use from the Java-bean Employee Recommendation methods:
      > e.g.If the user says "add extra" employees, use the `addRestaurantExtraEmployees` method.
      > e.g. If the user says "add" employees, use the `addRestaurantEmployees` method.
      > e.g. If the user says "set" employees, use the `setRestaurantEmployees` method.
      > e.g. If the user says "set" extra employees, use the `setRestaurantExtraEmployees` method.
      > e.g. If the user says "set" home delivery employees, use the `setHomeDeliveryEmployees` method.
- **Field Explanations:**
  - `type`: Always set "type": "BRLAction" when defining a Free-Form action on a DRL fact via a Java-bean method call.
  - `width`: The column's width in the guided decision table. Use 100 by default.
  - `header`: The visible label for this action column.
  - `hidden`: Use false unless the user explicitly wants to hide this column.
  - `definition.text`: Must contain exactly the DRL/Java snippet you want to execute, with "@{varName}" for the argument.
  - `childColumns.BRLActionVariableColumn`: This defines the column that holds the value to plug into @{...}.
  - `typedDefaultValue`: ALWAYS include this object with all its fields for EVERY action:
    - valueString: Always include this tag. If the argument type is String and you want a default, put it here. Otherwise set to "".
    - valueNumeric: Include this object if your Java-bean method takes an int or double.
    - valueBoolean: Include this if your method's parameter is a Boolean and you want a default. Otherwise omit.
    - dataType: Exactly the Drools type that corresponds to your method argument.
    - isOtherwise: Always set to false unless the user specifically asked for an otherwise row.
  - `varName`: Must be exactly the name you used inside definition.text (@{varName}).
  - `fieldType`: Exactly the Java type of the method's single parameter.

**Examples for different data types:**

**Integer Example:**
```json
{
  "actionColumns": [
    {
      "type": "BRLAction",
      "width": 100,
      "header": "Employee Count",
      "hidden": false,
      "definition": [
        {"text": "recommendation.addRestaurantEmployees(@{count})"}
      ],
      "childColumns": {
        "BRLActionVariableColumn": {
          "typedDefaultValue": {
            "valueString": "",
            "valueNumeric": {
              "class": "int",
              "value": 0
            },
            "dataType": "NUMERIC_INTEGER",
            "isOtherwise": false
          },
          "hidden": false,
          "width": 100,
          "header": "Restaurant Employees",
          "varName": "count",
          "fieldType": "Integer"
        }
      }
    }
  ]
}
```

**String Example:**
```json
{
  "actionColumns": [
    {
      "type": "BRLAction",
      "width": 100,
      "header": "Description",
      "hidden": false,
      "definition": [
        {"text": "recommendation.setDescription(@{desc})"}
      ],
      "childColumns": {
        "BRLActionVariableColumn": {
          "typedDefaultValue": {
            "valueString": "",
            "dataType": "STRING",
            "isOtherwise": false
          },
          "hidden": false,
          "width": 100,
          "header": "Description",
          "varName": "desc",
          "fieldType": "String"
        }
      }
    }
  ]
}
```

**Boolean Example:**
```json
{
  "actionColumns": [
    {
      "type": "BRLAction",
      "width": 100,
      "header": "Enable Promotion",
      "hidden": false,
      "definition": [
        {"text": "recommendation.enablePromo(@{flag})"}
      ],
      "childColumns": {
        "BRLActionVariableColumn": {
          "typedDefaultValue": {
            "valueBoolean": false,
            "valueString": "",
            "dataType": "BOOLEAN",
            "isOtherwise": false
          },
          "hidden": false,
          "width": 100,
          "header": "Enable Promotion",
          "varName": "flag",
          "fieldType": "Boolean"
        }
      }
    }
  ]
}
```
// ❌ WRONG: DO NOT DO THIS
"actionColumns": [
  {
    "type":"BRLAction",
    "definition":[
      { "text":
        "if (…small…) { recommendation.setRestaurantEmployees(5); } else if (…) { … }"
      }
    ],
    …
  }
]

// ✅ RIGHT: single method invocation only
"actionColumns": [
  {
    "type":"BRLAction",
    "width":100,
    "header":"Assign Base Employees",
    "definition":[
      { "text":"recommendation.addRestaurantEmployees(@{count})" }
    ],
    "childColumns":{
      "BRLActionVariableColumn":{
        "typedDefaultValue":{
          "valueNumeric":{ "class":"int","value":0 },
          "valueString":"",
          "dataType":"NUMERIC_INTEGER",
          "isOtherwise":false
        },
        "header":"Base Employees Count",
        "varName":"count",
        "fieldType":"Integer",
        "hidden":false,
        "width":100
      }
    }
  }
]

**Key takeaways:**
- The top-level must read "type": "BRLAction".
- definition.text is the exact Java/Drl call. Use @{varName} inside parentheses.
- The child column must be "BRLActionVariableColumn" with typedDefaultValue and the proper Drools dataType.
- varName must match exactly the name inside @{...}.
- fieldType must match the Java method's single parameter type.
- Include valueNumeric with appropriate class for numeric types, valueString for strings, and valueBoolean for booleans.
- Always include "dataType" exactly as "NUMERIC_INTEGER", "NUMERIC_DOUBLE", "STRING", or "BOOLEAN".

"""
    
    def _create_data_list_prompt(self) -> str:
        """
        Create the prompt section for data lists.
        
        Returns:
            str: Prompt section for data lists
        """
        return """**5. Data List:**
Produce a "data" array where each element represents one decision-table row. Each row object must contain:
1. "rowNumber" (an integer),
2. "description" (a human-readable string for that row), and
3. "values" (an ordered list of column-value objects).

Important: Within "values", preserve this exact sequence for every row:
1. salience column
2. recommendation binding (the BRLConditionVariableColumn that binds EmployeeRecommendation)
3. restaurantData binding (the BRLConditionVariableColumn that binds RestaurantData)
4. pattern-based conditions (one entry per condition-column52 under your Pattern52, in the same order they appear in your table)
5. complex BRLCondition expressions (if any—i.e. any FreeFormLine/EVAL statements)
6. action variables (one entry per BRLActionVariableColumn, in the same order they appear under actionCols)

Below is a template for a single row. Copy this structure exactly and fill in each "columnName", "value", and "dataType" according to the user's rule:
```json
{
  "data": [
    {
      "rowNumber": "<integer – the row's index, e.g. 1, 2, 3...>",
      "description": "<string – human-readable description of this rule row>",
      "values": [
        // 1) salience
        {
          "columnName": "salience",
          "value": "<int, e.g. 100>",
          "dataType": "NUMERIC_INTEGER"
        },

        // 2) recommendation binding (BRLConditionVariableColumn for EmployeeRecommendation)
        {
          "columnName": "recommendation",
          "value": "<boolean, usually true if this rule applies>",
          "dataType": "BOOLEAN"
        },

        // 3) restaurantData binding (BRLConditionVariableColumn for RestaurantData)
        {
          "columnName": "restaurantData",
          "value": "<boolean, usually true>",
          "dataType": "BOOLEAN"
        },

        // 4) Pattern52 conditions, in the same order as defined under conditionPatterns
        //    Example: if your Pattern52 has two condition columns "Max Sales" and "Min Sales":
        {
          "columnName": "Max Sales",
          "value": "<number or empty>",
          "dataType": "NUMERIC_DOUBLE"
        },
        {
          "columnName": "Min Sales",
          "value": "<number or empty>",
          "dataType": "NUMERIC_DOUBLE"
        },

        // 5) Any complex BRLCondition expressions (FreeFormLine/EVAL). If none, omit this block.
        //    Example: for an even-check on dailySales:
        {
          "columnName": "evenDailySalesCheck",
          "value": "<boolean, true or false>",
          "dataType": "BOOLEAN"
        },

        // 6) BRLActionVariableColumn values, in the same order as under actionCols
        {
          "columnName": "count",
          "value": "<integer, e.g. 2>",
          "dataType": "NUMERIC_INTEGER"
        }
      ]
    }
    // ...repeat one object per row...
  ]
}
```

**Field-by-Field Guidance:**
1. "rowNumber": Set to the sequential row index (1, 2, 3, ...).
2. "description": A short label for humans (e.g. "0–100 sales").
3. "values" (array must follow exactly this order):
   - salience: "columnName": "salience", "value": an integer (e.g. 100), "dataType": "NUMERIC_INTEGER"
   - recommendation binding: "columnName": "recommendation", "value": true/false (in practice, always true if you want that rule to fire), "dataType": "BOOLEAN"
   - restaurantData binding: "columnName": "restaurantData", "value": true/false (usually true), "dataType": "BOOLEAN"
   - pattern-based conditions: One object per Pattern52 condition-column52, in the order they were defined. 'columnName' should be exactly the same as the "header" in the condition-column52.
   - complex BRLCondition expressions: Include if the row uses a FreeFormLine/EVAL clause
   - action variable values: One object per BRLActionVariableColumn, in the same order

**Example Filling:**
Suppose you have a rule table where:
- salience = 10
- BRLConditionVariableColumn "recommendation" → always true
- BRLConditionVariableColumn "restaurantData" → always true
- Pattern52 has condition-column52 "Max Sales (≤100.0)" and "Min Sales (>0.0)"
- No additional FreeFormLine/EVAL
- One action "count" (Integer) = 2

Then one row's JSON entry becomes:
```json
{
  "rowNumber": 1,
  "description": "0–100 sales",
  "values": [
    {
      "columnName": "salience",
      "value": 10,
      "dataType": "NUMERIC_INTEGER"
    },
    {
      "columnName": "recommendation",
      "value": true,
      "dataType": "BOOLEAN"
    },
    {
      "columnName": "restaurantData",
      "value": true,
      "dataType": "BOOLEAN"
    },
    {
      "columnName": "Max Sales",
      "value": 100.0,
      "dataType": "NUMERIC_DOUBLE"
    },
    {
      "columnName": "Min Sales",
      "value": 0.0,
      "dataType": "NUMERIC_DOUBLE"
    },
    {
      "columnName": "count",
      "value": 2,
      "dataType": "NUMERIC_INTEGER"
    }
  ]
}
```

If you do have a FreeFormLine/EVAL for "even dailySales," insert it just before the "count" block:
```json
{
  "rowNumber": 2,
  "description": "Even-check on dailySales",
  "values": [
    {
      "columnName": "salience",
      "value": 20,
      "dataType": "NUMERIC_INTEGER"
    },
    {
      "columnName": "recommendation",
      "value": true,
      "dataType": "BOOLEAN"
    },
    {
      "columnName": "restaurantData",
      "value": true,
      "dataType": "BOOLEAN"
    },
    {
      "columnName": "Max Sales",
      "value": 200.0,
      "dataType": "NUMERIC_DOUBLE"
    },
    {
      "columnName": "Min Sales",
      "value": 100.0,
      "dataType": "NUMERIC_DOUBLE"
    },
    {
      "columnName": "evenDailySalesCheck",
      "value": true,
      "dataType": "BOOLEAN"
    },
    {
      "columnName": "count",
      "value": 4,
      "dataType": "NUMERIC_INTEGER"
    }
  ]
}
```

"""
    
    def _create_guidelines_prompt(self) -> str:
        """
        Create the prompt section for general guidelines.
        
        Returns:
            str: Prompt section for general guidelines
        """
        return """**IMPORTANT GUIDELINES:**
1. Extract ONLY the dynamic elements mentioned in the user's description such as conditions, actions, salience, and rule name (if provided). 
2. For any fields not explicitly mentioned from user input, use the default provided as described in above JSON schema.
3. For each range mentioned, create a corresponding data row with the appropriate values.

4. ALWAYS include the following in your JSON output:
   - Two BRLCondition entries: one for EmployeeRecommendation and one for RestaurantData.
   - Include typedDefaultValue for all columns with appropriate default values.
   - For salience attribute, always include reverseOrder=false and useRowNumber=false.

5. CRITICAL SCHEMA REQUIREMENTS:
   - All BRLCondition entries MUST be placed in the "conditionsBRL" array, NOT in "conditionPatterns".
   - Pattern entries MUST be placed in the "conditionPatterns" array.
   - EVERY condition and action column MUST include a "typedDefaultValue" object with appropriate fields.
   
6. WHEN TO USE CONDITION PATTERNS VS BRL CONDITIONS:
   - **conditionPatterns** holds every simple field‐comparison:
     • Single‐operator tests (==, !=, >, <, ≥, ≤).  
     • Ranges (≥ lower AND < upper) — exactly one Pattern object with two columns.  
     • **Do not** wrap these in `eval(...)` or in BRLCondition.
   - **conditionsBRL** is reserved only for:
     > Fact‐instantiations (`recommendation : EmployeeRecommendation()`, `restaurantData : RestaurantData()`).
     > Complex expressions (e.g. arithmetic, custom utility calls, Java `LocalTime` comparisons or parsing e.g. LocalTime.parse()) requiring `eval(...)`.

   - Example on using **conditionPatterns** for any simple field checks:
     ```json
    "conditionPatterns": [
    {
      "type": "Pattern",
      "factType": "RestaurantData",
      "boundName": "RestaurantData",
      "isNegated": false,
      "conditions": [
        {
          "typedDefaultValue": {
            "valueString": "",
            "dataType": "STRING",
            "isOtherwise": false
          },
          "header": "Size",
          "factField": "restaurantSize",
          "operator": "==",
          "fieldType": "String",
          "hidden": false,
          "width": 100,
          "parameters": "",
          "binding": ""
        }
      ],
      "window": {
        "parameters": ""
      }
    }
  ]
     ```
     *Data rows then supply “small”, “medium”, “large” under that one Pattern.*

   - example on using **conditionPatterns** for numeric ranges, *Only one Pattern, two condition‐columns*:
     ```jsonc
    "conditionPatterns": [
    {
      "type": "Pattern",
      "factType": "RestaurantData",
      "boundName": "RestaurantData",
      "isNegated": false,
      "conditions": [
        {
          "typedDefaultValue": {
            "valueString": "",
            "valueNumeric": null,
            "valueBoolean": null,
            "dataType": "NUMERIC_DOUBLE",
            "isOtherwise": false
          },
          "header": "Max Sales",
          "factField": "totalExpectedSales",
          "operator": "<",
          "fieldType": "Double",
          "hidden": false,
          "width": 100,
          "parameters": "",
          "binding": ""
        },
        {
          "typedDefaultValue": {
            "valueString": "",
            "valueNumeric": null,
            "valueBoolean": null,
            "dataType": "NUMERIC_DOUBLE",
            "isOtherwise": false
          },
          "header": "Min Sales",
          "factField": "totalExpectedSales",
          "operator": ">=",
          "fieldType": "Double",
          "hidden": false,
          "width": 100,
          "parameters": "",
          "binding": ""
        }
      ],
      "window": {
        "parameters": ""
      }
    }
  ]
     ```

  - example on using bindings in **conditionsBRL** and `eval(...)` for complex arithmetic operations:
   ```json eval example 
   {
      "type": "BRLCondition",
      "width": -1,
      "header": "Even Daily Sales",
      "hidden": false,
      "constraintValueType": 1,
      "parameters": "",
      "definition": [
        {"text": "eval(restaurantData.getDailySales() % 2 == 0)"}
      ],
      "childColumns": {
        "BRLConditionVariableColumn": {
          "typedDefaultValue": {
            "valueBoolean": true,
            "valueString": "",
            "dataType": "BOOLEAN",
            "isOtherwise": false
          },
          "hideColumn": false,
          "width": 100,
          "header": "Even Daily Sales",
          "constraintValueType": 1,
          "fieldType": "Boolean",
          "parameters": "",
          "varName": "evenDailySalesCheck"
        }
      }
    }
   ```
   ```json eval example for LocalTime parsing:
   {
      "type": "BRLCondition",
      "width": -1,
      "header": "Time of Day Check",
      "hidden": false,
      "constraintValueType": 1,
      "parameters": "",
      "definition": [
        {"text": "eval(restaurantData.getCalculationDateTime().toLocalTime() >= LocalTime.parse(\"@{targetTime}\"))"}
      ],
      "childColumns": {
        "BRLConditionVariableColumn": {
          "typedDefaultValue": {
            "valueBoolean": true,
            "valueString": "",
            "dataType": "BOOLEAN",
            "isOtherwise": false
          },
          "hideColumn": false,
          "width": 100,
          "header": "Time of Day Check",
          "constraintValueType": 1,
          "fieldType": "Boolean",
          "parameters": "",
          "varName": "targetTime"
        }
      }
    }
   ```

7. Return ONLY the JSON object, nothing else.

"""
    
    def _create_java_classes_prompt(self, java_classes_map: Dict[str, Dict]) -> str:
        """
        Create the prompt section for Java classes.
        
        Args:
            java_classes_map (dict): Dictionary mapping class names to package, class name, and methods
            
        Returns:
            str: Prompt section for Java classes
        """
        java_classes_prompt = "\n\n**Java Class Information:**\n"
        java_classes_prompt += "You have access to the following Java class definitions:\n"
        
        for class_name, class_info in java_classes_map.items():
            package = class_info.get("package", "")
            methods = class_info.get("methods", [])
            fields = class_info.get("fields", [])
            
            java_classes_prompt += f"\nClass: {class_name}\n"
            java_classes_prompt += f"Package: {package}\n"
            
            if fields:
                java_classes_prompt += "Fields:\n"
                for field in fields:
                    java_classes_prompt += f"- {field}\n"
            
            if methods:
                java_classes_prompt += "Methods:\n"
                for method in methods:
                    java_classes_prompt += f"- {method}\n"
        
        java_classes_prompt += "\n**IMPORTANT INSTRUCTIONS FOR JAVA CLASSES:**\n"
        java_classes_prompt += "1. Use the correct package names for imports based on the Java class definitions\n"
        java_classes_prompt += "2. When writing actions, select the appropriate method based on the user's intent:\n"
        java_classes_prompt += "   - For 'add' operations, use methods starting with 'add'\n"
        java_classes_prompt += "   - For 'set' operations, use methods starting with 'set'\n"
        java_classes_prompt += "   - Match the method signature with the appropriate parameters\n"
        
        return java_classes_prompt