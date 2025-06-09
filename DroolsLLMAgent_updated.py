"""
Updated DroolsLLMAgent with NL-to-JSON-to-Drools pipeline for add operation.

This module provides the DroolsLLMAgent class that leverages the language model
for intent detection and tool orchestration through function calling.
"""

import os
import json
from openai import OpenAI
from logger_utils import logger, log_operation, log_decorator


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
        try:
            log_operation(
                "agent_initialization",
                {
                    "model": model,
                    "rules_dir": rules_dir,
                    "java_dir": java_dir,
                },
            )

            # Set up OpenAI client
            self.client = OpenAI(api_key=api_key)
            self.model = model
            self.api_key = api_key
            logger.debug("OpenAI client initialized")

            # Set up directories
            self.rules_dir = rules_dir or os.path.join(os.getcwd(), "rules")
            self.deleted_rules_dir = os.path.join(self.rules_dir, "deleted_rules")
            logger.debug(f"Rules directory: {self.rules_dir}")

            # Create directories if they don't exist
            os.makedirs(self.rules_dir, exist_ok=True)
            os.makedirs(self.deleted_rules_dir, exist_ok=True)

            # Set up Java class mapping
            self.java_dir = java_dir or os.getenv("JAVA_DIR", "")
            self.java_classes_map = self._load_java_classes()
            logger.debug(f"Java classes mapped: {list(self.java_classes_map.keys())}")

            # Set up conversation history
            self.messages = []

            # Set up system prompt
            self._setup_system_prompt()

            # Ensure rules are indexed
            # from tools.search_tool import ensure_rules_indexed
            # if not ensure_rules_indexed(self.rules_dir, api_key):
            #     logger.warning("Failed to index rules during initialization")

            logger.info("DroolsLLMAgent initialization completed")
        except Exception as e:
            log_operation("agent_initialization", error=e)
            raise

    def _setup_system_prompt(self):
        """
        Set up the system prompt for the LLM.
        """
        logger.debug("Setting up system prompt")
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
        logger.debug("System prompt added to messages")

    def _load_java_classes(self):
        """
        Load Java classes and their package names.

        Returns:
            dict: Dictionary mapping class names to package names
        """
        try:
            # Import the map_java_classes function
            from utils.parse_java_classes import parse_java_classes

            if not self.java_dir or not os.path.exists(self.java_dir):
                # Default mapping if Java directory not available
                return {
                    "RestaurantData": "com.capstonespace.resopsrecomms",
                    "EmployeeRecommendation": "com.capstonespace.resopsrecomms",
                }

            return parse_java_classes(self.java_dir)
        except ImportError:
            # If the module is not available, return default mapping
            return {
                "RestaurantData": "com.capstonespace.resopsrecomms",
                "EmployeeRecommendation": "com.capstonespace.resopsrecomms",
            }

    @log_decorator("handle_message")
    def handle_user_message(self, user_input):
        """
        Handle a user message and return a response.

        Args:
            user_input (str): User message

        Returns:
            str: Agent response
        """
        try:
            # Add user message to conversation
            self.messages.append({"role": "user", "content": user_input})
            logger.debug("User message added to conversation history")

            # Define available functions
            functions = self._get_function_definitions()
            logger.debug(f"Available functions: {[f['name'] for f in functions]}")

            # Call OpenAI with function definitions
            logger.debug("Calling OpenAI API for completion")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                functions=functions,
                function_call="auto",
            )
            logger.debug("Received response from OpenAI")

            # Extract the message
            message = response.choices[0].message
            logger.debug(f"Message role: {message.role}")

            # Handle function calls if present
            if message.function_call:
                logger.info(f"Function call detected: {message.function_call.name}")
                function_response = self._handle_function_call(message.function_call)
                logger.debug(
                    f"Function response: {json.dumps(function_response)[:200]}..."
                )

                # Add function call and response to conversation
                self.messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "function_call": {
                            "name": message.function_call.name,
                            "arguments": message.function_call.arguments,
                        },
                    }
                )
                self.messages.append(
                    {
                        "role": "function",
                        "name": message.function_call.name,
                        "content": json.dumps(function_response),
                    }
                )
                logger.debug("Function call and response added to conversation history")

                # Get final response from LLM
                logger.debug("Getting final response from LLM")
                followup = self.client.chat.completions.create(
                    model=self.model, messages=self.messages
                )

                reply = followup.choices[0].message.content
                self.messages.append({"role": "assistant", "content": reply})
                logger.info("Final response generated")
                return reply

            # If no function call, return the message content
            logger.info("No function call detected, returning direct response")
            reply = message.content
            self.messages.append({"role": "assistant", "content": reply})
            return reply

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            error_message = f"Error processing message: {str(e)}"
            self.messages.append({"role": "assistant", "content": error_message})
            return error_message

    @log_decorator("function_call")
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
            logger.info(f"Handling function call: {name}")
            logger.debug(f"Function arguments: {json.dumps(args)}")

            # Call the appropriate function
            if name == "add_rule":
                logger.debug("Calling add_rule function")
                return self._add_rule(args)
            elif name == "edit_rule":
                logger.debug("Calling edit_rule function")
                return self._edit_rule(args)
            elif name == "delete_rule":
                logger.debug("Calling delete_rule function")
                return self._delete_rule(args)
            elif name == "search_rules":
                logger.debug("Calling search_rules function")
                return self._search_rules(args)
            else:
                logger.warning(f"Unknown function called: {name}")
                return {"success": False, "message": f"Unknown function: {name}"}
        except Exception as e:
            logger.error(f"Error handling function call: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"Error handling function call: {str(e)}",
            }

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
                            "description": "Natural language description of the rule",
                        }
                    },
                    "required": ["description"],
                },
            },
            {
                "name": "edit_rule",
                "description": "Modify an existing Drools rule",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "rule_name": {
                            "type": "string",
                            "description": "Name of the rule to edit",
                        },
                        "changes": {
                            "type": "string",
                            "description": "Natural language description of the changes to make",
                        },
                    },
                    "required": ["rule_name", "changes"],
                },
            },
            {
                "name": "delete_rule",
                "description": "Move a rule to the deleted_rules directory. The system will first search for the rule and move the best match.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "rule_name": {
                            "type": "string",
                            "description": "Name or description of the rule to move. The system will search for the best match.",
                        }
                    },
                    "required": ["rule_name"],
                },
            },
            {
                "name": "search_rules",
                "description": "Search for Drools rules based on natural language query",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language search query to find similar rules",
                        }
                    },
                    "required": ["query"],
                },
            },
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

            # from tools.search_tool import ensure_rules_indexed

            # Call the add_rule function
            result = add_rule(
                user_input=args["description"],
                java_classes_map=self.java_classes_map,
                rules_dir=self.rules_dir,
                api_key=self.api_key,
            )

            # If rule was added successfully, ensure it's indexed
            # if result.get("success", False):
            #     ensure_rules_indexed(self.rules_dir, self.api_key)

            return result
        except Exception as e:
            return {"success": False, "message": f"Error creating rule: {str(e)}"}

    def _edit_rule(self, args):
        """
        Edit an existing rule.

        Args:
            args (dict): Function arguments

        Returns:
            dict: Function response
        """
        try:
            # Import the edit_rule function
            from tools.edit_tool import edit_rule

            # from tools.search_tool import ensure_rules_indexed

            # Call the edit_rule function
            result = edit_rule(
                rule_name=args["rule_name"],
                changes=args["changes"],
                rules_dir=self.rules_dir,
                api_key=self.api_key,
            )

            # If rule was edited successfully, ensure it's indexed
            # if result.get("success", False):
            #     ensure_rules_indexed(self.rules_dir, self.api_key)

            return result
        except Exception as e:
            return {"success": False, "message": f"Error editing rule: {str(e)}"}

    def _delete_rule(self, args):
        """
        Delete an existing rule by moving it to the deleted_rules directory.

        Args:
            args (dict): Function arguments

        Returns:
            dict: Function response
        """
        try:
            # Import required functions
            from tools.search_tool import search_rules
            import shutil
            import os

            # First search for the rule
            search_result = search_rules(
                query=args["rule_name"],
                rules_dir=self.rules_dir,
                api_key=self.api_key,
            )

            if not search_result.get("success", False):
                return {
                    "success": False,
                    "message": f"Could not find any rules matching '{args['rule_name']}'. Please check the rule name and try again.",
                }

            # Get the best matching rule
            rules = search_result.get("rules", [])
            if not rules:
                return {
                    "success": False,
                    "message": f"No rules found matching '{args['rule_name']}'",
                }

            best_match = rules[0]  # First result is the best match
            rule_name = best_match["rule_name"]

            # Ensure deleted_rules directory exists
            deleted_rules_dir = os.path.join(self.rules_dir, "deleted_rules")
            os.makedirs(deleted_rules_dir, exist_ok=True)

            # Move the file to deleted_rules directory
            source_path = os.path.join(self.rules_dir, rule_name)
            dest_path = os.path.join(deleted_rules_dir, rule_name)

            if os.path.exists(source_path):
                shutil.move(source_path, dest_path)
                logger.info(f"Moved rule file from {source_path} to {dest_path}")
                return {
                    "success": True,
                    "message": f"Successfully moved rule '{rule_name}' to deleted_rules directory",
                    "moved_rule": best_match,
                }
            else:
                return {
                    "success": False,
                    "message": f"Rule file not found: {rule_name}",
                }

        except Exception as e:
            logger.error(f"Error moving rule: {str(e)}")
            return {"success": False, "message": f"Error moving rule: {str(e)}"}

    @log_decorator("search_rules")
    def _search_rules(self, args):
        """
        Search for rules.

        Args:
            args (dict): Function arguments

        Returns:
            dict: Function response
        """
        try:
            # Import the search_rules function
            from tools.search_tool import search_rules

            logger.debug("Successfully imported search_rules function")

            # Call the search_rules function
            logger.debug(f"Searching with query: {args['query']}")
            result = search_rules(
                query=args["query"],
                rules_dir=self.rules_dir,
                api_key=self.api_key,
            )

            logger.info(
                f"Search completed with success: {result.get('success', False)}"
            )
            return result
        except Exception as e:
            logger.error(f"Error searching rules: {str(e)}", exc_info=True)
            return {"success": False, "message": f"Error searching rules: {str(e)}"}
