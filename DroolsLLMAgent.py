import json
import os
from typing import List, Dict, Any
from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from pathlib import Path
from logger_utils import log_decorator, log_operation, logger

# Load environment variables
logger.info("Loading environment variables in DroolsLLMAgent.py...")
load_dotenv()

# Populate these lists with Java class names from your knowledge base
TARGET_CLASSES: List[str] = ["EmployeeRecommendation"]
INPUT_CLASSES: List[str] = ["RestaurantData"]
COLLECTION_NAME = "drools-rule-examples"
EMBEDDING_MODEL = "text-embedding-3-large"  # OpenAI embedding model
RULES_DIR = os.getenv("RULES_DIR")
JAVA_DIR = os.getenv("JAVA_DIR")
openai_key = os.getenv("OPENAI_API_KEY")
qdrant_url = os.getenv("QDRANT_URL")
qdrant_key = os.getenv("QDRANT_API_KEY")

print("DroolsLLMAgent environment check:")
print("OPENAI_API_KEY exists:", "Yes" if openai_key else "No")
print("OPENAI_API_KEY length:", len(openai_key) if openai_key else 0)

# Initialize clients
oai = OpenAI(api_key=openai_key)
qdrant = QdrantClient(url=qdrant_url, prefer_grpc=False, api_key=qdrant_key)

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
        if message.function_call:
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
            

            followup = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages
            )
            reply = followup.choices[0].message.content or ""
            self.messages.append({"role": "assistant", "content": reply})
            return reply

        # Otherwise, return the assistant's message
        reply = message.content or ""
        self.messages.append({"role": "assistant", "content": reply})
        return reply

# Placeholder tool implementations

def embed_text(text: str) -> list:
    res = oai.embeddings.create(input=text, model=EMBEDDING_MODEL)
    return res.data[0].embedding

@log_decorator('search')
def searchDroolsRules(rule_name: str = None, conditions: List[str] = None, actions: List[str] = None) -> List[Dict[str, Any]]:
    """
    Search through Drools rules using semantic search via Qdrant.
    Returns a list of matching rules with their details.
    """
    logger.debug(f"Starting search with parameters: rule_name={rule_name}, conditions={conditions}, actions={actions}")
    
    # Construct search query from the provided parameters
    search_parts = []
    if rule_name:
        search_parts.append(f"Rule named: {rule_name}")
    if conditions:
        search_parts.append(f"Conditions: {', '.join(conditions)}")
    if actions:
        search_parts.append(f"Actions: {', '.join(actions)}")
    
    search_query = " ".join(search_parts)
    logger.debug(f"Constructed search query: {search_query}")
    
    # If no search criteria provided, return empty results
    if not search_query:
        return {"status": "success", "rules": []}
    
    try:
        # First, check if collection exists
        collections = qdrant.get_collections()
        logger.debug(f"[DEBUG] Available collections: {[c.name for c in collections.collections]}")
        
        if COLLECTION_NAME not in [c.name for c in collections.collections]:
            logger.debug(f"[DEBUG] Collection {COLLECTION_NAME} not found!")
            return {"status": "error", "message": f"Collection {COLLECTION_NAME} not found", "rules": []}
            
        # Generate embedding for the search query
        logger.debug("[DEBUG] Generating embedding for search query...")
        query_embedding = embed_text(search_query)
        logger.debug("[DEBUG] Embedding generated successfully")
        
        # Build metadata filter
        must_conditions = []
        
        # Add type filter to only get rules (not Java classes)
        must_conditions.append(
            FieldCondition(
                key="type",
                match=MatchValue(value="rule_example")
            )
        )
        
        # Add source filter if rule_name is provided
        if rule_name:
            # If it's a full filename, use it directly
            if rule_name.endswith('.drl') or rule_name.endswith('.gdst'):
                must_conditions.append(
                    FieldCondition(
                        key="source",
                        match=MatchValue(value=rule_name)
                    )
                )
            else:
                # If it's a partial name, we'll rely on semantic search
                pass
        
        search_filter = Filter(must=must_conditions) if must_conditions else None
        
        # Search in Qdrant
        logger.debug("[DEBUG] Executing Qdrant search...")
        search_results = qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_embedding,
            query_filter=search_filter,
            limit=10  # Adjust this number based on needs
        )
        logger.debug(f"[DEBUG] Search completed. Found {len(search_results)} results")
        
        # Process and format results
        matching_rules = []
        for hit in search_results:
            payload = hit.payload
            logger.debug(f"[DEBUG] Processing hit with payload: {payload}")
            matching_rules.append({
                "rule_name": payload.get("title", payload.get("source", "Unknown")),  # Use title if available, fallback to source
                "file_name": payload.get("source", "unknown"),
                "file_type": payload.get("format", "unknown"),
                "rule_type": payload.get("rule_type", "unknown"),
                "target_class": payload.get("target_class", "unknown"),
                "score": hit.score
            })
        
        return {"status": "success", "rules": matching_rules}
        
    except Exception as e:
        logger.error(f"[DEBUG] Error during semantic search: {str(e)}")
        import traceback
        logger.debug(f"[DEBUG] Full traceback: {traceback.format_exc()}")
        return {"status": "error", "message": str(e), "rules": []}

@log_decorator('generate')
def generateDroolsRuleFromJson(json_payload: dict) -> str:
    # Initialize Qdrant client
    qdrant = QdrantClient(
        url=qdrant_url,
        api_key=qdrant_key
    )
    
    # extract info from JSON
    conditions = json_payload.get("conditions", [])
    input_class_name = json_payload.get("input_class", [])
    output_class_name = json_payload.get("target_class", [])
    rule_type = "complex" if len(conditions) > 1 else "simple"
    file_ext = "gdst" if rule_type == "complex" else "drl"
    
    # Embed full JSON and build metadata filter
    drools_query_text = json.dumps(json_payload)
    drools_query_vec = embed_text(drools_query_text)
    drools_metadata_filter = Filter(
        must=[
            FieldCondition(key="rule_type", match=MatchValue(value=rule_type)),
            FieldCondition(key="format",    match=MatchValue(value=file_ext)),
        ]
    )
    
    #Retrieve matching Drools and Java classes templates
    drools_template_hit = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=drools_query_vec,
        query_filter=drools_metadata_filter,
        limit=1
    )[0]
    drools_file_name= drools_template_hit.payload["source"]
    path = os.path.join(RULES_DIR, drools_file_name)
    with open(path, "r", encoding="utf-8") as f:
        drools_canonical_template = f.read()
    
    # 4. Directly load Java class definitions from filesystem
    def load_class_definition(class_name: str) -> str:
        class_file = f"{class_name}.java"
        class_path = os.path.join(JAVA_DIR, class_file)
        with open(class_path, 'r', encoding='utf-8') as cf:
            return cf.read()

    input_class_def = load_class_definition(input_class_name)
    output_class_def = load_class_definition(output_class_name)

    
    # Construct the LLM prompt with clear steps
    if file_ext == 'drl':
        gen_system_prompt = (
        "You are a Drools-file generator.\n"
        "Steps:\n"
        "1. Use the canonical template provided below.\n"
        "2. Replace rule_name, salience, conditions, and actions per user payload.\n"
        "3. For each user-provided field or method in conditions/actions, map to the exact getter/setter or method from the provided Java class definitions.\n"
        "4. Preserve all other template details (imports, package, dialect, etc.).\n"
        "5. Output only the full text of the generated rule file, using the extension '" + file_ext + "' based on rule_type."
        )
        user_instructions = f'''## Template (drl):
```
{drools_canonical_template}
```
## InputClass ({input_class_name}):
```
{input_class_def}
```
## TargetClass ({output_class_name}):
```
{output_class_def}
```
## Payload:
```
{json.dumps(json_payload)}
```'''
    else:
        gen_system_prompt = (
            "You are a Drools Decision-Table Generator (GDST).\n"
            "Use the retrieved similar gdst file as a reference and follow the user skeleton instructions exactly to produce a valid .gdst XML file importable into Business Central"
        )
        
        user_instructions = f'''## similar (gdst) file :
```
{drools_canonical_template}
```
## InputClass ({input_class_name}):
```
{input_class_def}
```
## TargetClass ({output_class_name}):
```
{output_class_def}
```

SKELETON (DO NOT CHANGE):

<decision-table52>
    <packageName>{{packageName}}</packageName>
    <imports>
        <imports/>
    </imports>
    <tableName>{{rule_name}}</tableName>
    <tableFormat>EXTENDED_ENTRY</tableFormat>
    <hitPolicy>NONE</hitPolicy>

    <rowNumberCol>
       <hideColumn>false</hideColumn>
       <width>-1</width>
       <header>Row</header>
    </rowNumberCol>
    <descriptionCol>
       <hideColumn>false</hideColumn>
       <width>-1</width>
       <header>Description</header>
    </descriptionCol>

    <metadataCols/>
    <attributeCols>
       <AttributeCol52>
         <attribute>salience</attribute>
         <header>Salience</header>
         <hideColumn>false</hideColumn>
         <width>-1</width>
         <defaultValue>
           <NumericValue>{{salience}}</NumericValue>
         </defaultValue>
       </AttributeCol52>
    </attributeCols>

    <conditionPatterns>
      <!-- zero or more free-form BRL conditions -->
      <org.drools.workbench.models.guided.dtable.shared.model.BRLConditionColumn>
        <definition>
          <org.drools.workbench.models.guided.dtable.shared.model.FreeFormLine>
            <text>{{dslCondition}}</text>
          </org.drools.workbench.models.guided.dtable.shared.model.FreeFormLine>
        </definition>
      </org.drools.workbench.models.guided.dtable.shared.model.BRLConditionColumn>

      <!-- zero or more structured Pattern52 blocks -->
      <Pattern52>
        <factType>{{input_class}}</factType>
        <boundName>$input</boundName>
        <negated>false</negated>
        <conditions>
          <condition-column52>
            <factField>{{fieldName}}</factField>
            <operator>{{operator}}</operator>
            <fieldType>Numeric</fieldType>
            <constraintValueType>Literal</constraintValueType>
            <header>{{input_class}}.{{fieldName}} {{operator}}</header>
            <hideColumn>false</hideColumn>
            <width>-1</width>
            <defaultValue/>
          </condition-column52>
        </conditions>
        <window>
          <parameters/>
        </window>
        <entryPointName/>
      </Pattern52>
    </conditionPatterns>

    <actionCols>
      <!-- zero or more free-form BRL actions -->
      <org.drools.workbench.models.guided.dtable.shared.model.BRLActionVariableColumn>
        <definition>
          <org.drools.workbench.models.guided.dtable.shared.model.FreeFormLine>
            <text>{{dslAction}}</text>
          </org.drools.workbench.models.guided.dtable.shared.model.FreeFormLine>
        </definition>
      </org.drools.workbench.models.guided.dtable.shared.model.BRLActionVariableColumn>

      <!-- zero or more structured action-set-field columns -->
      <ActionSetFieldCol52>
        <boundName>$target</boundName>
        <factField>employees</factField>
        <type>Numeric</type>
        <header>Set employees</header>
        <hideColumn>false</hideColumn>
        <width>-1</width>
      </ActionSetFieldCol52>
    </actionCols>

    <auditLog>
       <enabled>false</enabled>
    </auditLog>

    <data>
      <!-- For each rule row, one <list> with one <value> per column -->
      <list>
        <value>
          <valueNumeric class="int">{{rowNumber}}</valueNumeric>
          <valueString></valueString>
          <dataType>NUMERIC_INTEGER</dataType>
          <isOtherwise>false</isOtherwise>
        </value>
        <value>
          <valueString></valueString>
          <dataType>STRING</dataType>
          <isOtherwise>false</isOtherwise>
        </value>
        <!-- one <value> per BRLConditionColumn or Pattern52 column -->
        <value>
          <valueNumeric class="int">{{threshold}}</valueNumeric>
          <valueString></valueString>
          <dataType>NUMERIC_INTEGER</dataType>
          <isOtherwise>false</isOtherwise>
        </value>
        <!-- one <value> per BRLActionVariableColumn or ActionSetFieldCol52 column -->
        <value>
          <valueNumeric class="int">{{employeeCount}}</valueNumeric>
          <valueString></valueString>
          <dataType>NUMERIC_INTEGER</dataType>
          <isOtherwise>false</isOtherwise>
        </value>
      </list>
      <!-- Repeat <list> for each rule row -->
    </data>
</decision-table52>

INSTRUCTIONS:
1. Do not change any tag names or their order in the skeleton above.
2. Fill:
    - {{packageName}} fill it with the same package name from sample gdst file or input_class Java class.
    - {{rule_name}} fill it from the rule_name in user's JSON.
    - {{salience}} fill it from the salience in user's JSON.
    - {{input_class}} fill it from input_class in user's JSON.
    - $target The bound variable name for your action fact (usually $target mapping to {{target_class}}).
    - {{operator}} The comparison operator (e.g. >=, ==, <), extracted from the user's condition string.
    - $input The bound variable name representing an instance of {{input_class}} in the WHEN clause. e.g. $input : RestaurantData( getExpectedSales() >= … )
    - All your <ConditionCol52> entries under that <Pattern52> will apply against this $input.
    - For BRLConditionColumn / BRLActionVariableColumn, insert the DSL snippet into <text>.
    - The exact DRL/DSL snippet for that condition, taken verbatim from the user's JSON. e.g. if the JSON says "condition": "expected sales > 5000", you might transform that into <text>eval(RestaurantData.getExpectedSales() > 5000);</text>
    - For Pattern52, split each structured condition into fieldName + operator.
    - ActionSetFieldCol52, use the provided target class and action.
3. Emit one <list> per rule, with <value> entries matching the exact column sequence above.
4. Do not omit empty sections (e.g. an empty <imports/> or <metadataCols/> must still appear)
5. Output only the completed .gdst XML.


## Payload:
```
{json.dumps(json_payload)}
```'''
    
    # Call the LLM
    response = oai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": gen_system_prompt},
            {"role": "user",   "content": user_instructions}
        ]
    )
    drools_text = response.choices[0].message.content.strip()

    # 7. Write the rule file to disk
    filename = f"{json_payload['rule_name']}.{file_ext}"
    with open(filename, 'w') as f:
        f.write(drools_text)

    return {"status": "success", "file_name": filename}

def editDroolsRule(**payload: Any) -> Dict[str, Any]:
    return {"status": "success", "rule_name": payload.get("rule_name")}

@log_decorator('delete')
def deleteDroolsRule(rule_name: str) -> Dict[str, Any]:
    """
    Delete a Drools rule file from the rules_examples directory.
    First searches for the rule to confirm it exists, then deletes it.
    """
    logger.debug(f"Attempting to delete rule: {rule_name}")
    
    try:
        # First, search for the rule to get its exact filename
        search_results = searchDroolsRules(rule_name=rule_name)
        
        if search_results["status"] != "success":
            error_msg = f"Failed to search for rule: {search_results.get('message', 'Unknown error')}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg, "rule_name": rule_name}
            
        if not search_results["rules"]:
            error_msg = f"Rule '{rule_name}' not found"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg, "rule_name": rule_name}
            
        # Get the first matching rule's filename
        rule_file = search_results["rules"][0]["file_name"]
        
        # Construct the full path
        rules_dir = Path(RULES_DIR) if RULES_DIR else Path("rules_examples")
        file_path = rules_dir / rule_file
        
        logger.info(f"Deleting file: {file_path}")
        
        # Delete the file
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Successfully deleted {file_path}")
            
            # Also remove from Qdrant if it exists
            try:
                # Search for the point with matching source
                search_filter = Filter(
                    must=[
                        FieldCondition(
                            key="source",
                            match=MatchValue(value=rule_file)
                        )
                    ]
                )
                
                # Get points to delete
                search_results = qdrant.scroll(
                    collection_name=COLLECTION_NAME,
                    filter=search_filter,
                    limit=1
                )
                
                points = search_results[0]  # First element is points, second is next page offset
                if points:
                    point_ids = [point.id for point in points]
                    qdrant.delete(
                        collection_name=COLLECTION_NAME,
                        points_selector=point_ids
                    )
                    logger.info(f"Removed rule from Qdrant index")
            except Exception as e:
                logger.warning(f"Failed to remove from Qdrant: {str(e)}")
                # Don't fail the whole operation if Qdrant cleanup fails
            
            return {"status": "success", "message": f"Rule '{rule_file}' deleted successfully", "rule_name": rule_file}
        else:
            error_msg = f"Rule file '{rule_file}' not found in filesystem"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg, "rule_name": rule_file}
            
    except Exception as e:
        logger.error(f"Error during rule deletion: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e), "rule_name": rule_name}

# Example usage:
# agent = DroolsLLMAgent(api_key="YOUR_API_KEY")
# print(agent.handle_user_message("I want to add a new rule."))
