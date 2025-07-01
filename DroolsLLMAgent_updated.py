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
            self.collection_name = 'drools-rule-examples'
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
        system_prompt = """
        You are a Drools rule assistant that helps users create, search, edit, and delete Drools rules in a natural, conversational way. 
        
        **CRITICAL RULE: Always speak in plain NL and don't expose Java class or method names.
        E.g "total expected sales" instead of totalExpectedSales**
        
        General guidelines:
        - Call validate_user_input in case of add, edit intents to validate the request and receive the refined user intent in natural language before proceeding with rule creation or editing using the refined user intent.
        - If user intent is to search, find, or list rules, call the search_rules function passing the user's query as input.
        - If user sends a delete command and provided the rule name to delete, follow below steps:
            1. Call search_rules function passing the user's query as input.
            2. Show the matching rule details back to the user in natural language. 
            3. Ask user for confirmation to delete the rule.
            4. Only after confirming with user to proceed with the action, call the delete_rule function.
        - If user sends a delete command, and the user provided a description of the rule to delete **or** didn't provide the exact rule name, follow the below steps:
            1. Call search_rules function passing the user's query as input.
            2. Show the matching rule names with brief description back to the user in natural language.
            3. Once they pick a single rule, ask user for confirmation to delete the rule. 
            4. Only after confirming with user to proceed with the action, call the delete_rule function.
        - Maintain conversational, helpful tone throughout.
        
        Always respond in a helpful, conversational manner.
        """
        
        self.messages.append({"role": "system", "content": system_prompt})
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
                
                reply = message.content
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
            if name == "validate_user_input":
                logger.debug("Calling validate_user_input function")
                return self._validate_user_input(args)
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
                "name": "validate_user_input",
                "description": "Validate user input based on intent before executing add, or edit operations",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_input": {
                            "type": "string",
                            "description": "The user's input to validate",
                        },
                        "intent": {
                            "type": "string",
                            "description": "The detected intent (add, edit)",
                        }
                    },
                    "required": ["user_input", "intent"],
                },
            },
            {
                "name": "add_rule",
                "description": "Create a new Drools rule from natural language description (only call after validation passes)",
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
                "description": "Modify an existing Drools rule (only call after validation passes)",
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
                "description": "Move a rule to the deleted_rules directory (only call after validation passes)",
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
                "description": "Search for Drools rules based on natural language query (only call after validation passes)",
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
        
    def _validate_user_input(self, args):
        """
        Validate user input based on intent using LLM with specific validation prompts.

        Args:
            args (dict): Function arguments containing user_input and intent

        Returns:
            dict: Validation response
        """
        try:
            user_input = args.get("user_input", "")
            intent = args.get("intent", "")
            
            logger.info(f"Validating user input with intent: {intent}")
            
            # If intent is not add, or edit no validation needed
            if intent.lower() not in ["add", "edit"]:
                return {
                    "validation_passed": True,
                    "intent": intent,
                    "message": "No validation required for this intent",
                    "proceed_with_execution": True
                }
            
            # Get validation prompt based on intent
            validation_prompt = self._get_validation_prompt(intent)
            logger.info(f"Validation prompt: {validation_prompt}")
            
            # Create validation messages
            validation_messages = [
                {"role": "system", "content": validation_prompt},
                {"role": "user", "content": f"Please validate this user input: {user_input}"}
            ]
            logger.info(f"Validation messages: {validation_messages}")
            
            # Call LLM for validation
            validation_response = self.client.chat.completions.create(
                model=self.model,
                messages=validation_messages,
                temperature=0.5
            )
            
            validation_result = validation_response.choices[0].message.content
            logger.info(f"Validation result: {validation_result}")
            
            # Parse validation result to determine if validation passed
            validation_passed = self._parse_validation_result(validation_result)
            
            return {
                "validation_passed": validation_passed,
                "intent": intent,
                "validation_message": validation_result,
                "proceed_with_execution": validation_passed
            }
            
        except Exception as e:
            logger.error(f"Error in validation: {str(e)}", exc_info=True)
            return {
                "validation_passed": False,
                "intent": intent,
                "message": f"Validation error: {str(e)}",
                "proceed_with_execution": False
            }
            
    def _get_java_classes_info(self):
        """
        Get formatted Java classes information for validation prompts.

        Returns:
            str: Formatted Java classes information
        """
        java_classes_info = ""
        for class_name, class_info in self.java_classes_map.items():
            package = class_info.get("package", "")
            methods = class_info.get("methods", [])
            fields = class_info.get("fields", [])

            java_classes_info += f"\nClass: {class_name}\n"
            java_classes_info += f"Package: {package}\n"

            if fields:
                java_classes_info += "Fields:\n"
                for field in fields:
                    java_classes_info += f"- {field}\n"

            if methods:
                java_classes_info += "Methods:\n"
                for method in methods:
                    java_classes_info += f"- {method}\n"
        
        return java_classes_info
    
    def _parse_validation_result(self, validation_result):
        """
        Parse the validation result to determine if validation passed.

        Args:
            validation_result (str): The validation result from LLM

        Returns:
            bool: True if validation passed, False otherwise
        """
        return "VALIDATION_PASSED" in validation_result.upper()

    def _get_validation_prompt(self, intent):
        """
        Get the validation prompt based on the intent.

        Args:
            intent (str): The user's intent (add, edit)

        Returns:
            str: Validation prompt for the specific intent
        """
        java_classes_info = self._get_java_classes_info()
        
        if intent.lower() == "add":
            return f"""
You are validating user input for adding a new Drools rule. Follow this validation process:

**CRITICAL RULES:**
1. Always speak in plain NL and don't use exact Java class or method names (e.g "total expected sales" instead of "totalExpectedSales").
2. When receiving user input, follow these guidelines to analyze the user's intent:
    a. Facts are the objects you are reasoning about, like 'restaurant data' or 'employee recommendation'.
    b. Fields are the attributes of those facts, like 'restaurant size' or 'expected total sales'.
    c. Conditions are the constraints on those facts, like 'total expected sales is between 0 and 5'.
    d. Actions are what you want to do with the facts, like 'add employees' or 'set extra employees'.

**Validation Phase (intent = "add rule")**

follow the following steps:
    
1. **Completeness**  
   - Don't proceed until this passes.
   - Verify that a salience (priority) value was provided. If salience is not provided, ask user to provide it otherwise proceed to the next step.
    example: "I noticed you didn't provide a priority for the rule (any value from 0 to 100). Could you please provide a priority before we continue?"

2. **Validity**
   2.1 **Field-Mapping** 
    - **Map every user‐spoken concept field** (“sales,” “employees,” “size", etc.) to exactly one Java‐bean field from Java class map (see Java Class Information below).
    - Look up the concept in your Java class map (see below).
    - If *zero or multiple field matches*, then follow the steps (a-c) below:
        a. Gather the possible matching fields list from the Java class map (see Java Class Information below).
        b. From the matching list, convert each field name into a natural‐language description (e.g. totalExpectedSales -> total expected sales).
        c. Stop and ask the user to choose one of the closest matching fields. If there is no match, stop and ask user to describe a different field.
        For example in case of matching fields:
        “I’m not sure which field you meant by ‘sales.’  
        Here are the closest options:  
        – total expected sales.
        – time-slot expected sales.
        Please pick one of these or tell me another field you’d like to use.”
        For example in case there is no matching field:
        “I couldn’t find a field called ‘sales’ in our Restaurant Data.  
        Please describe the field you want to use in more detail, or choose from one of these options:  
        – total expected sales.
        – time-slot expected sales.”

   2.2 **Action-Mapping**  
    - **Map every user‐spoken concept action** (e.g. "assign employees", "add extra employees", etc.) to exactly one Java‐bean method from Java class map (see Java Class Information below).
    - Look up the concept in your Java class map (see below).
    - If *zero or multiple action matches*, then follow the steps (a-c) below:
        a. Gather the possible matching list of methods from from the Java class map (see Java Class Information below).
        b. From the matching list, convert each method name into a natural‐language option (e.g. addRestaurantEmployees(int) -> add restaurant employees, setRestaurantEmployees(int) -> set restaurant employees).
        c. Stop and ask the user to choose one of the closest matching actions. If there is no match, stop and ask the user to describe a different action.
        For example in case of matching actions:
        "Just to confirm, when you say 'assign base employees', do you mean:
        • **add restaurant employees** (adds to existing count)
        • **set restaurant employees** (sets total count)  
        • **add restaurant extra employees** (adds extra staff)
        • **set restaurant extra employees** (sets extra staff count)
        Please pick one of these options."
        For example in case there is no matching action:
        "I couldn't find an action called 'assign base employees' in our Employee Recommendation.  
        Please describe the action you want to use in more detail, or choose from one of these options:  
        • **add restaurant employees** (adds to existing count)
        • **set restaurant employees** (sets total count)  
        • **add restaurant extra employees** (adds extra staff)
        • **set restaurant extra employees** (sets extra staff count)"

   2.3 **Logical Consistency**  
    - **Range conditions**: confirm min ≤ max and that both bounds are sensible (e.g. non-negative).  
    - **Single-value conditions**: confirm the literal's type matches the field (no text in a numeric field).  
    - **Action values**: confirm every row's argument is valid (e.g. can't assign –1 employees).  
    - If anything fails, ask: "Your range is min=100, max=50—did you swap those?"
    
   2.4 **Duplication check**
    - Based on user refined description, check if a rule with the same patterns of conditions and actions already exists using search_rules function. If it does, ask user if they want to still proceed with creating a new rule, edit the existing rule, or not proceed with the action.
    - If user wants to proceed with addition, then continue with the next step.
    - If user wants to edit the existing rule, then move to edit rule flow.
    - If user does not want to proceed, then stop and ask user to describe a different rule.
    - For example on exact match: if we have a rule that says "If total expected sales is between 0 and 5, then add 0 extra employees." and user wants to add a new rule that says "If total expected sales is between 0 and 5, then add 0 extra employees." then ask user if they want to proceed with addition, edit the existing rule, or not proceed with the action.
    - For example on partial match: if we have a rule that says "If total expected sales is between 0 and 5, then add 0 extra employees." and user wants to add a new rule that says "If total expected sales is between 10 and 15, then add 10 extra employees." then ask user if they want to proceed with addition, edit the existing rule, or not proceed with the action.

3. **Confirmation**  
   - Once completeness and all validity checks pass, summarize in natural language and ask for user confirmation:  
     Example: "Great! Here's what I've got:  
       • If total expected sales is between 0 and 5, then add 0 extra employees.  
       • If total expected sales is between 5 and 10, then add 1 extra employee.  
       • If total expected sales is between 10 and 20, then add 2 extra employees.  
     And the rule's priority will be 75.  
     Shall I create that rule now?"  
   - Only after receiving user confirmation, go to step 4.

4. **Execution**  
   - Only after confirming with user to proceed with the action, respond with "VALIDATION_PASSED" and send final refined user intent in natural language (using the correct mapping of refined fields and action captured in validity checks) to the add function not in JSON format. The refined user intent should clearly mention what needs to be added to the rule in natural language.

"**Java Class Information:**"
"You have access to the following Java class definitions:"
{java_classes_info}

Respond with either:
- "VALIDATION_PASSED" if all validation steps pass and user confirms
- A specific question or clarification request if validation fails
"""

        elif intent.lower() == "edit":
            return f"""
You are validating user input for editing an existing Drools rule. Follow this validation process:

**CRITICAL RULES:**
1. Always speak in plain NL and don't use exact Java class or method names (e.g "total expected sales" instead of "totalExpectedSales").
2. When receiving user input, follow these guidelines to analyze the user's intent:
    a. Facts are the objects you are reasoning about, like 'restaurant data' or 'employee recommendation'.
    b. Fields are the attributes of those facts, like 'restaurant size' or 'expected total sales'.
    c. Conditions are the constraints on those facts, like 'total expected sales is between 0 and 5'.
    d. Actions are what you want to do with the facts, like 'add employees' or 'set extra employees'.

**Edit-Rule Flow**

1. **Search & Select**
   - Call search_rules function passing the user's description about the rule the user wants to edit.
   - Show the matching rule names with brief description back to the user in natural language,
     for example: "Based on your description, I found these rules:  
       • **HolidayPromo_Rule**: Adds extra employees for holidays.
       • **BaseBySize_Rule1**: Sets base employees based on restaurant size.
       • **ExtraByTimeSlot_Rule**: Adds extra employees based on time slot.
       Which one would you like to edit?"
   - If the user did start by naming a rule ("Edit BaseBySize_Rule1 to…"), still run search_rules under the hood, then show the rule name with it's description and ask:
     "Rule BaseBySize_Rule1 which sets base employees based on restaurant size, is this the rule you want to edit?"

2. **Confirm Target & Detect Inline Edits**  
   - After showing the matching rule(s), confirm which one to edit:
       “Great, we’ll edit **BaseBySize_Rule1**. Is that right?”
   - **If** the user’s original utterance already *specified* exactly what to change (e.g. “so that large restaurants should have 12 employees and salience is 80”), **do not** ask again “What would you like to change?”  
     Instead, proceed directly to the **4.Validation** phase with the parameters they already gave.
   - **Otherwise**, go to step **3. Gather Edit Details** 

3. **Gather Edit Details**
    - before proceeding with validation, get user input and **Identify** which part user want to change:
        - salience/priority.
        - fields conditions or operators.
        - actions.
        - values of fields and actions.
        
4. **Validation**
   4.1 **Field-Mapping** 
    - **Map every user‐spoken concept field** (“sales,” “employees,” “size", etc.) to exactly one Java‐bean field from Java class map (see Java Class Information below).
    - Look up the concept in your Java class map (see below).
    - If *zero or multiple field matches*, then follow the steps (a-c) below:
        a. Gather the possible matching fields list from the Java class map (see Java Class Information below).
        b. From the matching list, convert each field name into a natural‐language description (e.g. totalExpectedSales -> total expected sales).
        c. Stop and ask the user to choose one of the closest matching fields. If there is no match, stop and ask user to describe a different field.
        For example in case of matching fields:
        “I’m not sure which field you meant by ‘sales.’  
        Here are the closest options:  
        – total expected sales.
        – time-slot expected sales.
        Please pick one of these or tell me another field you’d like to use.”
        For example in case there is no matching field:
        “I couldn’t find a field called ‘sales’ in our Restaurant Data.  
        Please describe the field you want to use in more detail, or choose from one of these options:  
        – total expected sales.
        – time-slot expected sales.”

   4.2 **Action-Mapping**  
    - **Map every user‐spoken concept action** (e.g. "assign employees", "add extra employees", etc.) to exactly one Java‐bean method from Java class map (see Java Class Information below).
    - Look up the concept in your Java class map (see below).
    - If *zero or multiple action matches*, then follow the steps (a-c) below:
        a. Gather the possible matching list of methods from from the Java class map (see Java Class Information below).
        b. From the matching list, convert each method name into a natural‐language option (e.g. addRestaurantEmployees(int) -> add restaurant employees, setRestaurantEmployees(int) -> set restaurant employees).
        c. Stop and ask the user to choose one of the closest matching actions. If there is no match, stop and ask the user to describe a different action.
        For example: in case of finding matching actions show the most relevant ones:
        "Just to confirm, when you say 'assign base employees', do you mean:
        • **add restaurant employees** (adds to existing count)
        • **set restaurant employees** (sets total count)  
        • **add restaurant extra employees** (adds extra staff)
        • **set restaurant extra employees** (sets extra staff count)
        Please pick one of these options."
        For example: in case there is no matching action:
        "I couldn't find an action called 'assign base employees' in our Employee Recommendation.  
        Please describe the action you want to use in more detail, or choose from one of these options:  
        • **add restaurant employees** (adds to existing count)
        • **set restaurant employees** (sets total count)  
        • **add restaurant extra employees** (adds extra staff)
        • **set restaurant extra employees** (sets extra staff count)"

   4.3 **Logical Consistency**
    - **Range conditions**: confirm min ≤ max and that both bounds are sensible (e.g. non-negative).  
    - **Single-value conditions**: confirm the literal's type matches the field (no text in a numeric field).  
    - **Action values**: confirm every row's argument is valid (e.g. can't assign –1 employees).  
    - If anything fails, ask: "You asked to make the lower bound 10 and upper bound 5—did you mean 5 to 10 instead?"

5. **Recap & Final Confirmation**
   - Give a human-readable summary of only the changes. For example:
     "Okay! I'll update **BaseBySize_Rule1** to:
       • Change priority from 75 to 80
       • Change the total expected sales range to 1–5 instead of 0–5
      Shall I go ahead and apply these edits?"
   - Only after receiving user confirmation, go to step 6.

6. **Execution**  
   - Only after confirming with user to proceed with the action, respond with "VALIDATION_PASSED", and send rule name and final refined user intent (using the correct mapping of refined fields and action captured in validity checks) in natural language to the edit function not in JSON format. The refined user intent should clearly mention what needs to be replaced by what, added or updated or removed from the rule in natural language.

"**Java Class Information:**"
"You have access to the following Java class definitions:"
{java_classes_info}

Respond with either:
- "VALIDATION_PASSED" if all validation steps pass and user confirms
- A specific question or clarification request if validation fails
"""
        else:
            return "No specific validation required for this intent."

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
