"""
Updated DroolsLLMAgent with NL-to-JSON-to-Drools pipeline for add operation.

This module provides the DroolsLLMAgent class that leverages the language model
for intent detection and tool orchestration through function calling.
"""

import os
import json
from openai import OpenAI

class DroolsLLMAgent:
    """
    LLM-centric agent for handling natural language interactions to manage Drools rules.
    """
    
    def __init__(self, api_key, model="gpt-4o-mini", rules_dir=None, java_dir=None):
        """
        Initialize the Drools LLM Agent.
        
        Args:
            api_key (str): OpenAI API key
            model (str): OpenAI model to use
            rules_dir (str): Directory to store rules
            java_dir (str): Directory containing Java class files
        """
        # Set up OpenAI client
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.api_key = api_key
        
        # Set up directories
        self.rules_dir = rules_dir or os.path.join(os.getcwd(), "rules")
        self.deleted_rules_dir = os.path.join(self.rules_dir, "deleted_rules")
        
        # Create directories if they don't exist
        os.makedirs(self.rules_dir, exist_ok=True)
        os.makedirs(self.deleted_rules_dir, exist_ok=True)
        
        # Set up Java class mapping
        self.java_dir = java_dir or os.getenv("JAVA_DIR", "")
        self.java_classes_map = self._load_java_classes()
        
        # Set up conversation history
        self.messages = []
        
        # Set up system prompt
        self._setup_system_prompt()
    
    def _setup_system_prompt(self):
        """
        Set up the system prompt for the LLM.
        """
        system_content = """
        You are a Drools rule assistant that helps users create, search, edit, and delete Drools rules.
        
        Analyze user requests carefully to determine their intent. Based on the intent, call the appropriate function:
        
        - When users want to create a rule, call the add_rule function
        - When users want to modify a rule, call the edit_rule function
        - When users want to delete a rule, call the delete_rule function
        - When users want to find or list rules, call the search_rules function
        
        For rule creation, determine whether to create a DRL file or GDST file based on the complexity:
        - Use DRL for simple rules with a few conditions and actions
        - Use GDST for rules with multiple similar conditions or actions, especially those involving ranges or thresholds
        
        Always respond in a helpful, conversational manner.
        """
        self.messages.append({"role": "system", "content": system_content})
    
    def _load_java_classes(self):
        """
        Load Java classes and their package names.
        
        Returns:
            dict: Dictionary mapping class names to package names
        """
        try:
            # Import the map_java_classes function
            from utils.java_class_mapper import map_java_classes
            
            if not self.java_dir or not os.path.exists(self.java_dir):
                # Default mapping if Java directory not available
                return {
                    "RestaurantData": "com.capstonespace.resopsrecomms",
                    "EmployeeRecommendation": "com.capstonespace.resopsrecomms"
                }
            
            return map_java_classes(self.java_dir)
        except ImportError:
            # If the module is not available, return default mapping
            return {
                "RestaurantData": "com.capstonespace.resopsrecomms",
                "EmployeeRecommendation": "com.capstonespace.resopsrecomms"
            }
    
    def handle_user_message(self, user_input):
        """
        Handle a user message and return a response.
        
        Args:
            user_input (str): User message
            
        Returns:
            str: Agent response
        """
        # Add user message to conversation
        self.messages.append({"role": "user", "content": user_input})
        
        # Define available functions
        functions = self._get_function_definitions()
        
        try:
            # Call OpenAI with function definitions
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                functions=functions,
                function_call="auto"
            )
            
            # Extract the message
            message = response.choices[0].message
            
            # Handle function calls if present
            if message.function_call:
                function_response = self._handle_function_call(message.function_call)
                
                # Add function call and response to conversation
                self.messages.append({
                    "role": "assistant", 
                    "content": None, 
                    "function_call": {
                        "name": message.function_call.name,
                        "arguments": message.function_call.arguments
                    }
                })
                self.messages.append({
                    "role": "function", 
                    "name": message.function_call.name, 
                    "content": json.dumps(function_response)
                })
                
                # Get final response from LLM
                followup = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages
                )
                
                reply = followup.choices[0].message.content
                self.messages.append({"role": "assistant", "content": reply})
                return reply
            
            # If no function call, return the message content
            reply = message.content
            self.messages.append({"role": "assistant", "content": reply})
            return reply
            
        except Exception as e:
            error_message = f"Error processing message: {str(e)}"
            self.messages.append({"role": "assistant", "content": error_message})
            return error_message
    
    def _handle_function_call(self, function_call):
        """
        Handle a function call from the LLM.
        
        Args:
            function_call: Function call object from OpenAI
            
        Returns:
            dict: Function response
        """
        try:
            # Extract function name and arguments
            name = function_call.name
            args = json.loads(function_call.arguments)
            
            # Call the appropriate function
            if name == "add_rule":
                return self._add_rule(args)
            elif name == "edit_rule":
                return self._edit_rule(args)
            elif name == "delete_rule":
                return self._delete_rule(args)
            elif name == "search_rules":
                return self._search_rules(args)
            else:
                return {"success": False, "message": f"Unknown function: {name}"}
        except Exception as e:
            return {"success": False, "message": f"Error handling function call: {str(e)}"}
    
    def _get_function_definitions(self):
        """
        Get the function definitions for the LLM.
        
        Returns:
            list: List of function definitions
        """
        return [
            {
                "name": "add_rule",
                "description": "Create a new Drools rule from natural language description",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Natural language description of the rule"
                        }
                    },
                    "required": ["description"]
                }
            },
            {
                "name": "edit_rule",
                "description": "Modify an existing Drools rule",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "rule_name": {
                            "type": "string",
                            "description": "Name of the rule to edit"
                        },
                        "changes": {
                            "type": "string",
                            "description": "Natural language description of the changes to make"
                        }
                    },
                    "required": ["rule_name", "changes"]
                }
            },
            {
                "name": "delete_rule",
                "description": "Delete an existing Drools rule",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "rule_name": {
                            "type": "string",
                            "description": "Name of the rule to delete"
                        }
                    },
                    "required": ["rule_name"]
                }
            },
            {
                "name": "search_rules",
                "description": "Search for Drools rules",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (rule name, content, etc.)"
                        }
                    },
                    "required": ["query"]
                }
            }
        ]
    
    def _add_rule(self, args):
        """
        Add a new rule.
        
        Args:
            args (dict): Function arguments
            
        Returns:
            dict: Function response
        """
        try:
            # Import the add_rule function
            from tools.add_tool import add_rule
            
            # Call the add_rule function
            result = add_rule(
                user_input=args["description"],
                java_classes_map=self.java_classes_map,
                rules_dir=self.rules_dir,
                api_key=self.api_key
            )
            
            return result
        except Exception as e:
            return {
                "success": False,
                "message": f"Error creating rule: {str(e)}"
            }
    
    def _edit_rule(self, args):
        """
        Edit an existing rule.
        
        Args:
            args (dict): Function arguments
            
        Returns:
            dict: Function response
        """
        # This is a placeholder for the edit functionality
        return {
            "success": False,
            "message": "Edit functionality is not yet implemented."
        }
    
    def _delete_rule(self, args):
        """
        Delete an existing rule.
        
        Args:
            args (dict): Function arguments
            
        Returns:
            dict: Function response
        """
        # This is a placeholder for the delete functionality
        return {
            "success": False,
            "message": "Delete functionality is not yet implemented."
        }
    
    def _search_rules(self, args):
        """
        Search for rules.
        
        Args:
            args (dict): Function arguments
            
        Returns:
            dict: Function response
        """
        # This is a placeholder for the search functionality
        return {
            "success": False,
            "message": "Search functionality is not yet implemented."
        }
