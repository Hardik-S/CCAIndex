import os
import sys
import json
import logging
import traceback
from datetime import datetime
from functools import wraps
import smtplib
from email.message import EmailMessage
from pathlib import Path

# Create logs directory if it doesn't exist
Path("logs").mkdir(exist_ok=True)

# Configure base logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Create a custom logger for our application
logger = logging.getLogger('cca_index')
logger.setLevel(logging.DEBUG)

# Create handlers for different log levels
info_handler = logging.FileHandler('logs/info.log')
info_handler.setLevel(logging.INFO)

error_handler = logging.FileHandler('logs/error.log')
error_handler.setLevel(logging.ERROR)

# Create console handler for seeing output during development
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)

# Create formatters and add them to handlers
log_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s'
)

info_handler.setFormatter(log_formatter)
error_handler.setFormatter(log_formatter)
console_handler.setFormatter(log_formatter)

# Add handlers to the logger
logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.addHandler(console_handler)

class APIError(Exception):
    """Custom exception for API related errors"""
    def __init__(self, message, api_name=None, status_code=None, response=None):
        self.message = message
        self.api_name = api_name
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)

class DataProcessingError(Exception):
    """Custom exception for data processing errors"""
    pass

class ConfigurationError(Exception):
    """Custom exception for configuration errors"""
    pass

def log_error(e, context=None):
    """
    Log detailed error information
    
    Args:
        e (Exception): The exception that was raised
        context (dict, optional): Additional context information
    """
    error_info = {
        'error_type': e.__class__.__name__,
        'error_message': str(e),
        'timestamp': datetime.now().isoformat(),
        'traceback': traceback.format_exc()
    }
    
    if context:
        error_info['context'] = context
        
    logger.error(f"Error occurred: {e.__class__.__name__}: {str(e)}")
    logger.debug(f"Error details: {json.dumps(error_info, indent=2)}")
    
    # For critical errors, you might want to send an email alert
    if isinstance(e, (APIError, DataProcessingError)) and hasattr(e, 'status_code') and e.status_code in [500, 403, 401]:
        send_error_alert(error_info)

def send_error_alert(error_info):
    """
    Send an email alert for critical errors
    
    Args:
        error_info (dict): Information about the error
    """
    # Get email configuration from environment variables
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = os.getenv('SMTP_PORT')
    smtp_username = os.getenv('SMTP_USERNAME')
    smtp_password = os.getenv('SMTP_PASSWORD')
    alert_email = os.getenv('ALERT_EMAIL')
    
    # Only send if email is configured
    if all([smtp_server, smtp_port, smtp_username, smtp_password, alert_email]):
        try:
            msg = EmailMessage()
            msg['Subject'] = f"CCA Index Alert: {error_info['error_type']}"
            msg['From'] = smtp_username
            msg['To'] = alert_email
            
            # Create the email content
            content = f"""
            Critical error in CCA Index application:
            
            Error Type: {error_info['error_type']}
            Error Message: {error_info['error_message']}
            Timestamp: {error_info['timestamp']}
            
            Traceback:
            {error_info['traceback']}
            """
            
            msg.set_content(content)
            
            # Send the email
            with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
                
            logger.info("Error alert email sent successfully.")
        except Exception as email_error:
            logger.error(f"Failed to send error alert email: {str(email_error)}")

def log_api_request(api_name, endpoint, params=None):
    """
    Log information about an API request
    
    Args:
        api_name (str): Name of the API service
        endpoint (str): API endpoint being called
        params (dict, optional): Request parameters (sensitive info will be redacted)
    """
    # Redact sensitive information like API keys
    if params and isinstance(params, dict):
        logged_params = params.copy()
        sensitive_keys = ['key', 'apiKey', 'api_key', 'token', 'secret', 'password']
        for key in logged_params:
            if any(sensitive in key.lower() for sensitive in sensitive_keys) and logged_params[key]:
                logged_params[key] = '********'
    else:
        logged_params = params
        
    logger.info(f"API Request: {api_name} - {endpoint}")
    logger.debug(f"API Request Details: {api_name} - {endpoint} - {json.dumps(logged_params)}")

def log_function_call(func):
    """
    Decorator to log function calls, parameters, and execution time
    
    Args:
        func (function): The function to be wrapped
        
    Returns:
        function: The wrapped function
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        function_name = func.__name__
        
        # Log the function call
        logger.debug(f"Function {function_name} called with args: {args}, kwargs: {kwargs}")
        
        try:
            # Execute the function
            result = func(*args, **kwargs)
            
            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Log successful execution
            logger.debug(f"Function {function_name} completed in {execution_time:.2f} seconds")
            
            return result
        except Exception as e:
            # Log the exception
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Function {function_name} failed after {execution_time:.2f} seconds: {str(e)}")
            log_error(e, {'function': function_name})
            raise
    
    return wrapper

def handle_api_response(response, api_name):
    """
    Check API response for errors and handle them appropriately
    
    Args:
        response (requests.Response): The response from the API
        api_name (str): Name of the API service
        
    Returns:
        dict: The JSON response data
        
    Raises:
        APIError: If there's an issue with the API response
    """
    try:
        # Log the response status
        logger.debug(f"API Response from {api_name}: Status Code {response.status_code}")
        
        # Check if the request was successful
        response.raise_for_status()
        
        # Parse the JSON response
        data = response.json()
        
        # Check for API-specific error indicators in the response
        if api_name == "NewsAPI" and data.get("status") != "ok":
            error_message = data.get("message", "Unknown NewsAPI error")
            logger.error(f"NewsAPI error: {error_message}")
            raise APIError(
                message=error_message,
                api_name=api_name,
                status_code=response.status_code,
                response=data
            )
        elif api_name == "GNews" and "errors" in data:
            error_message = str(data.get("errors", "Unknown GNews error"))
            logger.error(f"GNews error: {error_message}")
            raise APIError(
                message=error_message,
                api_name=api_name,
                status_code=response.status_code,
                response=data
            )
            
        return data
    
    except json.JSONDecodeError as e:
        # Handle invalid JSON in the response
        error_message = f"Invalid JSON in {api_name} response: {str(e)}"
        logger.error(error_message)
        raise APIError(
            message=error_message,
            api_name=api_name,
            status_code=response.status_code,
            response=response.text
        )
        
    except requests.exceptions.HTTPError as e:
        # Handle HTTP errors (4xx, 5xx)
        error_message = f"{api_name} HTTP error: {str(e)}"
        logger.error(error_message)
        raise APIError(
            message=error_message,
            api_name=api_name,
            status_code=response.status_code,
            response=getattr(response, 'text', str(e))
        )
        
    except requests.exceptions.RequestException as e:
        # Handle other requests-related errors (connection, timeout, etc.)
        error_message = f"{api_name} request failed: {str(e)}"
        logger.error(error_message)
        raise APIError(
            message=error_message,
            api_name=api_name
        )

def setup_file_logging(log_dir='logs', retention_days=7):
    """
    Set up rotating file handler for log files with retention policy
    
    Args:
        log_dir (str): Directory for log files
        retention_days (int): Number of days to keep log files
    """
    try:
        # Create log directory if it doesn't exist
        Path(log_dir).mkdir(exist_ok=True)
        
        # Add a rotating file handler
        from logging.handlers import TimedRotatingFileHandler
        
        # Set up daily rotation with retention period
        file_handler = TimedRotatingFileHandler(
            f"{log_dir}/cca_index.log",
            when="midnight",
            interval=1,
            backupCount=retention_days
        )
        
        file_handler.setFormatter(log_formatter)
        file_handler.setLevel(logging.DEBUG)
        
        logger.addHandler(file_handler)
        logger.info(f"File logging configured with {retention_days} days retention")
        
    except Exception as e:
        logger.error(f"Failed to set up file logging: {str(e)}")
        # Fallback to basic file logging
        fallback_handler = logging.FileHandler(f"{log_dir}/fallback.log")
        fallback_handler.setFormatter(log_formatter)
        logger.addHandler(fallback_handler)

def check_env_variables(required_vars):
    """
    Check if all required environment variables are set
    
    Args:
        required_vars (list): List of required environment variable names
        
    Raises:
        ConfigurationError: If any required variables are missing
    """
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        error_message = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_message)
        raise ConfigurationError(error_message)
    
    logger.debug(f"All required environment variables present: {', '.join(required_vars)}")

def init():
    """Initialize the logging system"""
    logger.info("Initializing CCA Index logging system")
    setup_file_logging()
    
    # Log system info
    import platform
    system_info = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "system": platform.system(),
        "node": platform.node()
    }
    
    logger.info(f"System information: {json.dumps(system_info)}")
    logger.info("Logging system initialized successfully")

# Initialize logging when module is imported
if __name__ != "__main__":
    init()