"""
Configuration module for Flask applications.
All sensitive values (secrets, keys, passwords) are read from environment variables.
"""
import os


class BaseConfig:
    """Base configuration - production-ready settings."""
    DEBUG = False
    TESTING = False
    
    # Secret key for session management - MUST be set via environment variable
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
    
    # Admin password - MUST be set via environment variable in production
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
    
    # File upload limits
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 8 * 1024 * 1024))  # 8 MB default
    ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "txt", "doc", "docx"}
    
    # Database paths (relative, adjusted per service)
    DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../database"))
    
    # Security headers
    SESSION_COOKIE_SECURE = True  # Only send over HTTPS
    SESSION_COOKIE_HTTPONLY = True  # No JS access
    SESSION_COOKIE_SAMESITE = "Lax"  # CSRF protection
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour


class DevelopmentConfig(BaseConfig):
    """Development-specific config (with some debug enabled)."""
    DEBUG = False  # Even in dev, keep False for security
    SESSION_COOKIE_SECURE = False  # Allow HTTP in local dev


class TestingConfig(BaseConfig):
    """Testing configuration."""
    TESTING = True
    DEBUG = False
    SESSION_COOKIE_SECURE = False


def require_secrets(app):
    """
    Validate that required secrets are set.
    Call this in production to fail early if secrets are missing.
    Raises RuntimeError if any required secrets are missing.
    """
    missing = []
    
    if not app.config.get("FLASK_SECRET_KEY"):
        missing.append("FLASK_SECRET_KEY")
    if not app.config.get("ADMIN_PASSWORD"):
        missing.append("ADMIN_PASSWORD")
    
    if missing and not app.debug:
        error_msg = f"Missing required environment variables: {', '.join(missing)}\n"
        error_msg += "Set these variables before running in production."
        raise RuntimeError(error_msg)


def get_config(env=None):
    """Get configuration object based on environment."""
    env = env or os.environ.get("FLASK_ENV", "production")
    if env == "development":
        return DevelopmentConfig()
    elif env == "testing":
        return TestingConfig()
    else:
        return BaseConfig()
