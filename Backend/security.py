"""
Security utilities for input validation, sanitization, and secure comparisons.
Centralized security functions for all Flask applications.
"""
import re
import hmac
import hashlib
import secrets
from html import escape
from datetime import datetime
from functools import wraps
from flask import request, jsonify, session


# ============================================================================
# EMAIL VALIDATION
# ============================================================================

def is_valid_email(email: str, max_length: int = 254) -> bool:
    """
    Validate email address format and length.
    
    Args:
        email: Email string to validate
        max_length: Maximum allowed email length (RFC 5321 = 254)
    
    Returns:
        bool: True if valid, False otherwise
    """
    if not isinstance(email, str) or not email:
        return False
    
    if len(email) > max_length:
        return False
    
    # Basic RFC 5322 pattern (simplified for common cases)
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


# ============================================================================
# TEXT SANITIZATION
# ============================================================================

def sanitize_text(text: str, max_length: int = 1000, allow_newlines: bool = True) -> str:
    """
    Sanitize text input: strip, escape HTML, validate length.
    Prevents XSS attacks through content fields.
    
    Args:
        text: Text to sanitize
        max_length: Maximum allowed length
        allow_newlines: If False, replace newlines with spaces
    
    Returns:
        Sanitized text or None if invalid
    """
    if not isinstance(text, str):
        return None
    
    text = text.strip()
    
    # Remove null bytes and other dangerous characters
    text = text.replace('\x00', '')
    
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ' if not allow_newlines else '\n', text)
    
    if len(text) == 0 or len(text) > max_length:
        return None
    
    # Escape HTML entities to prevent XSS
    return escape(text)


def sanitize_html_aggressive(text: str) -> str:
    """
    Aggressive HTML sanitization for content that should NOT contain any HTML.
    Removes all tags and entities.
    
    Args:
        text: Text to sanitize
    
    Returns:
        Plain text without HTML
    """
    if not isinstance(text, str):
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    text = escape(text)
    
    return text.strip()


# ============================================================================
# DATE/TIME VALIDATION
# ============================================================================

def validate_iso_date(date_str: str) -> bool:
    """
    Validate ISO format date string (YYYY-MM-DD).
    
    Args:
        date_str: Date string to validate
    
    Returns:
        bool: True if valid, False otherwise
    """
    if not isinstance(date_str, str):
        return False
    
    try:
        datetime.fromisoformat(date_str)
        return True
    except (ValueError, TypeError):
        return False


def validate_time_format(time_str: str) -> bool:
    """
    Validate time format (HH:MM or HH:MM:SS).
    
    Args:
        time_str: Time string to validate
    
    Returns:
        bool: True if valid, False otherwise
    """
    if not isinstance(time_str, str):
        return False
    
    pattern = r'^([0-1][0-9]|2[0-3]):([0-5][0-9])(?::([0-5][0-9]))?$'
    return re.match(pattern, time_str) is not None


def validate_datetime_iso(datetime_str: str) -> bool:
    """
    Validate ISO format datetime string.
    
    Args:
        datetime_str: Datetime string to validate
    
    Returns:
        bool: True if valid, False otherwise
    """
    if not isinstance(datetime_str, str):
        return False
    
    try:
        datetime.fromisoformat(datetime_str)
        return True
    except (ValueError, TypeError):
        return False


# ============================================================================
# NUMERIC VALIDATION
# ============================================================================

def validate_range(value, min_val: float, max_val: float) -> bool:
    """
    Validate numeric value is within range.
    Useful for temperature, humidity, etc.
    
    Args:
        value: Value to check
        min_val: Minimum allowed value
        max_val: Maximum allowed value
    
    Returns:
        bool: True if in range, False otherwise
    """
    try:
        num = float(value)
        return min_val <= num <= max_val
    except (TypeError, ValueError):
        return False


# ============================================================================
# API KEY SECURITY
# ============================================================================

def secure_compare_api_keys(provided_key: str, stored_key: str) -> bool:
    """
    Timing-safe comparison of API keys.
    Prevents timing attacks on API key verification.
    
    Args:
        provided_key: API key provided by client
        stored_key: Stored reference API key
    
    Returns:
        bool: True if keys match, False otherwise
    """
    if not provided_key or not stored_key:
        return False
    
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(provided_key, stored_key)


def validate_api_key_header(api_key_env_var: str) -> bool:
    """
    Extract and validate API key from request headers.
    API key should ONLY come from X-API-Key header, never from query params.
    
    Args:
        api_key_env_var: The configured API key from environment
    
    Returns:
        bool: True if valid API key provided, False otherwise
    """
    if not api_key_env_var:
        return False
    
    # Only accept from header, never from query parameters
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return False
    
    return secure_compare_api_keys(api_key, api_key_env_var)


# ============================================================================
# DECORATORS
# ============================================================================

def require_api_key(api_key_env_var: str):
    """
    Decorator to require valid API key on endpoint.
    
    Usage:
        @app.route('/protected')
        @require_api_key(app.config['API_KEY'])
        def protected_route():
            ...
    
    Args:
        api_key_env_var: The API key from config/environment
    
    Returns:
        Decorator function
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not validate_api_key_header(api_key_env_var):
                return jsonify({'error': 'Unauthorized'}), 401
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ============================================================================
# UTILITY VALIDATORS
# ============================================================================

def is_valid_username(username: str, min_length: int = 3, max_length: int = 50) -> bool:
    """
    Validate username format.
    
    Args:
        username: Username to validate
        min_length: Minimum length
        max_length: Maximum length
    
    Returns:
        bool: True if valid, False otherwise
    """
    if not isinstance(username, str):
        return False
    
    username = username.strip()
    
    if len(username) < min_length or len(username) > max_length:
        return False
    
    # Allow alphanumeric, underscore, hyphen
    pattern = r'^[a-zA-Z0-9_-]+$'
    return re.match(pattern, username) is not None


def is_strong_password(password: str, min_length: int = 8) -> tuple[bool, str]:
    """
    Validate password strength.
    
    Args:
        password: Password to validate
        min_length: Minimum password length
    
    Returns:
        Tuple of (is_valid: bool, reason: str)
    """
    if not isinstance(password, str):
        return False, "Password must be a string"
    
    if len(password) < min_length:
        return False, f"Password must be at least {min_length} characters"
    
    if len(password) > 128:
        return False, "Password is too long (max 128 characters)"
    
    has_upper = bool(re.search(r'[A-Z]', password))
    has_lower = bool(re.search(r'[a-z]', password))
    has_digit = bool(re.search(r'[0-9]', password))
    has_special = bool(re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>?/\\|`~]', password))
    
    # Require at least 3 of 4 categories
    strength = sum([has_upper, has_lower, has_digit, has_special])
    
    if strength < 3:
        return False, "Password must contain uppercase, lowercase, numbers, and special characters"
    
    return True, "Password is strong"


# ============================================================================
# PATH TRAVERSAL PREVENTION
# ============================================================================

def safe_path_join(base_path: str, user_provided_path: str) -> tuple[bool, str]:
    """
    Safely join paths while preventing path traversal attacks.
    
    Args:
        base_path: Absolute base directory path
        user_provided_path: User-provided path component
    
    Returns:
        Tuple of (is_safe: bool, full_path: str or error_message: str)
    """
    import os
    
    base_path = os.path.abspath(base_path)
    full_path = os.path.abspath(os.path.join(base_path, user_provided_path))
    
    # Ensure the resolved path is within the base directory
    if not full_path.startswith(base_path + os.sep) and full_path != base_path:
        return False, "Path traversal detected"
    
    return True, full_path


# ============================================================================
# LOGGING HELPERS
# ============================================================================

def sanitize_for_logging(data: dict, sensitive_keys: list = None) -> dict:
    """
    Sanitize sensitive data before logging.
    Removes or masks sensitive fields.
    
    Args:
        data: Dictionary to sanitize
        sensitive_keys: List of keys to redact (default: common sensitive fields)
    
    Returns:
        Sanitized dictionary
    """
    if sensitive_keys is None:
        sensitive_keys = ['password', 'token', 'api_key', 'secret', 'creditcard', 'ssn']
    
    sanitized = {}
    for key, value in data.items():
        if any(sensitive_key.lower() in key.lower() for sensitive_key in sensitive_keys):
            sanitized[key] = '***REDACTED***'
        else:
            sanitized[key] = value
    
    return sanitized


# ============================================================================
# CSRF PROTECTION
# ============================================================================

def generate_csrf_token() -> str:
    """
    Generate a cryptographically secure CSRF token.
    
    Returns:
        str: CSRF token (32 bytes hex)
    """
    return secrets.token_hex(32)


def verify_csrf_token(provided_token: str, stored_token: str) -> bool:
    """
    Verify CSRF token using constant-time comparison.
    
    Args:
        provided_token: Token from request
        stored_token: Token from session
    
    Returns:
        bool: True if valid, False otherwise
    """
    if not provided_token or not stored_token:
        return False
    
    return hmac.compare_digest(provided_token, stored_token)


def require_csrf_token():
    """
    Decorator to require valid CSRF token on POST/PUT/DELETE requests.
    Token should be in request header 'X-CSRF-Token' or form data.
    
    Usage:
        @app.route('/api/data', methods=['POST'])
        @require_csrf_token()
        def update_data():
            ...
    
    Returns:
        Decorator function
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Skip for GET requests
            if request.method == 'GET':
                return f(*args, **kwargs)
            
            # Get stored token from session
            stored_token = session.get('csrf_token')
            if not stored_token:
                return jsonify({'error': 'CSRF token not found in session'}), 403
            
            # Get provided token from header or form
            provided_token = request.headers.get('X-CSRF-Token')
            if not provided_token:
                provided_token = request.form.get('csrf_token')
            
            if not provided_token:
                return jsonify({'error': 'CSRF token missing'}), 400
            
            # Verify token
            if not verify_csrf_token(provided_token, stored_token):
                return jsonify({'error': 'Invalid CSRF token'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator