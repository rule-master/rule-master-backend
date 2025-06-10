import os
import re
from typing import Dict, List
from logger_utils import logger


def parse_java_classes(java_dir: str) -> Dict[str, dict]:
    """
    Parse all Java class files in a directory and return a dictionary:
    {
      class_name: {
        'package': str,
        'class_name': str,
        'methods': [ 'methodName(paramType, ...)', ... ],
        'fields': [ 'fieldName', ... ]
      }
    }
    """
    if not java_dir or not os.path.exists(java_dir):
        logger.warning(f"Java directory not found: {java_dir}")
        return {}

    classes = {}

    for root, _, files in os.walk(java_dir):
        for file in files:
            if not file.endswith(".java"):
                continue
            file_path = os.path.join(root, file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                parsed_class = parse_single_java_file(content)
                if parsed_class:
                    classes[parsed_class['class_name']] = {
                        "package": parsed_class['package'],
                        "class_name": parsed_class['class_name'],
                        "methods": parsed_class['methods'],
                        "fields": parsed_class['fields'],
                    }
                    
                    # Debug logging for final results
                    logger.info(f"Successfully parsed class: {parsed_class['class_name']}")
                    logger.info(f"  Package: {parsed_class['package']}")
                    logger.info(f"  Methods found: {len(parsed_class['methods'])}")
                    for i, method in enumerate(parsed_class['methods'], 1):
                        logger.info(f"    {i}. {method}")
                    logger.info(f"  Fields found: {len(parsed_class['fields'])}")
                    for i, field in enumerate(parsed_class['fields'], 1):
                        logger.info(f"    {i}. {field}")
                    logger.info("-" * 50)
                    
            except Exception as e:
                logger.error(f"Error parsing Java file {file_path}: {str(e)}")
                continue

    return classes


def parse_single_java_file(content: str) -> Dict:
    """
    Parse a single Java file content and extract class information.
    """
    # Remove comments to avoid false matches
    content = remove_comments(content)
    
    # Extract package name
    package = extract_package(content)
    
    # Extract class name
    class_name = extract_class_name(content)
    if not class_name:
        return None
    
    # Extract methods
    methods = extract_methods(content, class_name)
    
    # Extract fields
    fields = extract_fields(content)
    
    return {
        "package": package,
        "class_name": class_name,
        "methods": methods,
        "fields": fields,
    }


def remove_comments(content: str) -> str:
    """
    Remove single-line and multi-line comments from Java code.
    """
    # Remove multi-line comments /* ... */
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    
    # Remove single-line comments //
    content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
    
    return content


def extract_package(content: str) -> str:
    """
    Extract package declaration from Java content.
    """
    pkg_match = re.search(r'package\s+([a-zA-Z0-9_.]+)\s*;', content)
    return pkg_match.group(1) if pkg_match else None


def extract_class_name(content: str) -> str:
    """
    Extract class name from Java content.
    Handles various class declarations including abstract, final, etc.
    """
    # Match class declaration with optional modifiers
    cls_match = re.search(
        r'(?:public\s+|private\s+|protected\s+)?(?:abstract\s+|final\s+|static\s+)*class\s+([A-Za-z0-9_]+)',
        content
    )
    return cls_match.group(1) if cls_match else None


def extract_methods(content: str, class_name: str) -> List[str]:
    """
    Extract method signatures from Java content.
    Excludes constructors and handles various method types.
    """
    methods = []
    
    # Pattern to match method declarations
    # Captures: access_modifier return_type method_name(parameters)
    method_pattern = re.compile(
        r'(?:public|private|protected)\s+'  # Access modifier (required)
        r'(?:static\s+|final\s+|abstract\s+|synchronized\s+)*'  # Optional modifiers
        r'(?:<[^>]+>\s+)?'  # Optional generic type parameters
        r'([a-zA-Z0-9_<>\[\].,\s]+)\s+'  # Return type (capture group 1)
        r'([A-Za-z0-9_]+)\s*'  # Method name (capture group 2)
        r'\(([^)]*)\)',  # Parameters (capture group 3)
        re.MULTILINE
    )
    
    for match in method_pattern.finditer(content):
        return_type = match.group(1).strip()
        method_name = match.group(2).strip()
        params = match.group(3).strip()
        
        # Skip constructors (method name same as class name)
        if method_name == class_name:
            continue
            
        # Clean up parameters - extract just the types
        param_types = extract_parameter_types(params)
        param_str = ', '.join(param_types) if param_types else ''
        
        # Create method signature
        signature = f"{method_name}({param_str})"
        methods.append(signature)
    
    return methods


def extract_parameter_types(params: str) -> List[str]:
    """
    Extract parameter types from method parameter string.
    """
    if not params.strip():
        return []
    
    param_types = []
    # Split by comma, but be careful with generics
    param_parts = split_parameters(params)
    
    for param in param_parts:
        param = param.strip()
        if param:
            # Extract type (everything before the last word, which is the variable name)
            parts = param.split()
            if len(parts) >= 2:
                # Join all parts except the last one (variable name)
                param_type = ' '.join(parts[:-1])
                param_types.append(param_type)
            elif len(parts) == 1:
                # Handle case where only type is present (shouldn't happen in valid Java)
                param_types.append(parts[0])
    
    return param_types


def split_parameters(params: str) -> List[str]:
    """
    Split parameter string by commas, handling generics properly.
    """
    if not params.strip():
        return []
    
    parts = []
    current = ""
    bracket_count = 0
    angle_count = 0
    
    for char in params:
        if char == '<':
            angle_count += 1
        elif char == '>':
            angle_count -= 1
        elif char == '(':
            bracket_count += 1
        elif char == ')':
            bracket_count -= 1
        elif char == ',' and angle_count == 0 and bracket_count == 0:
            parts.append(current.strip())
            current = ""
            continue
        
        current += char
    
    if current.strip():
        parts.append(current.strip())
    
    return parts


def extract_fields(content: str) -> List[str]:
    """
    Extract field names from Java content.
    Handles various field types and modifiers.
    """
    fields = []
    
    # Split content into lines for more precise parsing
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines, comments, and method/class declarations
        if not line or line.startswith('//') or line.startswith('/*') or line.startswith('*'):
            continue
        if 'class ' in line or ('(' in line and ')' in line and not line.strip().endswith(';')):
            continue
            
        # Pattern to match field declarations
        # Must start with access modifier and end with semicolon
        field_match = re.match(
            r'(?:public|private|protected)\s+'  # Access modifier
            r'(?:static\s+|final\s+|volatile\s+|transient\s+)*'  # Optional modifiers
            r'(?:<[^>]+>\s+)?'  # Optional generic type parameters
            r'([a-zA-Z0-9_<>\[\].,\s]+)\s+'  # Field type
            r'([A-Za-z0-9_]+)'  # Field name
            r'(?:\s*=\s*[^;]*)?'  # Optional initialization (changed from [^;]+ to [^;]*)
            r'\s*;$',  # Must end with semicolon
            line
        )
        
        if field_match:
            field_name = field_match.group(2).strip()
            if field_name and field_name not in fields:
                fields.append(field_name)
            continue
        
        # Handle multiple field declarations on one line
        # e.g., private int a, b, c;
        multi_field_match = re.match(
            r'(?:public|private|protected)\s+'
            r'(?:static\s+|final\s+|volatile\s+|transient\s+)*'
            r'(?:<[^>]+>\s+)?'
            r'([a-zA-Z0-9_<>\[\].,\s]+)\s+'  # Field type
            r'([A-Za-z0-9_,\s=\[\](){}."\']+);$',  # Multiple field names, must end with ;
            line
        )
        
        if multi_field_match:
            field_names_part = multi_field_match.group(2).strip()
            # Split by comma and extract field names
            for field_part in field_names_part.split(','):
                field_part = field_part.strip()
                # Remove initialization if present
                if '=' in field_part:
                    field_part = field_part.split('=')[0].strip()
                # Remove array brackets and other decorations
                field_name = re.sub(r'\[.*?\]', '', field_part).strip()
                # Remove any remaining parentheses or braces (shouldn't be in field names)
                field_name = re.sub(r'[(){}].*', '', field_name).strip()
                if field_name and field_name.isidentifier() and field_name not in fields:
                    fields.append(field_name)
    
    return fields