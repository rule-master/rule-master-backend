import os
import re
from typing import Dict

def parse_java_classes(java_dir: str) -> Dict[str, dict]:
    """
    Parse all Java class files in a directory and return a dictionary:
    {
      class_name: {
        'package': str,
        'class_name': str,
        'methods': [ 'methodName(paramType, ...)', ... ]
      }
    }
    """
    classes = {}

    for root, _, files in os.walk(java_dir):
        for file in files:
            if not file.endswith(".java"):
                continue
            file_path = os.path.join(root, file)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract package name
            pkg_match = re.search(r'package\s+([a-zA-Z0-9_.]+);', content)
            package = pkg_match.group(1) if pkg_match else None

            # Extract class name
            cls_match = re.search(r'public\s+class\s+([A-Za-z0-9_]+)', content)
            if not cls_match:
                continue
            class_name = cls_match.group(1)

            # Extract public methods (skip constructor)
            method_pattern = re.compile(
                r'public\s+[\w<>\[\]]+\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)'
            )
            methods = []
            for m in method_pattern.finditer(content):
                name = m.group(1)
                params = m.group(2).strip()
                if name == class_name:
                    continue
                signature = f"{name}({params})"
                methods.append(signature)

            classes[class_name] = {
                "package": package,
                "class_name": class_name,
                "methods": methods
            }

    return classes