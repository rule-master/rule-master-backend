import logging
import os
from datetime import datetime
from typing import Optional, Any
import json
from functools import wraps
import traceback

# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure the logger
logger = logging.getLogger('drools_llm')
logger.setLevel(logging.DEBUG)

# Create a file handler that logs everything to a daily rotating file
log_file = os.path.join('logs', f'drools_llm_{datetime.now().strftime("%Y%m%d")}.log')
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)

# Create a console handler with a higher log level
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create a formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

def log_operation(operation_type: str, details: Optional[dict] = None, error: Optional[Exception] = None) -> None:
    """
    Log an operation with its details and any errors.
    
    Args:
        operation_type (str): Type of operation (e.g., 'search', 'delete', 'edit')
        details (dict, optional): Dictionary containing operation details
        error (Exception, optional): Exception if operation failed
    """
    try:
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'operation': operation_type,
            'status': 'error' if error else 'success'
        }
        
        if details:
            log_entry['details'] = details
            
        if error:
            log_entry['error'] = {
                'type': type(error).__name__,
                'message': str(error),
                'traceback': traceback.format_exc()
            }
            
        # Log as JSON for better structure
        logger.info(json.dumps(log_entry, indent=2))
        
    except Exception as e:
        # Fallback logging if JSON serialization fails
        logger.error(f"Failed to log operation {operation_type}: {str(e)}")

def log_decorator(operation_type: str):
    """
    Decorator to automatically log function calls.
    
    Args:
        operation_type (str): Type of operation being performed
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            details = {
                'function': func.__name__,
                'args': str(args),
                'kwargs': str(kwargs)
            }
            
            try:
                result = func(*args, **kwargs)
                # Add result to details if it's serializable
                try:
                    if isinstance(result, dict):
                        details['result'] = result
                    else:
                        details['result'] = str(result)
                except:
                    details['result'] = 'Unable to serialize result'
                    
                log_operation(operation_type, details)
                return result
                
            except Exception as e:
                log_operation(operation_type, details, error=e)
                raise
                
        return wrapper
    return decorator

# Example usage of the decorator:
"""
@log_decorator('search')
def searchDroolsRules(...):
    ...

@log_decorator('delete')
def deleteDroolsRule(...):
    ...
"""

# Example direct logging:
"""
try:
    # Some operation
    log_operation('custom_operation', {'detail': 'value'})
except Exception as e:
    log_operation('custom_operation', {'detail': 'value'}, error=e)
""" 