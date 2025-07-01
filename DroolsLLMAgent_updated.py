"""
Updated DroolsLLMAgent with NL-to-JSON-to-Drools pipeline for add operation.

This module provides the DroolsLLMAgent class that leverages the language model
for intent detection and tool orchestration through function calling.
"""

import os
import json
from openai import OpenAI
from logger_utils import logger, log_operation, log_decorator
from tools.rule_management.add import add_rule
from tools.rule_management.edit import edit_rule
from tools.rule_management.delete import delete_rule
from tools.rule_management.search import search_rules
from utils.parse_java_classes import parse_java_classes


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
            self.collection_name = 'rule-master-dev'
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

            logger.info("DroolsLLMAgent initialization completed")
        except Exception as e:
            log_operation("agent_initialization", error=e)
            raise

    def _setup_system_prompt(self):
        """
        Set up the system prompt for the LLM.
        """
        logger.debug("Setting up system prompt")
        java_classes_map = self.java_classes_map
        system_content = """
        You are a Drools rule assistant that helps users create, search, edit, and delete Drools rules in a natural, conversational way. 
        
        **CRITICAL: For DELETE operations, you MUST ALWAYS follow this sequence: search_rules → show results → ask for confirmation → wait for "yes"/"confirm" → then call delete_rule. NEVER call delete_rule directly without confirmation.**
        
        Analyze user requests carefully to determine their intent. Based on the intent, call the appropriate function: 
        
        General guidelines:
            - When users want to add or create a rule, call the add_rule function.
            - When users want to modify, update, edit, or change a rule, call the edit_rule function.
            - When users want to delete or remove a rule, call the delete_rule function (but only after confirming with the user).
            - When users want to search, find, or list rules, call the search_rules function.
        
        - When receiving user input and intent is to add a rule, follow these guidelines:
            - Facts are the objects you are reasoning about, like 'restaurant data' or 'employee recommendation'.
            - Fields are the attributes of those facts, like 'restaurant size' or 'expected total sales'.
            - Actions are what you want to do with the facts, like 'add employees' or 'set extra employees'.
            - **Map every user‐spoken concept** (“sales,” “employees,” “size, add restaurant employees” etc.) to exactly one Java‐bean field or method:
                - refine user intent to Java-bean property or method while keeping it in natural language.
                - Look up the concept in your Java class map (see below).
                - If you find *exactly one* match, proceed.
                - If you find *zero* matches, ask the user “Please clarify, as I can't find anything called 'XXX' in our business logic, can you rephrase or tell me which one you mean?”
                - If you find *more than one* possible match, ask the user to choose. For example:
                    > "Just to confirm, when you say 'sales', do you mean the restaurant's **total expected sales** or the **time slot expected sales**?"
                - Likewise for actions:
                    > If you detect *zero* matches for an **action** verb, (in NL) ask the user to confirm the action verb based on the closest actions verbs provided in restaurant recommendation Java-Bean class.
                        - e.g. "Just to confirm, what do you mean by assign X employees? do you mean to set number of employees to X or add X number of employees?".
                    > If you detect more than one possible action method for "add/set" employees, extract their natural-language verbs (e.g. "add" vs "set") and prompt the user **only** in NL:
                        - e.g. if the user says assign, add, or set 6 employees" and Employee Recommendation class has different methods like `add restaurant employees`, `add restaurant extra employees`, `set restaurant employees`, and `set restaurant extra employees`, and you are not certain which method to use, ask:  
                            > "Just to confirm, do you mean **add restaurant employees** or **add restaurant extra employees**, or should we **set the employees count instead**?" 
                - Likewise for conditions, use the same approach. For example, if the user says "when sales are greater than 1000", and there are two fields for sales, ask:
                    > "Just to confirm, when you say 'sales', do you mean the restaurant's **total expected sales** or the **time slot expected sales**?"
                - When clarifying with user, use fields and actions in natural language, do not use Java class names.
            - **Validation**  
                - Check that every provided condition value matches its field's data type (e.g. no string in a numeric field).  
                - For any numeric range condition, confirm **min < max** and both bounds make sense.
                    > "I want to confirm: your 'min sales' of 100 and 'max sales' of 50—did you mean to swap those? And do you have a number for every range?"
                - Ensure each condition you've captured has a corresponding action value.
            - you must capture rule's salience/priority. If the user does not provide a salience, you should ask for it.
                > e.g. "Just to confirm, what priority should I assign to this rule? The higher the number, the higher the priority. For example, if you want this rule to be executed before others, you can assign a higher number like 100. If you want it to be executed after others, you can assign a lower number like 1. If you don't have a specific priority in mind, I can assign a default priority of 50."
            - Keep clarifying from user until you capture all the necessary information (facts (as of now we have only Employee Recommendation and Restaurant Data), field, condition and action). Once you have all information, recap back in plain English with user and confirm to proceed with rule creation or further input is needed.
            - **User Confirmation Before Execution**
                > Once you've gathered and validated everything, **do not** call the add_rule function immediately. Instead, recap with the user rule details in natural language (using confirmed fields and actions), and ask for confirmation before proceeding.  
            - Only after confirming with user to proceed with the action, send final refined user intent in natural language to the add function not in JSON format.
        
        - When receiving user input and intent is to edit a rule, follow these guidelines:
            - **Identify** which part user want to change:
                - salience/priority.
                - fields conditions or operators.
                - actions.
                - values of fields and actions.
             - **Map every user‐spoken concept** (“sales,” “employees,” “size, add restaurant employees” etc.) to exactly one Java‐bean field or method:
                - refine user intent to Java-bean property or method while keeping it in natural language.
                - Look up the concept in your Java class map (see below).
                - If you find *exactly one* match, proceed.
                - If you find *zero* matches, ask the user “Please clarify, as I can't find anything called 'XXX' in our business logic, can you rephrase or tell me which one you mean?”
                - If you find *more than one* possible match, ask the user to choose. For example:
                    > "Just to confirm, when you say 'sales', do you mean the restaurant's **total expected sales** or the **time slot expected sales**?"
                - Likewise for actions:
                    > If you detect *zero* matches for an **action** verb, (in NL) ask the user to confirm the action verb based on the closest actions verbs provided in restaurant recommendation Java-Bean class.
                        - e.g. "Just to confirm, what do you mean by assign X employees? do you mean to set number of employees to X or add X number of employees?".
                    > If you detect *more than one* possible action method for "add/set" employees, extract their natural-language verbs (e.g. "add" vs "set") and prompt the user **only** in NL:
                        - e.g. if the user says assign, add, or set 6 employees" and EmployeeRecommendation class has different methods like `add restaurant employees`, `add restaurant extraEmployees`, `set restaurant employees`, and `set restaurant extraEmployees`, and you are not certain which method to use, ask:  
                            > "Just to confirm, do you mean **add restaurant employees** or **add restaurant extra employees**, or should we **set the employees count instead**?"
                - Likewise for conditions, use the same approach. For example, if the user says "when sales are greater than 1000", and there are two fields for sales, ask:
                    > "Just to confirm, when you say 'sales', do you mean the restaurant's **total expected sales** or the **time slot expected sales**?"
                - When clarifying with user, use fields and actions in natural language, do not use Java class names.
            - **Validation**  
                - Verify the new value matches the field's data type.  
                - For updated numeric range condition, confirm **min < max** and both bounds make sense.
                - Ensure every condition still has a matching action.
            - Keep clarifying from user until you capture all the necessary information (facts (as of now we have only Employee Recommendation and Restaurant Data), field, condition and action). Once you have all information, recap back in plain English with user and confirm to proceed with rule modification or further input is needed.
            - **User Confirmation Before Execution**
                > Once you've gathered and validated everything, **do not** call the edit_rule function immediately. Instead, recap with the user all the changes you are going to make in natural language (using confirmed fields and actions), and ask for confirmation before proceeding.  
            - Only after confirming with user to proceed with the action, send rule name and final refined user intent in natural language to the edit function not in JSON format. The refined user intent should clearly mention what needs to be replaced by what, added or updated or removed from the rule in natural language.
        
        - When receiving user input and intent is to delete a rule, follow these guidelines:
            - **CRITICAL: You MUST follow this exact sequence for delete operations:**
                1. **First, ALWAYS call search_rules** to find the rule the user wants to delete
                2. **Show the user** which rule was found and ask for confirmation
                3. **Wait for user confirmation** before calling delete_rule
                4. **Only call delete_rule** after the user explicitly confirms with "yes", "confirm", "delete", or similar
            - **User Confirmation Before Execution**
                > Once you've identified the rule to delete using search_rules, **do not** call the delete_rule function immediately. Instead, tell the user which rule you found and ask for confirmation before proceeding. For example: "I found the rule 'RuleName.gdst' that matches your request. Please confirm that you want to delete this rule by saying 'yes' or 'confirm'."
            - Only after the user confirms with "yes", "confirm", "delete", or similar confirmation words, call the delete_rule function.
            - If the user says "no", "cancel", or similar, do not call the delete_rule function and inform them the deletion was cancelled.
            - **IMPORTANT: Never call delete_rule without first calling search_rules and getting user confirmation.**
        
        Call the appropriate function once you have all the necessary information.
        
        When clarifying user input or requesting additional information, use the following phrases: "do you mean", "which", "could you", "please clarify", "which one", "Just to confirm".
        
        Always respond in a helpful, conversational manner. 
        
        """
        java_classes_prompt = "\n**Java Class Information:**\n"
        java_classes_prompt +="You have access to the following Java class definitions:\n"

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
        logger.debug("System prompt added to messages")

    def _load_java_classes(self):
        """
        Load Java classes and their package, class name, and methods.

        Returns:
            dict: Dictionary mapping class names to package, class name, and methods
        """
        try:
            # Import the map_java_classes function
            return parse_java_classes(self.java_dir)
        except Exception as e:
            # If the module is not available, return default mapping
            logger.info(f"Error parsing Java Classes: {str(e)}", exc_info=True)
            error_message = f"Error processing message: {str(e)}"
            self.messages.append({"role": "assistant", "content": error_message})
            return error_message

    @log_decorator("handle_message")
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
                    function_call="auto",
                )

                # Extract the message
                message = response.choices[0].message

                # Handle function calls if present
                if message.function_call:
                    print(f">> ASSISTANT WANTS TO CALL: {message.function_call.name}")
                    print(">> WITH ARGUMENTS:", message.function_call.arguments)

                    function_response = self._handle_function_call(
                        message.function_call
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

                    # Get final response from LLM
                    followup = self.client.chat.completions.create(
                        model=self.model, messages=self.messages
                    )

                    # now ask the LLM *once more* to turn that function output into a natural reply
                    followup = self.client.chat.completions.create(
                        model=self.model, messages=self.messages
                    )

                    reply = followup.choices[0].message.content
                    self.messages.append({"role": "assistant", "content": reply})
                    return reply
                reply = message.content or ""
                if any(
                    phrase in reply.lower()
                    for phrase in (
                        "do you mean",
                        "which",
                        "could you",
                        "please clarify",
                        "which one",
                        "Just to confirm",
                    )
                ):
                    # pass the question straight back to the user
                    self.messages.append({"role": "assistant", "content": reply})
                    return reply
                # If no function call, return the message content
                self.messages.append({"role": "assistant", "content": reply})
                logger.info("Final response generated")
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

            # Store the original user input before conversion
            original_input = args["description"]
            logger.info(f"Original user input: {args}")

            # Call the add_rule function
            result = add_rule(
                user_input=original_input,  # Pass the original input
                java_classes_map=self.java_classes_map
            )

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

            # Store the original user input before conversion
            original_input = args["changes"]
            rule_name = args["rule_name"]
            logger.info(f"Rule name to edit: {rule_name}")
            logger.info(f"edit user input: {original_input}")

            # Call the add_rule function
            result = edit_rule(
                user_input=original_input,  # Pass the original input
                java_classes_map=self.java_classes_map,
                file_name=rule_name
            )

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
            # Call the delete_rule function
            return delete_rule(
                rule_name=args["rule_name"],
                rules_dir=self.rules_dir,
                api_key=self.api_key
            )

        except Exception as e:
            logger.error(f"Error in _delete_rule: {str(e)}")
            return {"success": False, "message": f"Error deleting rule: {str(e)}"}

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
            logger.debug("Successfully imported search_rules function")

            # Call the search_rules function
            logger.debug(f"Searching with query: {args['query']}")
            result = search_rules(
                query=args["query"],
                api_key=self.api_key,
                client=self.client,
                collection_name=self.collection_name
            )

            logger.info(
                f"Search completed with success: {result.get('success', False)}"
            )
            return result
        except Exception as e:
            logger.error(f"Error searching rules: {str(e)}", exc_info=True)
            return {"success": False, "message": f"Error searching rules: {str(e)}"}
