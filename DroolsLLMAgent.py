import json
from typing import List, Dict, Any
from openai import OpenAI

# Populate these lists with Java class names from your knowledge base
TARGET_CLASSES: List[str] = ["EmployeeRecommendation"]
INPUT_CLASSES: List[str] = ["RestaurantData"]

# Define function schemas for OpenAI function-calling
FUNCTION_DEFINITIONS = [
    {
        "name": "searchDroolsRules",
        "description": "Search Drools rules by rule name, conditions, and/or actions. Returns a list of matching rules, each with rule_name, conditions, and actions.",
        "parameters": {
            "type": "object",
            "properties": {
                "rule_name": {"type": "string", "description": "Exact or partial rule name to search for."},
                "conditions": {"type": "array", "items": {"type": "string"}, "description": "Condition expressions to match."},
                "actions": {"type": "array", "items": {"type": "string"}, "description": "Action strings to match."}
            },
            "minProperties": 1
        }
    },
    {
        "name": "generateDroolsRuleFromJson",
        "description": "Generate a new Drools rule file (.drl or .gdst) from the provided JSON payload. Returns status flag and rule_name.",
        "parameters": {
            "type": "object",
            "properties": {
                "intent": {"type": "string"},
                "target_class": {"type": "string"},
                "input_class": {"type": "string"},
                "rule_name": {"type": "string"},
                "salience": {"type": "integer"},
                "conditions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "condition": {"type": "string"},
                            "actions": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["condition", "actions"]
                    }
                }
            },
            "required": ["intent", "target_class", "input_class", "rule_name", "salience", "conditions"]
        }
    },
    {
        "name": "editDroolsRule",
        "description": "Edit an existing Drools rule by updating salience, conditions, or actions. Returns status flag and rule_name.",
        "parameters": {
            "type": "object",
            "properties": {
                "intent": {"type": "string"},
                "rule_name": {"type": "string"},
                "updates": {"type": "object", "description": "Fields to update: salience, conditions, actions."}
            },
            "required": ["intent", "rule_name", "updates"]
        }
    },
    {
        "name": "deleteDroolsRule",
        "description": "Delete an existing Drools rule by rule name. Returns status flag and rule_name.",
        "parameters": {
            "type": "object",
            "properties": {
                "rule_name": {"type": "string", "description": "Name of the rule to delete."}
            },
            "required": ["rule_name"]
        }
    }
]

class DroolsLLMAgent:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.messages: List[Dict[str, Any]] = []  # system prompt should be prepended externally
        
        system_content = f"""
You are a friendly Drools Rule Assistant. Follow these rules based on the user's intent:

1) ADD:
   • intent = "add".
   • Collect: target_class (from {TARGET_CLASSES}), input_class (from {INPUT_CLASSES}), rule_name, salience (integer ≥1), then one or more conditions.
   • For each condition, ask for the condition expression and then one or more actions associated with it.
   • Conditions and actions can be specified either as expressions (e.g., sales > 100) or in natural language (e.g., sales is greater than 100).
   • In your final JSON, include a "conditions" array of objects:
     [
       {{"condition": "...", "actions": ["action1", "action2", ...]}},
       ...
     ]
   • Example ADD JSON:
     {{
       "intent": "add",
       "target_class": "EmployeeRecommendation",
       "input_class": "RestaurantData",
       "rule_name": "ApproveIfHighSales_20250508T145200",
       "salience": 1,
       "conditions": [
         {{"condition": "sales > 5000", "actions": ["set employees to 10"]}}
       ]
     }}
   • CALL generateDroolsRuleFromJson with the collected JSON payload. This function returns a status flag and rule_name.
   • After the call, display:
       "✅ add completed successfully for rule '<rule_name>'" on success, or
       "❌ add failed: <error message>" on error.

2) EDIT:
   • intent = "edit".
   • Ask: "What term would you like to search for? You can provide rule_name, conditions, or actions."
   • CALL searchDroolsRules with any non-null of {{"rule_name":..., "conditions":[...], "actions":[...]}}. This function returns a list of matching rules, each with rule_name, conditions, and actions.
   • Present each matching rule in clear business language.
   • Ask the user: "Which rule by name would you like to edit?"
   • Once confirmed, ask which fields to change (salience, conditions, actions). Conditions and actions follow same structure as in ADD.
   • Example EDIT JSON:
     {{
       "intent": "edit",
       "rule_name": "<selected name>",
       "updates": {{
         "salience": 2,
         "conditions": [
           {{"condition": "orders < 100", "actions": ["set employees to 3", "notify manager"]}}
         ]
       }}
     }}
   • CALL editDroolsRule with the collected JSON payload. This function returns a status flag and the rule_name.
   • After the call, display:
       "✅ edit completed successfully for rule '<rule_name>'" on success, or
       "❌ edit failed: <error message>" on error.

3) DELETE:
   • intent = "delete".
   • Ask: "What term would you like to search for? You can provide rule_name, conditions, or actions."
   • CALL searchDroolsRules with any non-null of {{"rule_name":..., "conditions":[...], "actions":[...]}}.
   • Present each matching rule in clear business language.
   • Ask the user: "Which rule by name would you like to delete?"
   • Once confirmed, Example DELETE JSON:
     {{
       "intent": "delete",
       "rule_name": "<selected name>"
     }}
   • CALL deleteDroolsRule with {{"rule_name":"<selected name>"}}. This function returns a status flag and rule_name.
   • After the call, display:
       "✅ delete completed successfully for rule '<rule_name>'" or
       "❌ delete failed: <error message>".

4) SEARCH:
   • intent = "search".
   • Ask: "What would you like to search for? You can provide rule_name, conditions, or actions."
   • CALL searchDroolsRules with the provided fields.
   • After the call, present each matching rule in clear business language.

Ask one question at a time in clear business language. Use OpenAI's function_call mechanism—do not output raw JSON yourself.
"""

        self.messages.append({"role": "system", "content": system_content})

    def handle_user_message(self, user_message: str) -> str:
        # Append user message
        self.messages.append({"role": "user", "content": user_message})

        # Call OpenAI function-calling via new client API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            functions=FUNCTION_DEFINITIONS,
            function_call="auto"
        )
        # Extract the first choice's message
        message = response.choices[0].message

        # Handle function calls
        if hasattr(message, 'function_call') and message.function_call:
            func_name = message.function_call.name
            args = json.loads(message.function_call.arguments)
            try:
                function_response = globals()[func_name](**args)
                status = function_response.get("status", "success")
            except Exception as e:
                function_response = {"status": "error", "error": str(e)}
                status = "error"

            # Log function call and its result
            self.messages.append({"role": "assistant", "content": None, "function_call": {"name": func_name, "arguments": message.function_call.arguments}})
            self.messages.append({"role": "function", "name": func_name, "content": json.dumps(function_response)})

            # Send confirmation or error back to user
            if status == "success":
                rule_name = function_response.get("rule_name", args.get("rule_name", ""))
                reply = f"✅ {func_name} completed successfully for rule '{rule_name}'."
            else:
                error_msg = function_response.get("error", "Unknown error")
                reply = f"❌ An error occurred during {func_name}: {error_msg}."

            self.messages.append({"role": "assistant", "content": reply})
            return reply

        # Otherwise, return the assistant's message
        reply = message.content or ""
        self.messages.append({"role": "assistant", "content": reply})
        return reply

# Placeholder tool implementations

def searchDroolsRules(rule_name: str = None, conditions: List[str] = None, actions: List[str] = None) -> List[Dict[str, Any]]:
    return [{"rule_name": "SampleRule", "conditions": ["age > 18"], "actions": ["approve"]}]

def generateDroolsRuleFromJson(**payload: Any) -> Dict[str, Any]:
    return {"status": "success", "rule_name": payload.get("rule_name")}

def editDroolsRule(**payload: Any) -> Dict[str, Any]:
    return {"status": "success", "rule_name": payload.get("rule_name")}

def deleteDroolsRule(rule_name: str) -> Dict[str, Any]:
    return {"status": "deleted", "rule_name": rule_name}

# Example usage:
# agent = DroolsLLMAgent(api_key="YOUR_API_KEY")
# print(agent.handle_user_message("I want to add a new rule."))
