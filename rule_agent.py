import os
from dotenv import load_dotenv
from openai import OpenAI
from drools_knowledge_base import DROOLS_KNOWLEDGE_BASE
import json

load_dotenv()  # loads .env

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1"
)

SYSTEM_PROMPT = """
You are RuleMaster, an AI assistant specialized in BRMS using DMN and Drools.
When given a natural-language rule, return ONLY the valid DMN XML code without any additional text, explanations, or markdown formatting.
Do not include any text before or after the XML code.

The DMN XML must include only these essential components:
1. XML declaration
2. Basic namespaces (MODEL, DMNDI, DI, DC)
3. Decision with:
   - Decision table with hit policy
   - Input expressions with proper type references
   - Output definitions
4. Rules with proper input and output entries

Keep the structure minimal and avoid any unnecessary elements.

Use the following patterns as reference:
{patterns}
"""


def generate_rule(prompt: str, model="llama3-8b-8192"):
    # Format the system prompt with the knowledge base patterns
    formatted_prompt = SYSTEM_PROMPT.format(
        patterns=json.dumps(DROOLS_KNOWLEDGE_BASE, indent=2)
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": formatted_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
    )
    return response.choices[0].message.content


def export_rule_to_xml(rule_text: str, output_file: str = "rule.dmn"):
    """
    Generate a rule and export it to an XML file.

    Args:
        rule_text (str): The natural language rule to convert to DMN
        output_file (str): The path to save the XML file
    """
    dmn_xml = generate_rule(rule_text)

    # Ensure the output is properly formatted XML
    if not dmn_xml.strip().startswith("<?xml"):
        dmn_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + dmn_xml

    # Write to file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(dmn_xml)

    return output_file
