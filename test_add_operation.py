#!/usr/bin/env python3
"""
Test script for validating the add operation in DroolsLLMAgent.

This script tests the end-to-end add operation from natural language to Drools rule creation.
"""

import os
import sys
import json
from DroolsLLMAgent_updated import DroolsLLMAgent

def test_add_operation():
    """Test the add operation in DroolsLLMAgent."""
    print("Testing DroolsLLMAgent add operation...")
    
    # Get API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        sys.exit(1)
    
    # Create test directory
    test_dir = os.path.join(os.getcwd(), "test_rules")
    os.makedirs(test_dir, exist_ok=True)
    
    # Initialize the agent
    agent = DroolsLLMAgent(
        api_key=api_key,
        rules_dir=test_dir
    )
    
    # Test cases
    test_cases = [
        {
            "name": "simple_drl_rule",
            "input": "Create a rule named recommend_extra_staff_for_autoking that adds 2 additional employees when a restaurant has AutoKing and the restaurant size is Large. The rule should have a salience of 90.",
            "expected_type": "drl"
        },
        {
            "name": "complex_gdst_rule",
            "input": "Create a staffing rule for restaurants based on total expected sales. If sales are between 0 and 100 dollars, assign 2 employees. If sales are between 100 and 200 dollars, assign 3 employees. If sales are between 200 and 300 dollars, assign 4 employees.",
            "expected_type": "gdst"
        }
    ]
    
    # Run test cases
    for i, test_case in enumerate(test_cases):
        print(f"\nTest Case {i+1}: {test_case['name']}")
        print(f"Input: {test_case['input']}")
        
        # Process the input with the agent
        response = agent.handle_user_message(test_case['input'])
        print(f"Agent response: {response}")
        
        # Check if files were created
        rule_files = os.listdir(test_dir)
        print(f"Files in test directory: {rule_files}")
        
        # Check for expected file types
        expected_ext = ".drl" if test_case['expected_type'] == "drl" else ".gdst"
        matching_files = [f for f in rule_files if f.endswith(expected_ext)]
        
        if matching_files:
            print(f"✅ Test passed: {test_case['expected_type'].upper()} file(s) created successfully")
            for file in matching_files:
                print(f"  - {file}")
        else:
            print(f"❌ Test failed: No {test_case['expected_type'].upper()} file created")
    
    print("\nAll tests completed.")

if __name__ == "__main__":
    test_add_operation()
