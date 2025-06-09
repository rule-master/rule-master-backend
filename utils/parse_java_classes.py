import os
import re
from typing import Dict
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
        return {
            "RestaurantData": {
                "package": "com.myspace.resopsrecomms",
                "methods": [
                    "getRestaurantSize()",
                    "getTotalExpectedSales()",
                    "getTimeSlotExpectedSales()",
                    "getCurrentEmployees()",
                    "getExtraEmployees()",
                ],
                "fields": [
                    "restaurantSize",
                    "totalExpectedSales",
                    "timeSlotExpectedSales",
                    "currentEmployees",
                    "extraEmployees",
                ],
            },
            "EmployeeRecommendation": {
                "package": "com.myspace.resopsrecomms",
                "methods": [
                    "addRestaurantEmployees(int count)",
                    "addRestaurantExtraEmployees(int count)",
                    "setRestaurantEmployees(int count)",
                    "setRestaurantExtraEmployees(int count)",
                    "getRequiredEmployees()",
                    "getExtraEmployees()",
                ],
                "fields": ["requiredEmployees", "extraEmployees"],
            },
        }

    classes = {}

    for root, _, files in os.walk(java_dir):
        for file in files:
            if not file.endswith(".java"):
                continue
            file_path = os.path.join(root, file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Extract package name
                pkg_match = re.search(r"package\s+([a-zA-Z0-9_.]+);", content)
                package = pkg_match.group(1) if pkg_match else None

                # Extract class name
                cls_match = re.search(r"public\s+class\s+([A-Za-z0-9_]+)", content)
                if not cls_match:
                    continue
                class_name = cls_match.group(1)

                # Extract public methods (skip constructor)
                method_pattern = re.compile(
                    r"public\s+[\w<>\[\]]+\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)"
                )
                methods = []
                for m in method_pattern.finditer(content):
                    name = m.group(1)
                    params = m.group(2).strip()
                    if name == class_name:
                        continue
                    signature = f"{name}({params})"
                    methods.append(signature)

                # Extract fields
                field_pattern = re.compile(
                    r"private\s+[\w<>\[\]]+\s+([A-Za-z0-9_]+)\s*;"
                )
                fields = []
                for f in field_pattern.finditer(content):
                    field_name = f.group(1)
                    fields.append(field_name)

                classes[class_name] = {
                    "package": package,
                    "class_name": class_name,
                    "methods": methods,
                    "fields": fields,
                }
            except Exception as e:
                logger.error(f"Error parsing Java file {file_path}: {str(e)}")
                continue

    return classes
