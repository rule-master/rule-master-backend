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
        java_classes_map = self.java_classes_map
        system_content = """
        You are a Drools rule assistant that helps users create, search, edit, and delete Drools rules in a natural, conversational way. 
        
        Analyze user requests carefully to determine their intent. Based on the intent, call the appropriate function: 
        
        - When users want to add or create a rule, call the add_rule function.
        - When users want to modify, update, edit, or change a rule, call the edit_rule function.
        - When users want to delete or remove a rule, call the delete_rule function.
        - When users want to search, find, or list rules, call the search_rules function.
        
        When user wants to add a new rule:
        - Mapping user language to facts, fields, and actions: 
            > Facts are the objects you are reasoning about, like 'restaurant data' or 'employee recommendation'.
            > Fields are the attributes of those facts, like 'restaurant size' or 'expected total sales'.
            > Actions are what you want to do with the facts, like 'add employees' or 'set extra employees'.
        - Before you transform their request, identify each condition and action in plain English, then map it to the exact Java-bean property or method.
        - If you’re not certain which field or method to use (for example, “sales” could mean `totalExpectedSales` or `timeSlotExpectedSales`), politely ask for clarification:
        > “Just to confirm, when you say ‘sales’, do you mean the restaurant’s **total expected sales** or the **time slot expected sales**?”
        - Likewise for actions: for example, if the user says assign, add, or set 6 employees” and EmployeeRecommendation class has different methods like `addRestaurantEmployees`, `addRestaurantExtraEmployees`, `setRestaurantEmployees`, and `setRestaurantExtraEmployees`, and you are not certain which method to use, ask:  
        > “Would you like to use **add restaurant employees** or **add restaurant extra employees**, or should we **set the employees count instead**?”
        - you must capture rule's salience/priority. If the user does not provide a salience, you should ask for it.
        > e.g. “Just to confirm, what priority should I assign to this rule? The higher the number, the higher the priority. For example, if you want this rule to be executed before others, you can assign a higher number like 100. If you want it to be executed after others, you can assign a lower number like 1. If you don't have a specific priority in mind, I can assign a default priority of 50.”
        - If you captured all the necessary information (even from 1st user input or first followup), don't clarify anything else or ask for user confirmation to call the function, just call it.
        - Send final refined user intent in natural language to the add function not in JSON format.
        
        Call the appropriate function once you have all the necessary information. 
        
        When clarifying user input or requesting additional information, use the following phrases: "do you mean", "which", "could you", "please clarify", "which one", "Just to confirm".
        
        Always respond in a helpful, conversational manner. 
        
        """
        java_classes_prompt = "\n**Java Class Information:**\n"
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
        
        system_content += java_classes_prompt
        self.messages.append({"role": "system", "content": system_content})
    
    def _load_java_classes(self):
        """
        Load Java classes and their package, class name, and methods.
        
        Returns:
            dict: Dictionary mapping class names to package, class name, and methods
        """
        try:
            # Import the map_java_classes function
            from utils.parse_java_classes import parse_java_classes
            return parse_java_classes(self.java_dir)
        except ImportError:
            # If the module is not available, return default mapping
            return {
                "RestaurantData": "com.myspace.resopsrecomms",
                "EmployeeRecommendation": "com.myspace.resopsrecomms"
            }
    
    def handle_user_message(self, user_input):
        """
        Handle a user message and return a response.
        
        Args:
            user_input (str): User message
            
        Returns:
            str: Agent response
        """
        print(">> RAW USER INPUT:", user_input)
        # Add user message to conversation
        self.messages.append({"role": "user", "content": user_input})
        
        # Define available functions
        functions = self._get_function_definitions()
        
        try:
            
            while True:
                
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
                    print(f">> ASSISTANT WANTS TO CALL: {message.function_call.name}")
                    print(">> WITH ARGUMENTS:", message.function_call.arguments)
                    
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
                    
                    # now ask the LLM *once more* to turn that function output into a natural reply
                    followup = self.client.chat.completions.create(
                        model=self.model,
                        messages=self.messages
                    )
                    
                    reply = followup.choices[0].message.content
                    self.messages.append({"role": "assistant", "content": reply})
                    return reply
                reply = message.content or ""
                if any(phrase in reply.lower() for phrase in (
            "do you mean", "which", "could you", "please clarify", "which one", "Just to confirm"
                )):
                    # pass the question straight back to the user
                    self.messages.append({"role": "assistant", "content": reply})
                    return reply
                # If no function call, return the message content
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
