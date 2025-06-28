"""
Search tool implementation for Drools LLM Agent.

This module provides functionality to search for similar Drools rules using Qdrant vector search
with OpenAI embeddings.
"""

from .rule_management import search_rules, delete_rule, edit_rule

__all__ = ['search_rules', 'delete_rule', 'edit_rule']