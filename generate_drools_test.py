import json
import os
from typing import List, Dict, Any
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from dotenv import load_dotenv
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
oai = OpenAI(api_key=openai_key)
qdrant = QdrantClient(url=qdrant_url, prefer_grpc=False, api_key=qdrant_key)

def load_class_definition(class_name: str) -> str:
    class_file = f"{class_name}.java"
    class_path = os.path.join(JAVA_DIR, class_file)
    with open(class_path, 'r', encoding='utf-8') as cf:
        return cf.read()


def build_section1_prompts(json_payload: dict, skeleton_section1: str):
    """
    Returns a tuple (system_prompt, user_prompt) for Section 1.
    - json_payload: the full user JSON (contains input_class, target_class, rule_name, salience, etc.)
    - skeleton_section1: the raw XML snippet for Section 1 with placeholders.
    """
    # 1. Extract values
    input_class  = json_payload["input_class"]
    target_class = json_payload["target_class"]
    rule_name    = json_payload["rule_name"]
    salience     = json_payload.get("salience", "")
    input_class_def = load_class_definition(input_class)

    # 2. System prompt: instructions only for Section 1
    system_prompt = (
        "Section 1: Table & Metadata columns\n"
        "Your task is to fill **only** these tags in the skeleton below:\n"
        "  • <tableName>\n"
        "  • <rowNumberCol>\n"
        "  • <descriptionCol>\n"
        "  • <ruleNameColumn>\n"
        "  • <metadataCols/>\n"
        "  • <attributeCols> (always one salience column)\n"
        "  • <packageName>\n"
        "  • <version>\n"
        "  • <tableFormat>\n"
        "  • <hitPolicy>\n"
        "\n"
        "For each tag:\n"
        "  - Replace __LLM_INSERT_TABLE_NAME__ with the JSON.rule_name\n"
        "  - Emit rowNumberCol exactly as given (static)\n"
        "  - Emit descriptionCol exactly as given (static)\n"
        "  - Emit ruleNameColumn exactly as given (static)\n"
        "  - Emit <metadataCols/> exactly (static)\n"
        "  - Replace __LLM_INSERT_SALIENCE__ with JSON.salience in the single attribute-column52 block\n"
        "  - Read the provided Java input class POJO source to find the `package ...;` line.\n"
        "  - Replace __LLM_INSERT_PACKAGE_NAME__ with exact package (everything before the semicolon) for <packageName>.\n"
        "  - Emit <version>739</version> exactly (static)\n"
        "  - Emit <tableFormat>EXTENDED_ENTRY</tableFormat> exactly (static)\n"
        "  - Emit <hitPolicy>NONE</hitPolicy> exactly (static)\n"
        "\n"
        "Output **only** the completed XML fragment for Section 1—no extra text."
    )

    # 3. User prompt: skeleton + the concrete values
    user_prompt = (
        "Here is the Section 1 skeleton:\n"
        "```xml\n"
        f"{skeleton_section1}\n"
        "```\n\n"
        "Here is the Java POJO source for the input class (so you can extract its package):\n"
        "```java\n"
        f"{input_class_def}\n"
        "```\n\n"
        "And here are the values to inject:\n"
        f"- input_class: `{input_class}`\n"
        f"- target_class: `{target_class}`\n"
        f"- rule_name: `{rule_name}`\n"
        f"- salience: `{salience}`\n\n"
        "Please fill in every placeholder in the skeleton accordingly."
    )

    return system_prompt, user_prompt
  
def build_conditions_prompts(json_payload: dict, conditions_skeleton: str):
    """
    Returns (system_prompt, user_prompt) for Section 3 (<conditionPatterns>).
    - json_payload: full user JSON including 'conditions'
    - skeleton_section3: XML snippet for Section 3 with placeholders
    - input_class_def: full Java source of INPUT_CLASS for package/field reference
    - target_class_def: full Java source of TARGET_CLASS for method reference
    """
    # 1. Extract values
    input_class  = json_payload["input_class"]
    target_class = json_payload["target_class"]
    input_class_def = load_class_definition(input_class)
    target_class_def = load_class_definition(target_class)

    # Extract conditions array as JSON string
    conditions_list = json_payload.get("conditions", [])
    conditions_json = json.dumps(conditions_list, indent=2)

    # System prompt with tag-by-tag instructions
    system_prompt = (
        "Section 3: Condition Patterns\n"
        "Fill **only** the <conditionPatterns> in skeleton below. Follow these steps exactly:\n"
        "1. First, examine all conditions in the provided JSON:\n"
        "  - If a condition string matches a single field comparison of the form '<field> <operator> <value>', treat it as a simple condition.\n"
        "  - Otherwise, treat it as a free-form DSL condition.\n"
        "2. Emit <conditionPatterns> once as a static root.\n"
        "3. Emit first <BRLConditionColumn> which binds TARGET_CLASS helper:\n"
        "   - Replace __LLM_INSERT_TARGET_HEADER_ALIAS__ with class target name as in target class def\n"
        "   - Replace __LLM_INSERT_TARGET_INSTANCE__ with a code to create instance of a TARGET_CLASS() and instance name should be lower case of the capital letters in class name e.g. of format 'er : EmployeeRecommendation()'.\n"
        "4. Emit first <BRLConditionColumn> which binds INPUT_CLASS helper:\n"
        "   - Replace __LLM_INSERT_INPUT_HEADER_ALIAS__ with class target name as in target class def\n"
        "   - Replace __LLM_INSERT_INPUT_INSTANCE__ with a code to create instance of a TARGET_CLASS() and instance name should be lower case of the capital letters in class name e.g. of format 'rd : RestaurantData()'.\n"
        "5. Emit <Pattern52> for simple field-based conditions if exists, otherwise don't emit.\n"
        "   - repeat one <condition-column52> per condition. \n" 
        "   - Replace __INPUT_CLASS__ with input exact class name as found in INPUT_CLASS POJO.\n"
        "   - Replace __LLM_PATTERN52_INPUT_ALIAS__ with camelCase input class name found in INPUT_CLASS POJO.\n"
        "   - <condition-column52> (inside <Pattern52>) – repeat exactly once per simple condition emitting static content and filling:"
        "   - Replace the greater operator '>' with '&gt;' and smaller operator with &lt; and add '=' behind it in case it was '>=' or '<='.\n"
        "   - Replace __LLM_INSERT_TYPE__ with INPUT_CLASS POJO field dataType but in format (e.g. NUMERIC_INTEGER, STRING, NUMERIC_DOUBLE, BOOLEAN etc.)"
        "   - Replace __LLM_INSERT_CONDITION_HEADER__ with full condition human text using field, operator and value (e.g. \"field = value\", \"field &gt;= value\")\n"
        "   - Replace __LLM_INSERT_FACT_FIELD__ with INPUT_CLASS POJO field name (camelCase).\n"
        "   - Replace __LLM_INSERT_FACT_TYPE__ with INPUT_CLASS POJO field dataType (Double, String, Integer, etc.)\n"
        "   - Replace __LLM_INSERT_OPERATOR__: operator ('==', '&lt;', '&gt;', '&gt;=', '&lt;=', etc.)\n"
        "5. Emit BRLConditionColumn for free-form/DSL conditions if exists (repeat once per DSL condition if needed):\n"
        "   - in DSL expression, replace the greater operator '>' with '&gt;' and smaller operator with &lt; and add '=' behind it in case it was '>=' or '<='.\n"
        "   - Replace __LLM_INSERT_DSL_HEADER__ with a human short descriptive header.\n"
        "   - Replace __LLM_INSERT_DSL_EXPRESSION__ with DSL expression inside eval(). in eval it has subject (e.g. er.getRestaurantEmployees(), rd.getCalculationDateTime()), then operator (e.g &gt;=) and finally the value placeholder ''"
        "   - Replace __LLM_INSERT_DSL_VAR__ with the same value placeholder used in __LLM_INSERT_DSL_EXPRESSION__"
        "6. Emit </conditionPatterns> once as closing tag.\n"
        "Output **only** the completed XML fragment for Section 3—no extra text."
    )

    # User prompt with skeleton, POJO sources, and JSON conditions
    user_prompt = (
        "Section 3 skeleton to fill:\n"
        "```xml\n"
        f"{conditions_skeleton}\n"
        "```\n\n"
        "Java POJO for INPUT_CLASS (for field types and package):\n"
        "```java\n"
        f"{input_class_def}\n"
        "```\n\n"
        "Java POJO for TARGET_CLASS (for helper methods):\n"
        "```java\n"
        f"{target_class_def}\n"
        "```\n\n"
        "User conditions JSON:\n"
        "```json\n"
        f"{conditions_json}\n"
        "```\n\n"
        "Please replace each placeholder in the skeleton above as per the instructions."
    )

    return system_prompt, user_prompt
  
def embed_text(text: str) -> list:
    res = oai.embeddings.create(input=text, model=EMBEDDING_MODEL)
    return res.data[0].embedding

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
    drools_template_hits = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=drools_query_vec,
        query_filter=drools_metadata_filter,
        limit=3
    )
    
    # 2. Build few-shot XML blocks with titles
    sections = []
    for doc in drools_template_hits:
        drools_file_name= doc.payload["source"]
        path = os.path.join(RULES_DIR, drools_file_name)
        with open(path, "r", encoding="utf-8") as f:
          content = f.read()
        sections.append(f"### Example: {drools_file_name}\n```content \n{content}\n```")
    drools_samples_sections="\n\n".join(sections)
    
    # 4. Directly load Java class definitions from filesystem
    def load_class_definition(class_name: str) -> str:
        class_file = f"{class_name}.java"
        class_path = os.path.join(JAVA_DIR, class_file)
        with open(class_path, 'r', encoding='utf-8') as cf:
            return cf.read()

    input_class_def = load_class_definition(input_class_name)
    output_class_def = load_class_definition(output_class_name)
    
    with open("gdst_skeleton.gdst", "r") as f:
      gdst_skeleton = f.read()

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
{drools_samples_sections}
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
          "You are a Drools Guided Decision Table generator for Business Central.\n"
          "• We have provided 3 sample `.gdst` files below. Study their structure, tags, and how conditions and actions are expressed in XML.\n"
          "• Do not copy their specific content—only learn the common template they follow.\n"
          "• You also have the full definitions of the INPUT_CLASS and TARGET_CLASS POJOs, including package names and field types. Use these to populate `<imports>`, `<packageName>`, `<factType>`, `<boundName>`, and bindings as instructed in the provided skeleton.\n"
          "• Your job is to merge the patterns you see in the examples with the skeleton—filling in every `__LLM_INSERT_*__` placeholder—so that the output is a valid `.gdst` XML file that can be imported into Business Central without errors.\n"
          "• Make sure to:\n"
            "1. Study the three sample .gdst files to learn their common XML structure—tag order, nesting, and naming conventions for conditions and actions—and then apply that learned structure to fill in the provided skeleton with the user’s values.\n"
            "2. Initialize the OUTPUT helper (`TARGET_CLASS`) and INPUT helper (`INPUT_CLASS`) via BRLConditionColumns.\n"
            "3. Use `<Pattern52>` blocks for simple field constraints, and `<BRLConditionColumn>` blocks for any free-form or DSL expressions.\n"
            "4. Populate `<imports>` with the two DTO classes and any other required Java types.\n"
            "5. Set `<version>` to `739`, `<tableFormat>` to `EXTENDED_ENTRY`, and `<hitPolicy>` to `NONE`.\n"
            "6. Repeat `<condition-column52>`, `<BRLActionColumn>`, and `<list>` blocks as needed for multiple conditions, actions, and data rows.\n"
        )
        
        user_json_str = json.dumps(json_payload, indent=2)

        user_message = (
            "Here is the user’s input JSON for the rule:\n"
            "```json\n"
            f"{user_json_str}\n"
            "```"
        )
    
    # Call the LLM
    response = oai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": gen_system_prompt},
            {"role": "user",   "content": user_message}
        ]
    )
    drools_text = response.choices[0].message.content.strip()

    # 7. Write the rule file to disk
    filename = f"{json_payload['rule_name']}.{file_ext}"
    with open(filename, 'w') as f:
        f.write(drools_text)

    return filename

if __name__ == "__main__":    
    sample_payload = {
        "intent": "add",
        "target_class": "EmployeeRecommendation",
        "input_class": "RestaurantData",
        "rule_name": "DynamicStaffRule",
        "salience": 7,
        "conditions": [
            {"condition": "expected sales > 15000", "actions": ["set restaurant employees to 10"]}
        ]
    }
    
    sample_payload_2 = {
    "intent": "add",
    "target_class": "EmployeeRecommendation",
    "input_class": "RestaurantData",
    "rule_name": "TestRule2",
    "salience": 100,
    "conditions": [{"condition": "expected sales = 5000", "actions": ["set employees to 10"]},
                   {"condition": "expected sales = 8000", "actions": ["set employees to 15"]},
                   {"condition": "expected sales >= 12000", "actions": ["set employees to 20"]}]
    }
    
    skeleton1 = open("gdst_skeleton_section1.xml").read()
    sys_msg, usr_msg = build_section1_prompts(sample_payload_2, skeleton1)

    messages = [
        {"role": "system", "content": sys_msg},
        {"role": "user",   "content": usr_msg},
    ]
    resp = oai.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.0
    )
    section1_xml = resp.choices[0].message.content.strip()
    
    filename = f"section1.xml"
    with open(filename, 'w') as f:
        f.write(section1_xml)

    conditions_skeleton = open("conditions_skeleton.xml").read()
    sys_msg, usr_msg = build_conditions_prompts(sample_payload_2, conditions_skeleton)

    messages = [
        {"role": "system", "content": sys_msg},
        {"role": "user",   "content": usr_msg},
    ]
    resp = oai.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.0
    )
    condition_xml = resp.choices[0].message.content.strip()
    
    filename = f"conditions.xml"
    with open(filename, 'w') as f:
        f.write(condition_xml)