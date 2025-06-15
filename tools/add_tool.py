"""
Add tool implementation for Drools LLM Agent.

This module provides functionality to add new Drools rules (DRL or GDST)
from natural language descriptions using the NL-to-JSON-to-Drools pipeline.
"""

from .rule_management import add_rule, save_json_to_file

__all__ = ['add_rule', 'save_json_to_file']
