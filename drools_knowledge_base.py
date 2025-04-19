import json
from typing import Dict, List

# Structure to store key Drools concepts and examples
DROOLS_KNOWLEDGE_BASE = {
    "rule_patterns": {
        "basic_condition": {
            "description": "Basic rule with a single condition",
            "example": 'rule "BasicRule"\n    when\n        $fact : FactType( field == value )\n    then\n        // actions\nend',
            "natural_language_pattern": "If {condition} then {action}",
        },
        "multiple_conditions": {
            "description": "Rule with multiple conditions",
            "example": 'rule "MultipleConditions"\n    when\n        $fact1 : FactType1( field1 == value1 )\n        $fact2 : FactType2( field2 == value2 )\n    then\n        // actions\nend',
            "natural_language_pattern": "If {condition1} and {condition2} then {action}",
        },
        "not_condition": {
            "description": "Rule with a NOT condition",
            "example": 'rule "NotCondition"\n    when\n        not FactType( field == value )\n    then\n        // actions\nend',
            "natural_language_pattern": "If not {condition} then {action}",
        },
    },
    "dmn_patterns": {
        "decision_table": {
            "description": "DMN decision table pattern with proper XML structure",
            "example": """<?xml version="1.0" encoding="UTF-8"?>
<dmn:definitions xmlns="https://www.drools.org/kie-dmn/LoanApproval"
    xmlns:dmn="http://www.omg.org/spec/DMN/20151101/dmn.xsd"
    xmlns:feel="http://www.omg.org/spec/FEEL/20140401"
    id="_loan_approval"
    name="loan-approval"
    namespace="https://www.drools.org/kie-dmn/LoanApproval">

  <dmn:itemDefinition id="_tLoanApplication" name="tLoanApplication">
    <dmn:itemComponent id="_tLoanApplication_CreditScore" name="Credit Score">
      <dmn:typeRef>feel:number</dmn:typeRef>
    </dmn:itemComponent>
    <dmn:itemComponent id="_tLoanApplication_Income" name="Income">
      <dmn:typeRef>feel:number</dmn:typeRef>
    </dmn:itemComponent>
    <dmn:itemComponent id="_tLoanApplication_DebtToIncome" name="Debt to Income Ratio">
      <dmn:typeRef>feel:number</dmn:typeRef>
    </dmn:itemComponent>
  </dmn:itemDefinition>

  <dmn:inputData id="i_Loan_Application" name="Loan Application">
    <dmn:variable name="Loan Application" typeRef="tLoanApplication"/>
  </dmn:inputData>

  <dmn:decision id="d_LoanApproval" name="Loan Approval Decision">
    <dmn:variable name="Loan Approval" typeRef="feel:string"/>
    <dmn:variable name="Interest Rate" typeRef="feel:number"/>
    
    <dmn:informationRequirement>
      <dmn:requiredInput href="#i_Loan_Application"/>
    </dmn:informationRequirement>
    
    <dmn:decisionTable id="dt_LoanApproval" hitPolicy="UNIQUE">
      <dmn:input id="dt_i_CreditScore" label="Credit Score">
        <dmn:inputExpression typeRef="feel:number">
          <dmn:text>Loan Application.Credit Score</dmn:text>
        </dmn:inputExpression>
      </dmn:input>
      
      <dmn:input id="dt_i_Income" label="Income">
        <dmn:inputExpression typeRef="feel:number">
          <dmn:text>Loan Application.Income</dmn:text>
        </dmn:inputExpression>
      </dmn:input>
      
      <dmn:input id="dt_i_DebtToIncome" label="Debt to Income Ratio">
        <dmn:inputExpression typeRef="feel:number">
          <dmn:text>Loan Application.Debt to Income</dmn:text>
        </dmn:inputExpression>
      </dmn:input>
      
      <dmn:output id="dt_o_Approval" label="Approval" typeRef="feel:string"/>
      <dmn:output id="dt_o_InterestRate" label="Interest Rate" typeRef="feel:number"/>
      
      <dmn:rule id="dt_r1">
        <dmn:inputEntry id="dt_r1_i1">
          <dmn:text>&gt;=700</dmn:text>
        </dmn:inputEntry>
        <dmn:inputEntry id="dt_r1_i2">
          <dmn:text>&gt;=50000</dmn:text>
        </dmn:inputEntry>
        <dmn:inputEntry id="dt_r1_i3">
          <dmn:text>&lt;0.4</dmn:text>
        </dmn:inputEntry>
        <dmn:outputEntry id="dt_r1_o1">
          <dmn:text>"APPROVED"</dmn:text>
        </dmn:outputEntry>
        <dmn:outputEntry id="dt_r1_o2">
          <dmn:text>3.5</dmn:text>
        </dmn:outputEntry>
      </dmn:rule>
    </dmn:decisionTable>
  </dmn:decision>
</dmn:definitions>""",
            "natural_language_pattern": "If {input1} {operator1} {value1} and {input2} {operator2} {value2} and {input3} {operator3} {value3} then {output1} is {result1} and {output2} is {result2}",
        }
    },
    "common_operators": {
        "comparison": ["==", "!=", "<", ">", "<=", ">="],
        "logical": ["and", "or", "not"],
        "arithmetic": ["+", "-", "*", "/", "%"],
    },
}


def get_rule_pattern(pattern_name: str) -> Dict:
    """Get a specific rule pattern from the knowledge base."""
    return DROOLS_KNOWLEDGE_BASE["rule_patterns"].get(pattern_name)


def get_dmn_pattern(pattern_name: str) -> Dict:
    """Get a specific DMN pattern from the knowledge base."""
    return DROOLS_KNOWLEDGE_BASE["dmn_patterns"].get(pattern_name)


def get_operators(operator_type: str) -> List[str]:
    """Get operators of a specific type."""
    return DROOLS_KNOWLEDGE_BASE["common_operators"].get(operator_type, [])


def save_knowledge_base(file_path: str = "drools_knowledge_base.json"):
    """Save the knowledge base to a JSON file."""
    with open(file_path, "w") as f:
        json.dump(DROOLS_KNOWLEDGE_BASE, f, indent=2)


def load_knowledge_base(file_path: str = "drools_knowledge_base.json"):
    """Load the knowledge base from a JSON file."""
    global DROOLS_KNOWLEDGE_BASE
    with open(file_path, "r") as f:
        DROOLS_KNOWLEDGE_BASE = json.load(f)
