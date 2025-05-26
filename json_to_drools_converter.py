"""
JSON to Drools Converter for DRL and GDST files

This module provides functionality to convert JSON schemas into Drools Rule Language (DRL)
and Guided Decision Table (GDST) files.
"""

import os
import re
import json
import xml.dom.minidom
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional

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
        attributes = self.json_data.get("attributes", {})
        globals = self.json_data.get("globals", [])
        conditions = self.json_data.get("conditions", [])
        actions = self.json_data.get("actions", [])
        
        # Build the DRL content
        drl_content = f"package {package_name};\n\n"
        
        # Add imports
        for import_path in imports:
            drl_content += f"import {import_path};\n"
        
        # Add globals
        for global_var in globals:
            drl_content += f"global {global_var};\n"
        
        # Add dialect
        drl_content += "\ndialect \"mvel\";\n\n"
        
        # Add rule
        drl_content += f"rule \"{rule_name}\"\n"
        
        # Add attributes
        for attr_name, attr_value in attributes.items():
            if attr_value is not None:
                if isinstance(attr_value, bool):
                    drl_content += f"    {attr_name} {str(attr_value).lower()}\n"
                else:
                    drl_content += f"    {attr_name} {attr_value}\n"
        
        # Add when section with conditions
        drl_content += "when\n"
        for condition in conditions:
            drl_content += f"    {condition}\n"
        
        # Add then section with actions
        drl_content += "then\n"
        for action in actions:
            drl_content += f"    {action}\n"
        
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
        
    def convert(self) -> str:
        """
        Convert JSON to GDST XML format.
        
        Returns:
            String containing the formatted XML
        """
        # Add table name
        self._add_table_name()
        
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
        self._add_package_name()
        
        # Add version
        self._add_version()
        
        # Add table format
        self._add_table_format()
        
        # Add hit policy
        self._add_hit_policy()
        
        # Add data
        self._add_data()
        
        # Convert to string and format
        xml_str = ET.tostring(self.root, encoding='utf-8', method='xml')
        dom = xml.dom.minidom.parseString(xml_str)
        return dom.toprettyxml(indent="  ")
    
    def _add_table_name(self):
        """Add table name to the XML."""
        table_name = ET.SubElement(self.root, "tableName")
        table_name.text = self.json_data.get("tableName", "")
    
    def _add_row_number_column(self):
        """Add row number column to the XML."""
        row_number_col = ET.SubElement(self.root, "rowNumberCol")
        hide_column = ET.SubElement(row_number_col, "hideColumn")
        hide_column.text = "false"
        width = ET.SubElement(row_number_col, "width")
        width.text = "50"
    
    def _add_description_column(self):
        """Add description column to the XML."""
        desc_col = ET.SubElement(self.root, "descriptionCol")
        hide_column = ET.SubElement(desc_col, "hideColumn")
        hide_column.text = "false"
        width = ET.SubElement(desc_col, "width")
        width.text = "150"
    
    def _add_rule_name_column(self):
        """Add rule name column to the XML."""
        rule_name_col = ET.SubElement(self.root, "ruleNameColumn")
        hide_column = ET.SubElement(rule_name_col, "hideColumn")
        hide_column.text = "true"
        width = ET.SubElement(rule_name_col, "width")
        width.text = "150"
    
    def _add_metadata_columns(self):
        """Add metadata columns to the XML."""
        metadata_cols = ET.SubElement(self.root, "metadataCols")
        # Add any metadata columns if present in JSON
    
    def _add_attribute_columns(self):
        """Add attribute columns to the XML."""
        attribute_cols = ET.SubElement(self.root, "attributeCols")
        
        for attr in self.json_data.get("attributes", []):
            attr_col = ET.SubElement(attribute_cols, "attribute-column52")
            
            # Add typed default value
            typed_default = ET.SubElement(attr_col, "typedDefaultValue")
            
            # Handle different data types
            if attr["dataType"] == "NUMERIC_INTEGER":
                if attr["value"] is not None:
                    value_numeric = ET.SubElement(typed_default, "valueNumeric")
                    value_numeric.set("class", "int")
                    value_numeric.text = str(attr["value"])
            elif attr["dataType"] == "NUMERIC_DOUBLE":
                if attr["value"] is not None:
                    value_numeric = ET.SubElement(typed_default, "valueNumeric")
                    value_numeric.set("class", "double")
                    value_numeric.text = str(attr["value"])
            elif attr["dataType"] == "BOOLEAN":
                value_boolean = ET.SubElement(typed_default, "valueBoolean")
                value_boolean.text = str(attr["value"]).lower() if attr["value"] is not None else "false"
            else:
                value_string = ET.SubElement(typed_default, "valueString")
                value_string.text = str(attr["value"]) if attr["value"] is not None else ""
            
            # Add empty valueString element (required by Drools)
            if attr["dataType"] != "STRING":
                value_string = ET.SubElement(typed_default, "valueString")
                value_string.text = ""
            
            # Add data type
            data_type = ET.SubElement(typed_default, "dataType")
            data_type.text = attr["dataType"]
            
            # Add isOtherwise
            is_otherwise = ET.SubElement(typed_default, "isOtherwise")
            is_otherwise.text = "false"
            
            # Add hide column
            hide_column = ET.SubElement(attr_col, "hideColumn")
            hide_column.text = str(attr.get("hidden", "false")).lower()
            
            # Add width
            width = ET.SubElement(attr_col, "width")
            width.text = "130"
            
            # Add attribute name
            attribute = ET.SubElement(attr_col, "attribute")
            attribute.text = attr["name"]
            
            # Add reverse order
            reverse_order = ET.SubElement(attr_col, "reverseOrder")
            reverse_order.text = "false"
            
            # Add use row number
            use_row_number = ET.SubElement(attr_col, "useRowNumber")
            use_row_number.text = "false"
    
    def _add_condition_patterns(self):
        """Add condition patterns to the XML."""
        condition_patterns = ET.SubElement(self.root, "conditionPatterns")
        
        for pattern in self.json_data.get("conditionPatterns", []):
            if pattern["type"] == "BRLCondition":
                self._add_brl_condition(condition_patterns, pattern)
            elif pattern["type"] == "Pattern":
                self._add_pattern_condition(condition_patterns, pattern)
    
    def _add_brl_condition(self, parent, pattern):
        """Add BRL condition to the XML."""
        brl_condition = ET.SubElement(parent, "org.drools.workbench.models.guided.dtable.shared.model.BRLConditionColumn")
        
        # Add hide column
        hide_column = ET.SubElement(brl_condition, "hideColumn")
        hide_column.text = str(pattern.get("hidden", "false")).lower()
        
        # Add width
        width = ET.SubElement(brl_condition, "width")
        width.text = "-1"
        
        # Add header
        header = ET.SubElement(brl_condition, "header")
        header.text = pattern["header"]
        
        # Add constraint value type
        constraint_value_type = ET.SubElement(brl_condition, "constraintValueType")
        constraint_value_type.text = "1"
        
        # Add parameters
        parameters = ET.SubElement(brl_condition, "parameters")
        
        # Add definition
        definition = ET.SubElement(brl_condition, "definition")
        
        for line in pattern["definition"]:
            free_form_line = ET.SubElement(definition, "org.drools.workbench.models.datamodel.rule.FreeFormLine")
            text = ET.SubElement(free_form_line, "text")
            text.text = line
        
        # Add child columns
        child_columns = ET.SubElement(brl_condition, "childColumns")
        
        # Add variable column
        var_column = ET.SubElement(child_columns, "org.drools.workbench.models.guided.dtable.shared.model.BRLConditionVariableColumn")
        
        # Add typed default value for variable column
        typed_default = ET.SubElement(var_column, "typedDefaultValue")
        value_boolean = ET.SubElement(typed_default, "valueBoolean")
        value_boolean.text = "true"
        value_string = ET.SubElement(typed_default, "valueString")
        value_string.text = ""
        data_type = ET.SubElement(typed_default, "dataType")
        data_type.text = "BOOLEAN"
        is_otherwise = ET.SubElement(typed_default, "isOtherwise")
        is_otherwise.text = "false"
        
        # Add hide column for variable column
        hide_column = ET.SubElement(var_column, "hideColumn")
        hide_column.text = str(pattern.get("hidden", "false")).lower()
        
        # Add width for variable column
        width = ET.SubElement(var_column, "width")
        width.text = "100"
        
        # Add header for variable column
        header = ET.SubElement(var_column, "header")
        header.text = pattern["header"]
        
        # Add constraint value type for variable column
        constraint_value_type = ET.SubElement(var_column, "constraintValueType")
        constraint_value_type.text = "1"
        
        # Add field type for variable column
        field_type = ET.SubElement(var_column, "fieldType")
        field_type.text = "Boolean"
        
        # Add parameters for variable column
        parameters = ET.SubElement(var_column, "parameters")
        
        # Add var name for variable column
        var_name = ET.SubElement(var_column, "varName")
        var_name.text = ""
    
    def _add_pattern_condition(self, parent, pattern):
        """Add Pattern condition to the XML."""
        pattern_element = ET.SubElement(parent, "Pattern52")
        
        # Add fact type
        fact_type = ET.SubElement(pattern_element, "factType")
        fact_type.text = pattern["factType"]
        
        # Add bound name
        bound_name = ET.SubElement(pattern_element, "boundName")
        bound_name.text = pattern["boundName"]
        
        # Add is negated
        is_negated = ET.SubElement(pattern_element, "isNegated")
        is_negated.text = "false"
        
        # Add conditions
        conditions = ET.SubElement(pattern_element, "conditions")
        
        for condition in pattern.get("conditions", []):
            condition_col = ET.SubElement(conditions, "condition-column52")
            
            # Add typed default value
            typed_default = ET.SubElement(condition_col, "typedDefaultValue")
            value_string = ET.SubElement(typed_default, "valueString")
            value_string.text = ""
            data_type = ET.SubElement(typed_default, "dataType")
            data_type.text = condition.get("dataType", "NUMERIC_DOUBLE")
            is_otherwise = ET.SubElement(typed_default, "isOtherwise")
            is_otherwise.text = "false"
            
            # Add hide column
            hide_column = ET.SubElement(condition_col, "hideColumn")
            hide_column.text = str(condition.get("hidden", "false")).lower()
            
            # Add width
            width = ET.SubElement(condition_col, "width")
            width.text = str(condition.get("width", "100"))
            
            # Add header
            header = ET.SubElement(condition_col, "header")
            header.text = condition["header"]
            
            # Add constraint value type
            constraint_value_type = ET.SubElement(condition_col, "constraintValueType")
            constraint_value_type.text = "1"
            
            # Add fact field
            fact_field = ET.SubElement(condition_col, "factField")
            fact_field.text = condition["factField"]
            
            # Add field type
            field_type = ET.SubElement(condition_col, "fieldType")
            field_type.text = condition["fieldType"]
            
            # Add operator
            operator = ET.SubElement(condition_col, "operator")
            operator.text = condition["operator"]
            
            # Add parameters
            parameters = ET.SubElement(condition_col, "parameters")
            
            # Add binding
            binding = ET.SubElement(condition_col, "binding")
            binding.text = ""
        
        # Add window
        window = ET.SubElement(pattern_element, "window")
        parameters = ET.SubElement(window, "parameters")
        
        # Add entry point name
        entry_point_name = ET.SubElement(pattern_element, "entryPointName")
        entry_point_name.text = ""
    
    def _add_action_columns(self):
        """Add action columns to the XML."""
        action_cols = ET.SubElement(self.root, "actionCols")
        
        for action in self.json_data.get("actionColumns", []):
            if action["type"] == "BRLAction":
                self._add_brl_action(action_cols, action)
            elif action["type"] == "ActionSetField":
                self._add_action_set_field(action_cols, action)
            elif action["type"] == "ActionInsertFact":
                self._add_action_insert_fact(action_cols, action)
    
    def _add_brl_action(self, parent, action):
        """Add BRL action to the XML."""
        brl_action = ET.SubElement(parent, "org.drools.workbench.models.guided.dtable.shared.model.BRLActionColumn")
        
        # Add hide column
        hide_column = ET.SubElement(brl_action, "hideColumn")
        hide_column.text = str(action.get("hidden", "false")).lower()
        
        # Add width
        width = ET.SubElement(brl_action, "width")
        width.text = "-1"
        
        # Add header
        header = ET.SubElement(brl_action, "header")
        header.text = action["header"]
        
        # Add definition
        definition = ET.SubElement(brl_action, "definition")
        
        for line in action["definition"]:
            free_form_line = ET.SubElement(definition, "org.drools.workbench.models.datamodel.rule.FreeFormLine")
            text = ET.SubElement(free_form_line, "text")
            text.text = line
        
        # Add child columns
        child_columns = ET.SubElement(brl_action, "childColumns")
        
        # Add variable column
        var_column = ET.SubElement(child_columns, "org.drools.workbench.models.guided.dtable.shared.model.BRLActionVariableColumn")
        
        # Add typed default value for variable column
        typed_default = ET.SubElement(var_column, "typedDefaultValue")
        value_string = ET.SubElement(typed_default, "valueString")
        value_string.text = ""
        data_type = ET.SubElement(typed_default, "dataType")
        data_type.text = "STRING"
        is_otherwise = ET.SubElement(typed_default, "isOtherwise")
        is_otherwise.text = "false"
        
        # Add hide column for variable column
        hide_column = ET.SubElement(var_column, "hideColumn")
        hide_column.text = str(action.get("hidden", "false")).lower()
        
        # Add width for variable column
        width = ET.SubElement(var_column, "width")
        width.text = "300"
        
        # Add header for variable column
        header = ET.SubElement(var_column, "header")
        header.text = action["header"]
        
        # Add var name for variable column
        var_name = ET.SubElement(var_column, "varName")
        var_name.text = action["header"]
        
        # Add field type for variable column
        field_type = ET.SubElement(var_column, "fieldType")
        field_type.text = "Object"
    
    def _add_action_set_field(self, parent, action):
        """Add ActionSetField to the XML."""
        action_set_field = ET.SubElement(parent, "ActionSetField")
        
        # Add bound name
        bound_name = ET.SubElement(action_set_field, "boundName")
        bound_name.text = action["boundName"]
        
        # Add fact field
        fact_field = ET.SubElement(action_set_field, "factField")
        fact_field.text = action["factField"]
        
        # Add type
        type_elem = ET.SubElement(action_set_field, "type")
        type_elem.text = action["type"]
        
        # Add value list
        value_list = ET.SubElement(action_set_field, "valueList")
        value_list.text = ""
        
        # Add update
        update = ET.SubElement(action_set_field, "update")
        update.text = "false"
        
        # Add header
        header = ET.SubElement(action_set_field, "header")
        header.text = action["header"]
        
        # Add hide column
        hide_column = ET.SubElement(action_set_field, "hideColumn")
        hide_column.text = str(action.get("hidden", "false")).lower()
        
        # Add default value
        default_value = ET.SubElement(action_set_field, "defaultValue")
        default_value.text = ""
        
        # Add width
        width = ET.SubElement(action_set_field, "width")
        width.text = "100"
    
    def _add_action_insert_fact(self, parent, action):
        """Add ActionInsertFact to the XML."""
        action_insert_fact = ET.SubElement(parent, "ActionInsertFact")
        
        # Add fact type
        fact_type = ET.SubElement(action_insert_fact, "factType")
        fact_type.text = action["factType"]
        
        # Add bound name
        bound_name = ET.SubElement(action_insert_fact, "boundName")
        bound_name.text = action["boundName"]
        
        # Add fact field
        fact_field = ET.SubElement(action_insert_fact, "factField")
        fact_field.text = action["factField"]
        
        # Add type
        type_elem = ET.SubElement(action_insert_fact, "type")
        type_elem.text = action["type"]
        
        # Add value list
        value_list = ET.SubElement(action_insert_fact, "valueList")
        value_list.text = ""
        
        # Add is bound
        is_bound = ET.SubElement(action_insert_fact, "isInsertLogical")
        is_bound.text = "false"
        
        # Add header
        header = ET.SubElement(action_insert_fact, "header")
        header.text = action["header"]
        
        # Add hide column
        hide_column = ET.SubElement(action_insert_fact, "hideColumn")
        hide_column.text = str(action.get("hidden", "false")).lower()
        
        # Add default value
        default_value = ET.SubElement(action_insert_fact, "defaultValue")
        default_value.text = ""
        
        # Add width
        width = ET.SubElement(action_insert_fact, "width")
        width.text = "100"
    
    def _add_audit_log(self):
        """Add audit log to the XML."""
        audit_log = ET.SubElement(self.root, "auditLog")
        filter_elem = ET.SubElement(audit_log, "filter")
        filter_elem.set("class", "org.drools.guvnor.client.modeldriven.dt52.auditlog.DecisionTableAuditLogFilter")
        
        accepted_types = ET.SubElement(filter_elem, "acceptedTypes")
        
        # Add accepted types
        types = ["INSERT_ROW", "INSERT_COLUMN", "DELETE_ROW", "DELETE_COLUMN", "UPDATE_COLUMN"]
        for type_name in types:
            entry = ET.SubElement(accepted_types, "entry")
            string = ET.SubElement(entry, "string")
            string.text = type_name
            boolean = ET.SubElement(entry, "boolean")
            boolean.text = "false"
        
        # Add entries
        entries = ET.SubElement(audit_log, "entries")
    
    def _add_imports(self):
        """Add imports to the XML."""
        imports_elem = ET.SubElement(self.root, "imports")
        imports_list = ET.SubElement(imports_elem, "imports")
        
        for import_path in self.json_data.get("imports", []):
            import_elem = ET.SubElement(imports_list, "org.kie.soup.project.datamodel.imports.Import")
            type_elem = ET.SubElement(import_elem, "type")
            type_elem.text = import_path
    
    def _add_package_name(self):
        """Add package name to the XML."""
        package_name = ET.SubElement(self.root, "packageName")
        package_name.text = self.json_data.get("packageName", "com.myspace.rules")
    
    def _add_version(self):
        """Add version to the XML."""
        version = ET.SubElement(self.root, "version")
        version.text = str(self.json_data.get("version", "1"))
    
    def _add_table_format(self):
        """Add table format to the XML."""
        table_format = ET.SubElement(self.root, "tableFormat")
        table_format.text = self.json_data.get("tableFormat", "EXTENDED_ENTRY")
    
    def _add_hit_policy(self):
        """Add hit policy to the XML."""
        hit_policy = ET.SubElement(self.root, "hitPolicy")
        hit_policy.text = self.json_data.get("hitPolicy", "NONE")
    
    def _add_data(self):
        """Add data to the XML."""
        data = ET.SubElement(self.root, "data")
        
        for row in self.json_data.get("data", []):
            row_list = ET.SubElement(data, "list")
            
            # Add row number
            value_elem = ET.SubElement(row_list, "value")
            value_numeric = ET.SubElement(value_elem, "valueNumeric")
            value_numeric.set("class", "int")
            value_numeric.text = str(row["rowNumber"])
            value_string = ET.SubElement(value_elem, "valueString")
            value_string.text = ""
            data_type = ET.SubElement(value_elem, "dataType")
            data_type.text = "NUMERIC_INTEGER"
            is_otherwise = ET.SubElement(value_elem, "isOtherwise")
            is_otherwise.text = "false"
            
            # Add description
            value_elem = ET.SubElement(row_list, "value")
            value_string = ET.SubElement(value_elem, "valueString")
            value_string.text = row.get("description", "")
            data_type = ET.SubElement(value_elem, "dataType")
            data_type.text = "STRING"
            is_otherwise = ET.SubElement(value_elem, "isOtherwise")
            is_otherwise.text = "false"
            
            # Add values
            for value_data in row.get("values", []):
                value_elem = ET.SubElement(row_list, "value")
                
                if value_data["dataType"] == "NUMERIC_INTEGER":
                    if value_data["value"] is not None:
                        value_numeric = ET.SubElement(value_elem, "valueNumeric")
                        value_numeric.set("class", "int")
                        value_numeric.text = str(value_data["value"])
                    value_string = ET.SubElement(value_elem, "valueString")
                    value_string.text = ""
                elif value_data["dataType"] == "NUMERIC_DOUBLE":
                    if value_data["value"] is not None:
                        value_numeric = ET.SubElement(value_elem, "valueNumeric")
                        value_numeric.set("class", "double")
                        value_numeric.text = str(value_data["value"])
                    value_string = ET.SubElement(value_elem, "valueString")
                    value_string.text = ""
                elif value_data["dataType"] == "BOOLEAN":
                    value_boolean = ET.SubElement(value_elem, "valueBoolean")
                    value_boolean.text = str(value_data["value"]).lower() if value_data["value"] is not None else "false"
                    value_string = ET.SubElement(value_elem, "valueString")
                    value_string.text = ""
                else:
                    value_string = ET.SubElement(value_elem, "valueString")
                    value_string.text = str(value_data["value"]) if value_data["value"] is not None else ""
                
                data_type = ET.SubElement(value_elem, "dataType")
                data_type.text = value_data["dataType"]
                is_otherwise = ET.SubElement(value_elem, "isOtherwise")
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
            filename = self.json_data.get("tableName", "unnamed_table")
        
        # Generate GDST content
        gdst_content = self.convert()
        
        # Save to file
        file_path = os.path.join(output_dir, f"{filename}.gdst")
        with open(file_path, "w") as f:
            f.write(gdst_content)
        
        # Also save the JSON for reference
        json_path = os.path.join(output_dir, f"{filename}.json")
        with open(json_path, "w") as f:
            json.dump(self.json_data, f, indent=2)
        
        return file_path


def convert_json_to_drools(json_data: Dict[str, Any], output_dir: str, filename: str = None) -> str:
    """
    Convert JSON schema to appropriate Drools file format (DRL or GDST).
    
    Args:
        json_data: Dictionary containing the rule data
        output_dir: Directory to save the file
        filename: Optional filename (without extension)
        
    Returns:
        Path to the saved file
    """
    # Determine if this is a DRL or GDST based on JSON structure
    if "tableName" in json_data:
        # This is a GDST
        converter = JsonToGdstConverter(json_data)
        return converter.save_to_file(output_dir, filename)
    else:
        # This is a DRL
        converter = JsonToDrlConverter(json_data)
        return converter.save_to_file(output_dir, filename)