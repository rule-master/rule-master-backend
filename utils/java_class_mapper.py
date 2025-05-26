#!/usr/bin/env python3
"""
Utility module for mapping Java classes to their packages.
"""

import os
import re
from typing import Dict, List, Optional

def map_java_classes(java_dir: str) -> Dict[str, str]:
    """
    Map Java class names to their package names.
    
    Args:
        java_dir (str): Directory containing Java class files
        
    Returns:
        dict: Dictionary mapping class names to package names
    """
    class_map = {}
    
    # Check if directory exists
    if not os.path.exists(java_dir):
        return class_map
    
    # Walk through the directory
    for root, _, files in os.walk(java_dir):
        for file in files:
            if file.endswith(".java"):
                file_path = os.path.join(root, file)
                
                # Extract class name and package
                class_name, package = _extract_class_info(file_path)
                
                if class_name and package:
                    class_map[class_name] = package
    
    return class_map

def _extract_class_info(file_path: str) -> tuple:
    """
    Extract class name and package from a Java file.
    
    Args:
        file_path (str): Path to the Java file
        
    Returns:
        tuple: (class_name, package_name)
    """
    class_name = None
    package_name = None
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract package name
    package_match = re.search(r'package\s+([a-zA-Z0-9_.]+);', content)
    if package_match:
        package_name = package_match.group(1)
    
    # Extract class name
    class_match = re.search(r'(?:public|private|protected)?\s+class\s+([a-zA-Z0-9_]+)', content)
    if class_match:
        class_name = class_match.group(1)
    
    return class_name, package_name
