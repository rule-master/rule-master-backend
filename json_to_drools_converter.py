"""
JSON to Drools Converter for DRL and GDST files - Final Format Version

This module provides functionality to convert JSON schemas into Drools Rule Language (DRL)
and Guided Decision Table (GDST) files.
"""

import os
import re
import json
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional, Tuple
from logger_utils import logger
import sys
    

class JsonToDrlConverter:
    """
    Converts JSON schema to Drools Rule Language (DRL) file.
    """
    
    def __init__(self, json_data: Dict[str, Any]):
        """
        Initialize the converter with JSON data.
        
        Args:
            json_data: Dictionary containing the rule data
        """
        self.json_data = json_data
    
    def convert(self) -> str:
        """
        Convert JSON to DRL format.
        
        Returns:
            String containing the DRL content
        """
        # Extract data from JSON
        rule_name = self.json_data.get("ruleName", "unnamed_rule")
        package_name = self.json_data.get("packageName", "com.myspace.rules")
        imports = self.json_data.get("imports", [])
        salience = self.json_data.get("salience", "10")
        conditions = self.json_data.get("conditions", [])
        actions = self.json_data.get("actions", [])
        
        # Build the DRL content
        drl_content = f"package {package_name};\n\n"
        
        # Add imports
        for import_path in imports:
            drl_content += f"import {import_path};\n"
        
        # Add dialect
        drl_content += "\ndialect \"mvel\";\n\n"
        
        # Add rule
        drl_content += f"rule \"{rule_name}\"\n"
        
        # Add attributes
        drl_content += f"    salience {salience}\n"
        
        # Add when section with conditions
        drl_content += "    when\n"
        for condition in conditions:
            drl_content += f"        {condition}\n"
        
        # Add then section with actions
        drl_content += "    then\n"
        for action in actions:
            drl_content += f"        {action}\n"
        
        # Close rule
        drl_content += "end\n"
        
        return drl_content
    
    def save_to_file(self, output_dir: str, filename: str = None) -> str:
        """
        Save the DRL content to a file.
        
        Args:
            output_dir: Directory to save the file
            filename: Optional filename (without extension)
            
        Returns:
            Path to the saved file
        """
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Use rule name as filename if not provided
        if not filename:
            filename = self.json_data.get("ruleName", "unnamed_rule")
        
        # Generate DRL content
        drl_content = self.convert()
        
        # Save to file
        file_path = os.path.join(output_dir, f"{filename}.drl")
        with open(file_path, "w") as f:
            f.write(drl_content)
        
        return file_path
class JsonToGdstConverter:
    """
    Converts JSON schema to Drools Guided Decision Table (GDST) file.
    """
    
    def __init__(self, json_data: Dict[str, Any]):
        """
        Initialize the converter with JSON data.
        
        Args:
            json_data: Dictionary containing the decision table data
        """
        self.json_data = json_data
        self.root = ET.Element("decision-table52")
        self.column_structure = []  # Track column structure for data alignment
        self.column_count = 0  # Track total column count
        self.brl_condition_indices = []  # Track indices of BRLCondition columns
        self.pattern_condition_indices = []  # Track indices of Pattern condition columns
        self.brl_action_indices = []  # Track indices of BRLAction columns
        self.attribute_indices = {}  # Track indices of attribute columns by name
        
    def convert(self) -> str:
        """
        Convert JSON to GDST XML format.
        
        Returns:
            String containing the formatted XML
        """
        # Reset column structure and count
        self.column_structure = []
        self.column_count = 0
        self.brl_condition_indices = []
        self.pattern_condition_indices = []
        self.brl_action_indices = []
        self.attribute_indices = {}
        
        # Generate the XML structure
        self._generate_gdst_xml()
        
        # Convert to string and format
        xml_str = ET.tostring(self.root, encoding='utf-8', method='xml')
        
        # Format the XML
        formatted_xml = self._format_xml(xml_str)
        
        return formatted_xml
    
    def _format_xml(self, xml_str: str) -> str:
        """
        Format XML for readability.
        
        Args:
            xml_str (str): XML string
            
        Returns:
            str: Formatted XML string
        """
        # Parse XML string
        dom = minidom.parseString(xml_str)
        
        # Pretty print with 2-space indentation
        pretty_xml = dom.toprettyxml(indent="  ")
        
        # Remove XML declaration from pretty_xml if it exists
        if pretty_xml.startswith('<?xml'):
            pretty_xml = pretty_xml[pretty_xml.find('?>')+2:].lstrip()
        
        # # Fix valueString tags to be non-self-closing
        # pretty_xml = pretty_xml.replace("<valueString/>", "<valueString></valueString>")
        
        return pretty_xml
    
    def _generate_gdst_xml(self):
        """Generate the GDST XML structure."""
        # Add table name
        table_name = ET.SubElement(self.root, "tableName")
        table_name.text = self.json_data.get("tableName", "Decision Table")
        
        # Add row number column
        self._add_row_number_column()
        
        # Add description column
        self._add_description_column()
        
        # Add rule name column
        self._add_rule_name_column()
        
        # Add metadata columns
        self._add_metadata_columns()
        
        # Add attribute columns
        self._add_attribute_columns()
        
        # Add condition patterns
        self._add_condition_patterns()
        
        # Add action columns
        self._add_action_columns()
        
        # Add audit log
        self._add_audit_log()
        
        # Add imports
        self._add_imports()
        
        # Add package name
        package_name = ET.SubElement(self.root, "packageName")
        package_name.text = self.json_data.get("packageName", "com.myspace")
        
        # Add version
        version = ET.SubElement(self.root, "version")
        version.text = str(self.json_data.get("version", 739))
        
        # Add table format
        table_format = ET.SubElement(self.root, "tableFormat")
        table_format.text = self.json_data.get("tableFormat", "EXTENDED_ENTRY")
        
        # Add hit policy
        hit_policy = ET.SubElement(self.root, "hitPolicy")
        hit_policy.text = self.json_data.get("hitPolicy", "NONE")
        
        # Add data rows
        self._add_data()
    
    def _add_row_number_column(self):
        """Add row number column."""
        row_number_col = ET.SubElement(self.root, "rowNumberCol")
        
        hide_column = ET.SubElement(row_number_col, "hideColumn")
        hide_column.text = "false"
        
        width = ET.SubElement(row_number_col, "width")
        width.text = "50"
        
        # Add to column structure
        self.column_structure.append(("rowNumber", "NUMERIC_INTEGER"))
        self.column_count += 1
    
    def _add_description_column(self):
        """Add description column."""
        desc_col = ET.SubElement(self.root, "descriptionCol")
        
        hide_column = ET.SubElement(desc_col, "hideColumn")
        hide_column.text = "false"
        
        width = ET.SubElement(desc_col, "width")
        width.text = "150"
        
        # Add to column structure
        self.column_structure.append(("description", "STRING"))
        self.column_count += 1
    
    def _add_rule_name_column(self):
        """Add rule name column."""
        rule_name_col = ET.SubElement(self.root, "ruleNameColumn")
        
        hide_column = ET.SubElement(rule_name_col, "hideColumn")
        hide_column.text = "true"
        
        width = ET.SubElement(rule_name_col, "width")
        width.text = "150"
        
        # Add to column structure
        self.column_structure.append(("ruleName", "STRING"))
        self.column_count += 1
    
    def _add_metadata_columns(self):
        """Add metadata columns."""
        metadata_cols = ET.SubElement(self.root, "metadataCols")
        # No metadata columns in the example
    
    def _add_attribute_columns(self):
        """Add attribute columns."""
        attribute_cols = ET.SubElement(self.root, "attributeCols")
        
        for attr in self.json_data.get("attributes", []):
            # Add all attributes to the column structure
            attr_col = ET.SubElement(attribute_cols, "attribute-column52")
            
            # Add typed default value
            typed_default = ET.SubElement(attr_col, "typedDefaultValue")
            
            # Handle different data types
            if attr["dataType"] == "NUMERIC_INTEGER":
                value_numeric = ET.SubElement(typed_default, "valueNumeric")
                value_numeric.set("class", "int")
                value_numeric.text = str(attr["value"])
                value_string = ET.SubElement(typed_default, "valueString")
                value_string.text = ""
            elif attr["dataType"] == "NUMERIC_DOUBLE":
                value_numeric = ET.SubElement(typed_default, "valueNumeric")
                value_numeric.set("class", "double")
                value_numeric.text = str(attr["value"])
                value_string = ET.SubElement(typed_default, "valueString")
                value_string.text = ""
            elif attr["dataType"] == "BOOLEAN":
                value_boolean = ET.SubElement(typed_default, "valueBoolean")
                value_boolean.text = str(attr["value"]).lower()
                value_string = ET.SubElement(typed_default, "valueString")
                value_string.text = ""
            else:  # STRING
                value_string = ET.SubElement(typed_default, "valueString")
                value_string.text = str(attr["value"]) if attr["value"] is not None else ""
            
            # Add data type
            data_type = ET.SubElement(typed_default, "dataType")
            data_type.text = attr["dataType"]
            
            # Add isOtherwise
            is_otherwise = ET.SubElement(typed_default, "isOtherwise")
            is_otherwise.text = "false"
            
            # Add hide column
            hide_column = ET.SubElement(attr_col, "hideColumn")
            hide_column.text = str(attr.get("hideColumn", "false")).lower()
            
            # Add width
            width = ET.SubElement(attr_col, "width")
            width.text = "130"
            
            # Add attribute name
            attribute = ET.SubElement(attr_col, "attribute")
            attribute.text = attr["name"]
            
            if(attr["name"]=="salience"):
                # Add reverse order
                reverse_order = ET.SubElement(attr_col, "reverseOrder")
                reverse_order.text = "false"
                
                # Add use row number
                use_row_number = ET.SubElement(attr_col, "useRowNumber")
                use_row_number.text = "false"
            
            # Add to column structure
            self.column_structure.append((attr["name"], attr["dataType"]))
            self.attribute_indices[attr["name"]] = self.column_count
            self.column_count += 1
    
    def _add_condition_patterns(self):
        """Add condition patterns to the XML."""
        condition_patterns = ET.SubElement(self.root, "conditionPatterns")
        
        # First add BRL conditions
        for brl_condition in self.json_data.get("conditionsBRL", []):
            self._add_brl_condition_to_patterns(condition_patterns, brl_condition)
        
        # Then add pattern conditions
        for pattern in self.json_data.get("conditionPatterns", []):
            self._add_pattern_condition(condition_patterns, pattern)
    
    def _add_brl_condition_to_patterns(self, parent, brl_condition):
        """Add BRL condition to condition patterns."""
        pattern_element = ET.SubElement(parent, "org.drools.workbench.models.guided.dtable.shared.model.BRLConditionColumn")
        
        # Add BRL condition properties
        header = ET.SubElement(pattern_element, "header")
        header.text = brl_condition.get("header", "")
        
        hide_column = ET.SubElement(pattern_element, "hideColumn")
        hide_column.text = str(brl_condition.get("hidden", "false")).lower()
        
        width = ET.SubElement(pattern_element, "width")
        width.text = str(brl_condition.get("width", "-1"))
        
        constraint_value_type = ET.SubElement(pattern_element, "constraintValueType")
        constraint_value_type.text = str(brl_condition.get("constraintValueType", "1"))
        
        parameters = ET.SubElement(pattern_element, "parameters")
        
        definition = ET.SubElement(pattern_element, "definition")
        
        # Handle definition as either a dict with FreeFormLine or a list of objects
        definition_data = brl_condition.get("definition", [])
        if isinstance(definition_data, dict):
            # Handle FreeFormLine as a dict
            if "FreeFormLine" in definition_data:
                free_form_line = ET.SubElement(definition, "org.drools.workbench.models.datamodel.rule.FreeFormLine")
                text = ET.SubElement(free_form_line, "text")
                text.text = definition_data["FreeFormLine"].get("text", "")
        elif isinstance(definition_data, list):
            # Handle definition as a list of objects
            for line in definition_data:
                free_form_line = ET.SubElement(definition, "org.drools.workbench.models.datamodel.rule.FreeFormLine")
                text = ET.SubElement(free_form_line, "text")
                if isinstance(line, dict) and "text" in line:
                    text.text = line["text"]
                elif isinstance(line, str):
                    text.text = line
                else:
                    text.text = str(line)  # Fallback to string conversion
        
        # Add child columns
        child_columns = ET.SubElement(pattern_element, "childColumns")
        
        # Handle childColumns as either a dict or a list
        child_columns_data = brl_condition.get("childColumns", {})
        if isinstance(child_columns_data, dict):
            # Handle childColumns as a dict
            for column_type, column_data in child_columns_data.items():
                if column_type == "BRLConditionVariableColumn":
                    var_column = ET.SubElement(child_columns, "org.drools.workbench.models.guided.dtable.shared.model.BRLConditionVariableColumn")
                    
                    # Add typed default value
                    typed_default = ET.SubElement(var_column, "typedDefaultValue")
                    
                    # Handle different data types in typedDefaultValue
                    typed_default_data = column_data.get("typedDefaultValue", {})
                    if "valueBoolean" in typed_default_data:
                        value_boolean = ET.SubElement(typed_default, "valueBoolean")
                        value_boolean.text = str(typed_default_data["valueBoolean"]).lower()
                    
                    if "valueString" in typed_default_data:
                        value_string = ET.SubElement(typed_default, "valueString")
                        value_string.text = typed_default_data["valueString"]
                    
                    data_type = ET.SubElement(typed_default, "dataType")
                    data_type.text = typed_default_data.get("dataType", "BOOLEAN")
                    
                    is_otherwise = ET.SubElement(typed_default, "isOtherwise")
                    is_otherwise.text = str(typed_default_data.get("isOtherwise", "false")).lower()
                    
                    # Add other properties
                    hide_column = ET.SubElement(var_column, "hideColumn")
                    hide_column.text = str(column_data.get("hideColumn", "false")).lower()
                    
                    width = ET.SubElement(var_column, "width")
                    width.text = str(column_data.get("width", "100"))
                    
                    header = ET.SubElement(var_column, "header")
                    header.text = column_data.get("header", "")
                    
                    constraint_value_type = ET.SubElement(var_column, "constraintValueType")
                    constraint_value_type.text = str(column_data.get("constraintValueType", "1"))
                    
                    field_type = ET.SubElement(var_column, "fieldType")
                    field_type.text = column_data.get("fieldType", "Boolean")
                    
                    parameters = ET.SubElement(var_column, "parameters")
                    
                    var_name = ET.SubElement(var_column, "varName")
                    var_name.text = column_data.get("varName", "")
                    
                    # Add to column structure
                    self.column_structure.append((column_data.get("header", ""), "BOOLEAN"))
                    self.column_count += 1
                    self.brl_condition_indices.append(self.column_count - 1)
        elif isinstance(child_columns_data, list):
            # Handle childColumns as a list
            for column_data in child_columns_data:
                var_column = ET.SubElement(child_columns, "org.drools.workbench.models.guided.dtable.shared.model.BRLConditionVariableColumn")
                
                # Add typed default value
                typed_default = ET.SubElement(var_column, "typedDefaultValue")
                
                # Handle different data types in typedDefaultValue
                typed_default_data = column_data.get("typedDefaultValue", {})
                if "valueBoolean" in typed_default_data:
                    value_boolean = ET.SubElement(typed_default, "valueBoolean")
                    value_boolean.text = str(typed_default_data["valueBoolean"]).lower()
                
                if "valueString" in typed_default_data:
                    value_string = ET.SubElement(typed_default, "valueString")
                    value_string.text = typed_default_data["valueString"]
                
                data_type = ET.SubElement(typed_default, "dataType")
                data_type.text = typed_default_data.get("dataType", "BOOLEAN")
                
                is_otherwise = ET.SubElement(typed_default, "isOtherwise")
                is_otherwise.text = str(typed_default_data.get("isOtherwise", "false")).lower()
                
                # Add other properties
                hide_column = ET.SubElement(var_column, "hideColumn")
                hide_column.text = str(column_data.get("hideColumn", "false")).lower()
                
                width = ET.SubElement(var_column, "width")
                width.text = str(column_data.get("width", "100"))
                
                header = ET.SubElement(var_column, "header")
                header.text = column_data.get("header", "")
                
                constraint_value_type = ET.SubElement(var_column, "constraintValueType")
                constraint_value_type.text = str(column_data.get("constraintValueType", "1"))
                
                field_type = ET.SubElement(var_column, "fieldType")
                field_type.text = column_data.get("fieldType", "Boolean")
                
                parameters = ET.SubElement(var_column, "parameters")
                
                var_name = ET.SubElement(var_column, "varName")
                var_name.text = column_data.get("varName", "")
                
                # Add to column structure
                self.column_structure.append((column_data.get("header", ""), "BOOLEAN"))
                self.column_count += 1
                self.brl_condition_indices.append(self.column_count - 1)
    
    def _add_pattern_condition(self, parent, pattern):
        """Add pattern condition to the XML."""
        pattern_element = ET.SubElement(parent, "Pattern52")
        
        # Add fact type
        fact_type = ET.SubElement(pattern_element, "factType")
        fact_type.text = pattern.get("factType", "")
        
        # Add bound name
        bound_name = ET.SubElement(pattern_element, "boundName")
        bound_name.text = pattern.get("boundName", "")
        
        # Add is negated
        is_negated = ET.SubElement(pattern_element, "isNegated")
        is_negated.text = str(pattern.get("isNegated", "false")).lower()
        
        # Add conditions
        conditions = ET.SubElement(pattern_element, "conditions")
        
        for condition in pattern.get("conditions", []):
            condition_col = ET.SubElement(conditions, "condition-column52")
            
            # Add typed default value
            typed_default = ET.SubElement(condition_col, "typedDefaultValue")
            
            # Create default typedDefaultValue if missing
            default_typed_value = {
                "valueString": "",
                "dataType": self._get_data_type_from_field_type(condition.get("fieldType", "String")),
                "isOtherwise": False
            }
            
            # Use provided typedDefaultValue or create one based on fieldType
            typed_default_value = condition.get("typedDefaultValue", default_typed_value)
            
            # # Handle different data types
            # data_type = typed_default_value.get("dataType", self._get_data_type_from_field_type(condition.get("fieldType", "String")))
            
            # if data_type == "NUMERIC_INTEGER" or data_type == "NUMERIC_DOUBLE":
            #     value_numeric = ET.SubElement(typed_default, "valueNumeric")
            #     if data_type == "NUMERIC_INTEGER":
            #         value_numeric.set("class", "int")
            #     else:
            #         value_numeric.set("class", "double")
            #     numeric_value = typed_default_value.get("valueNumeric")
            #     if numeric_value is not None and numeric_value != "":
            #         value_numeric.text = str(numeric_value.get("value"))
            #     else:
            #         value_numeric.text = "0" if data_type == "NUMERIC_INTEGER" else "0.0"
            
            data_type = typed_default_value.get("dataType", self._get_data_type_from_field_type(condition.get("fieldType", "String")))
            if data_type == "NUMERIC_INTEGER" or data_type == "NUMERIC_DOUBLE":
                value_numeric = ET.SubElement(typed_default, "valueNumeric")
                if data_type == "NUMERIC_INTEGER":
                    value_numeric.set("class", "int")
                else:
                    value_numeric.set("class", "double")
                numeric_value = typed_default_value.get("valueNumeric")
                if numeric_value is not None and numeric_value != "":
                    if isinstance(numeric_value, dict):
                        numeric_value_text = numeric_value.get("value")
                        if(numeric_value_text is not None and numeric_value_text != ""):
                            value_numeric.text = str(numeric_value_text)
                    else:
                        value_numeric.text = str(numeric_value.get("value"))
                else:
                    value_numeric.text = "0" if data_type == "NUMERIC_INTEGER" else "0.0"
            
            value_string = ET.SubElement(typed_default, "valueString")
            value_string.text = typed_default_value.get("valueString", "")
            
            data_type_element = ET.SubElement(typed_default, "dataType")
            data_type_element.text = data_type
            
            is_otherwise = ET.SubElement(typed_default, "isOtherwise")
            is_otherwise.text = str(typed_default_value.get("isOtherwise", "false")).lower()
            
            # Add hide column
            hide_column = ET.SubElement(condition_col, "hideColumn")
            hide_column.text = str(condition.get("hidden", "false")).lower()
            
            # Add width
            width = ET.SubElement(condition_col, "width")
            width.text = str(condition.get("width", "100"))
            
            # Add header
            header = ET.SubElement(condition_col, "header")
            header.text = condition.get("header", "")
            
            # Add constraint value type
            constraint_value_type = ET.SubElement(condition_col, "constraintValueType")
            constraint_value_type.text = "1"
            
            # Add fact field
            fact_field = ET.SubElement(condition_col, "factField")
            fact_field.text = condition.get("factField", "")
            
            # Add field type
            field_type = ET.SubElement(condition_col, "fieldType")
            field_type.text = condition.get("fieldType", "String")
            
            # Add operator
            operator = ET.SubElement(condition_col, "operator")
            operator.text = condition.get("operator", "==")
            
            # Add parameters
            parameters = ET.SubElement(condition_col, "parameters")
            
            # Add binding
            binding = ET.SubElement(condition_col, "binding")
            binding.text = condition.get("binding", "")
            
            # Add to column structure
            self.column_structure.append((condition.get("header", ""), data_type))
            self.column_count += 1
            self.pattern_condition_indices.append(self.column_count - 1)
        
        # Add window
        window = ET.SubElement(pattern_element, "window")
        parameters = ET.SubElement(window, "parameters")
        
        # Add entry point name
        entry_point_name = ET.SubElement(pattern_element, "entryPointName")
        entry_point_name.text = ""
    
    def _get_data_type_from_field_type(self, field_type):
        """Convert field type to data type."""
        if field_type == "Integer":
            return "NUMERIC_INTEGER"
        elif field_type == "Double":
            return "NUMERIC_DOUBLE"
        elif field_type == "Boolean":
            return "BOOLEAN"
        else:
            return "STRING"
    
    def _add_action_columns(self):
        """Add action columns to the XML."""
        action_cols = ET.SubElement(self.root, "actionCols")
        
        for action in self.json_data.get("actionColumns", []):
            if action.get("type") == "BRLAction":
                self._add_brl_action(action_cols, action)
    
    def _add_brl_action(self, parent, action):
        """Add BRL action to the XML."""
        brl_action = ET.SubElement(parent, "org.drools.workbench.models.guided.dtable.shared.model.BRLActionColumn")
        
        # Add hide column
        hide_column = ET.SubElement(brl_action, "hideColumn")
        hide_column.text = str(action.get("hidden", "false")).lower()
        
        # Add width
        width = ET.SubElement(brl_action, "width")
        width.text = str(action.get("width", "-1"))
        
        # Add header
        header = ET.SubElement(brl_action, "header")
        header.text = action.get("header", "")
        
        # Add definition
        definition = ET.SubElement(brl_action, "definition")
        
        # Handle definition as either a dict with FreeFormLine or a list of objects
        definition_data = action.get("definition", [])
        if isinstance(definition_data, dict):
            # Handle FreeFormLine as a dict
            if "FreeFormLine" in definition_data:
                free_form_line = ET.SubElement(definition, "org.drools.workbench.models.datamodel.rule.FreeFormLine")
                text = ET.SubElement(free_form_line, "text")
                text.text = definition_data["FreeFormLine"].get("text", "")
        elif isinstance(definition_data, list):
            # Handle definition as a list of objects
            for line in definition_data:
                free_form_line = ET.SubElement(definition, "org.drools.workbench.models.datamodel.rule.FreeFormLine")
                text = ET.SubElement(free_form_line, "text")
                if isinstance(line, dict) and "text" in line:
                    text.text = line["text"]
                elif isinstance(line, str):
                    text.text = line
                else:
                    text.text = str(line)  # Fallback to string conversion
        
        # Add child columns
        child_columns = ET.SubElement(brl_action, "childColumns")
        
        # Extract variable names from definition
        var_names = self._extract_variable_names(definition_data)
        
        if var_names:
            # Add variable column for each variable
            for var_name in var_names:
                var_column = ET.SubElement(child_columns, "org.drools.workbench.models.guided.dtable.shared.model.BRLActionVariableColumn")
                
                # Add typed default value
                typed_default = ET.SubElement(var_column, "typedDefaultValue")
                
                # Get field type
                field_type = action["childColumns"]["BRLActionVariableColumn"].get("fieldType", "")
                
                # Add value based on field type
                if field_type.lower() in ["boolean", "bool"]:
                    value_boolean = ET.SubElement(typed_default, "valueBoolean")
                    value_boolean.text = "false"
                    data_type_text = "BOOLEAN"
                elif field_type.lower() in ["integer", "int", "long"]:
                    value_numeric = ET.SubElement(typed_default, "valueNumeric")
                    value_numeric.set("class", "int")
                    value_numeric.text = "0"
                    data_type_text = "NUMERIC_INTEGER"
                elif field_type.lower() in ["double", "float", "decimal", "number"]:
                    value_numeric = ET.SubElement(typed_default, "valueNumeric")
                    value_numeric.set("class", "double")
                    value_numeric.text = "0.0"
                    data_type_text = "NUMERIC_DOUBLE"
                else:
                    value_string = ET.SubElement(typed_default, "valueString")
                    data_type_text = "STRING"
                
                # # Default to STRING data type
                value_string = ET.SubElement(typed_default, "valueString")
                value_string.text = ""
                
                data_type = ET.SubElement(typed_default, "dataType")
                data_type.text = data_type_text
                
                is_otherwise = ET.SubElement(typed_default, "isOtherwise")
                is_otherwise.text = "false"
                
                # Add hide column
                hide_column = ET.SubElement(var_column, "hideColumn")
                hide_column.text = "false"
                
                # Add width
                width = ET.SubElement(var_column, "width")
                width.text = "100"
                
                # Add header
                header = ET.SubElement(var_column, "header")
                header.text = var_name
                
                # Add var name
                var_name_element = ET.SubElement(var_column, "varName")
                var_name_element.text = var_name
                
                # Add field type
                field_type_element = ET.SubElement(var_column, "fieldType")
                field_type_element.text = field_type
                
                # Add to column structure
                self.column_structure.append((var_name, data_type))
                self.column_count += 1
                self.brl_action_indices.append(self.column_count - 1)
        else:
            # Add a default variable column if no variables found
            var_column = ET.SubElement(child_columns, "org.drools.workbench.models.guided.dtable.shared.model.BRLActionVariableColumn")
            
            # Add typed default value
            typed_default = ET.SubElement(var_column, "typedDefaultValue")
            value_string = ET.SubElement(typed_default, "valueString")
            value_string.text = ""
            data_type = ET.SubElement(typed_default, "dataType")
            data_type.text = "STRING"
            is_otherwise = ET.SubElement(typed_default, "isOtherwise")
            is_otherwise.text = "false"
            
            # Add hide column
            hide_column = ET.SubElement(var_column, "hideColumn")
            hide_column.text = "false"
            
            # Add width
            width = ET.SubElement(var_column, "width")
            width.text = "100"
            
            # Add header
            header = ET.SubElement(var_column, "header")
            header.text = action.get("header", "")
            
            # Add var name
            var_name_element = ET.SubElement(var_column, "varName")
            var_name_element.text = action.get("header", "")
            
            # Add field type
            field_type = ET.SubElement(var_column, "fieldType")
            field_type.text = "Object"
            
            # Add to column structure
            self.column_structure.append((action.get("header", ""), "STRING"))
            self.column_count += 1
            self.brl_action_indices.append(self.column_count - 1)
    
    def _extract_variable_names(self, definition_data):
        """Extract variable names from BRL definition."""
        var_names = []
        
        if isinstance(definition_data, list):
            for item in definition_data:
                if isinstance(item, str):
                    # Look for @{VarName} pattern
                    matches = re.findall(r'@\{([^}]+)\}', item)
                    var_names.extend(matches)
                elif isinstance(item, dict) and "text" in item:
                    # Look for @{VarName} pattern in text field
                    matches = re.findall(r'@\{([^}]+)\}', item["text"])
                    var_names.extend(matches)
        elif isinstance(definition_data, dict) and "FreeFormLine" in definition_data:
            text = definition_data["FreeFormLine"].get("text", "")
            matches = re.findall(r'@\{([^}]+)\}', text)
            var_names.extend(matches)
        
        return var_names
    
    def _add_audit_log(self):
        """Add audit log to the XML."""
        audit_log = ET.SubElement(self.root, "auditLog")
        
        # Add filter
        filter_element = ET.SubElement(audit_log, "filter")
        filter_element.set("class", "org.drools.guvnor.client.modeldriven.dt52.auditlog.DecisionTableAuditLogFilter")
        
        # Add acceptedTypes
        accepted_types = ET.SubElement(filter_element, "acceptedTypes")
        
        # Add entries
        self._add_audit_log_entry(accepted_types, "INSERT_ROW", "false")
        self._add_audit_log_entry(accepted_types, "INSERT_COLUMN", "false")
        self._add_audit_log_entry(accepted_types, "DELETE_ROW", "false")
        self._add_audit_log_entry(accepted_types, "DELETE_COLUMN", "false")
        self._add_audit_log_entry(accepted_types, "UPDATE_COLUMN", "false")
        
        # Add entries
        entries = ET.SubElement(audit_log, "entries")
    
    def _add_audit_log_entry(self, parent, string_value, boolean_value):
        """Add an entry to the audit log acceptedTypes."""
        entry = ET.SubElement(parent, "entry")
        
        string_element = ET.SubElement(entry, "string")
        string_element.text = string_value
        
        boolean_element = ET.SubElement(entry, "boolean")
        boolean_element.text = boolean_value
    
    def _add_imports(self):
        """Add imports to the XML."""
        imports_container = ET.SubElement(self.root, "imports")
        imports = ET.SubElement(imports_container, "imports")
        
        for import_path in self.json_data.get("imports", []):
            import_element = ET.SubElement(imports, "org.kie.soup.project.datamodel.imports.Import")
            type_element = ET.SubElement(import_element, "type")
            type_element.text = import_path
    
    def _add_data(self):
        """Add data rows to the XML."""
        data_element = ET.SubElement(self.root, "data")
        
        # Process each data row
        for row_data in self.json_data.get("data", []):
            list_element = ET.SubElement(data_element, "list")
            
            # Create a dictionary of values by column name for easy lookup
            values_dict = {value.get("columnName"): value for value in row_data.get("values", [])}
            
            # 1. Row Number (always first) - using the exact structure provided
            self._add_row_number_value(list_element, row_data.get("rowNumber", 1))
            
            # 2. Description (always second) - using the exact structure provided
            self._add_description_value(list_element, row_data.get("description", ""))
            
            # 3. Rule Name (always third, usually empty) - using the exact structure provided
            self._add_rule_name_value(list_element, "")
            
            # 4. Attributes - include salience but skip enabled
            for attr in self.json_data.get("attributes", []):
                attr_name = attr["name"]
                
                # Skip enabled attribute in data rows
                if attr_name == "enabled":
                    continue
                
                # For salience and other attributes (except enabled)
                if attr_name in values_dict:
                    value_data = values_dict[attr_name]
                    self._add_value_element(list_element, value_data.get("value"), value_data.get("dataType", attr["dataType"]))
                else:
                    # Use default from attribute definition
                    self._add_value_element(list_element, attr.get("value"), attr["dataType"])
            
            # 5. BRL Conditions (recommendation, restaurantData, etc.)
            for brl_index in self.brl_condition_indices:
                col_name, col_type = self.column_structure[brl_index]
                if col_name in values_dict:
                    value_data = values_dict[col_name]
                    self._add_value_element(list_element, value_data.get("value", True), value_data.get("dataType", col_type))
                else:
                    # Default to true for BRL conditions
                    self._add_value_element(list_element, True, col_type)
            
            # 6. Pattern Conditions (Max Sales, Min Sales, etc.)
            for pattern_index in self.pattern_condition_indices:
                col_name, col_type = self.column_structure[pattern_index]
                if col_name in values_dict:
                    value_data = values_dict[col_name]
                    self._add_value_element(list_element, value_data.get("value"), value_data.get("dataType", col_type))
                else:
                    # Use empty value for pattern conditions
                    self._add_value_element(list_element, None, col_type)
            
            # 7. BRL Actions (count, etc.)
            for action_index in self.brl_action_indices:
                col_name, col_type = self.column_structure[action_index]
                if col_name in values_dict:
                    value_data = values_dict[col_name]
                    self._add_value_element(list_element, value_data.get("value"), value_data.get("dataType", col_type))
                    #self._add_value_element(list_element, value_data.get("value"), "STRING")
                else:
                    # Use default from action definition
                    self._add_value_element(list_element, None, col_type)
    
    def _add_row_number_value(self, parent, value):
        """Add row number value with exact structure."""
        row_number_value = ET.SubElement(parent, "value")
        
        value_numeric = ET.SubElement(row_number_value, "valueNumeric")
        value_numeric.set("class", "int")
        value_numeric.text = str(value)
        
        value_string = ET.SubElement(row_number_value, "valueString")
        
        data_type = ET.SubElement(row_number_value, "dataType")
        data_type.text = "NUMERIC_INTEGER"
        
        is_otherwise = ET.SubElement(row_number_value, "isOtherwise")
        is_otherwise.text = "false"
    
    def _add_description_value(self, parent, value):
        """Add description value with exact structure."""
        description_value = ET.SubElement(parent, "value")
        
        value_string = ET.SubElement(description_value, "valueString")
        value_string.text = value
        
        data_type = ET.SubElement(description_value, "dataType")
        data_type.text = "STRING"
        
        is_otherwise = ET.SubElement(description_value, "isOtherwise")
        is_otherwise.text = "false"
    
    def _add_rule_name_value(self, parent, value):
        """Add rule name value with exact structure."""
        rule_name_value = ET.SubElement(parent, "value")
        
        value_string = ET.SubElement(rule_name_value, "valueString")
        
        data_type = ET.SubElement(rule_name_value, "dataType")
        data_type.text = "STRING"
        
        is_otherwise = ET.SubElement(rule_name_value, "isOtherwise")
        is_otherwise.text = "false"
    
    def _add_value_element(self, parent, value, data_type, numeric_class=None):
        """Add a value element to the XML."""
        value_element = ET.SubElement(parent, "value")
        
        if data_type == "NUMERIC_INTEGER" and value is not None:
            value_numeric = ET.SubElement(value_element, "valueNumeric")
            if numeric_class:
                value_numeric.set("class", numeric_class)
            else:
                value_numeric.set("class", "int")
            value_numeric.text = str(value)
            value_string = ET.SubElement(value_element, "valueString")
            value_string.text = ""
        elif data_type == "NUMERIC_DOUBLE" and value is not None:
            value_numeric = ET.SubElement(value_element, "valueNumeric")
            if numeric_class:
                value_numeric.set("class", numeric_class)
            else:
                value_numeric.set("class", "double")
            value_numeric.text = str(value)
            value_string = ET.SubElement(value_element, "valueString")
            value_string.text = ""
        elif data_type == "BOOLEAN":
            value_boolean = ET.SubElement(value_element, "valueBoolean")
            value_boolean.text = str(value).lower() if value is not None else "false"
            value_string = ET.SubElement(value_element, "valueString")
            value_string.text = ""
        else:  # STRING
            value_string = ET.SubElement(value_element, "valueString")
            value_string.text = str(value) if value is not None else ""
        
        data_type_element = ET.SubElement(value_element, "dataType")
        data_type_element.text = data_type
        
        is_otherwise = ET.SubElement(value_element, "isOtherwise")
        is_otherwise.text = "false"
    
    def save_to_file(self, output_dir: str, filename: str = None) -> str:
        """
        Save the GDST content to a file.
        
        Args:
            output_dir: Directory to save the file
            filename: Optional filename (without extension)
            
        Returns:
            Path to the saved file
        """
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Use table name as filename if not provided
        if not filename:
            filename = self.json_data.get("tableName", "unnamed_table").replace(" ", "_")
        
        # Generate GDST content
        gdst_content = self.convert()
        
        # Save to file
        file_path = os.path.join(output_dir, f"{filename}.gdst")
        with open(file_path, "w") as f:
            f.write(gdst_content)
        
        return file_path

def convert_json_to_drools(json_data: Dict[str, Any], output_dir: str, rule_type: str,filename: str = None) -> str:
    """
    Convert JSON to Drools file (DRL or GDST).
    
    Args:
        json_data: Dictionary containing the rule data
        output_dir: Directory to save the file
        filename: Optional filename (without extension)
        
    Returns:
        Path to the saved file
    """
    
    logger.info(f"Converting JSON to Drools {rule_type.upper()} file...")
    
    # Determine the type of rule
    if rule_type == "gdst":
        # This is a decision table (GDST)
        converter = JsonToGdstConverter(json_data)
    else:
        # This is a simple rule (DRL)
        converter = JsonToDrlConverter(json_data)
    
    # Save to file
    return converter.save_to_file(output_dir, filename)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python json_to_drools_converter_final_format.py <input_json_file> <output_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    # Load JSON data
    with open(input_file, "r") as f:
        json_data = json.load(f)
    
    # Determine output directory and filename
    output_dir = os.path.dirname(output_file)
    if not output_dir:
        output_dir = "."
    
    filename = os.path.basename(output_file)
    if "." in filename:
        filename = filename.split(".")[0]
    
    # Convert and save
    saved_file = convert_json_to_drools(json_data, output_dir, filename)
    
    print(f"Converted {input_file} to {saved_file}")