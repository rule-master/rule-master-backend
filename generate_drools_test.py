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
        
        user_instructions = f'''## Template (gdst) file :
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
        <!-- follow same pattern from the drools_canonical_template -->
      </org.drools.workbench.models.guided.dtable.shared.model.BRLConditionColumn>

      <!-- zero or more structured Pattern52 blocks -->
      <Pattern52>
        <!-- follow same pattern from the drools_canonical_template on how to fill the data-->
        <factType>{{input_class}}</factType>
        <boundName>bound Name using variable name from {{input_class}}</boundName>
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
        <boundName>bound Name using variable name from {{target_class}}</boundName>
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
- Do not change any tag names or their order in the skeleton above.
- learn from the sample provided in canonical template above (drools_canonical_template).
- {{packageName}} fill it with the same package name used in canonical template
- {{rule_name}} fill it from the rule_name in user's JSON.
- {{salience}} fill it from the salience in user's JSON.
- {{input_class}} fill it from input_class in user's JSON.
- {{target_class}} fill it from target_class in user's JSON.
- {{operator}} The comparison operator (e.g. >=, ==, <), extracted from the user’s condition string.
- All your <ConditionCol52> entries under that <Pattern52> will apply against this $input.
- For BRLConditionColumn / BRLActionVariableColumn, insert the DSL snippet into <text>.
- The exact DRL/DSL snippet for that condition, taken verbatim from the user’s JSON. e.g. if the JSON says "condition": "expected sales > 5000", you might transform that into <text>eval(RestaurantData.getExpectedSales() > 5000);</text>
- For Pattern52, split each structured condition into fieldName + operator.
- ActionSetFieldCol52, use the provided target class and action.
- Emit one <list> per rule, with <value> entries matching the exact column sequence above.
- Do not omit empty sections (e.g. an empty <imports/> or <metadataCols/> must still appear)
- Output only the completed .gdst XML.


## Payload:
```
{json.dumps(json_payload)}
```'''
    
    # Call the LLM
    response = oai.chat.completions.create(
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
    "rule_name": "TestRule",
    "salience": 100,
    "conditions": [{"condition": "expected sales > 5000", "actions": ["set employees to 10"]},
                   {"condition": "expected sales > 8000", "actions": ["set employees to 15"]},
                   {"condition": "expected sales > 12000", "actions": ["set employees to 20"]}]
    }
    
    output_file = generateDroolsRuleFromJson(sample_payload_2)
    print(f"Generated rule file: {output_file}")