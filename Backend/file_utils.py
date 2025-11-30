"""
Secure file handling utilities.
Provides safe file upload and serving functions with validation.
"""
import os
import uuid
from werkzeug.utils import secure_filename
from flask import abort, send_from_directory


def allowed_file(filename, allowed_extensions):
    """
    Check if a filename has an allowed extension.
    
    Args:
        filename: The uploaded filename
        allowed_extensions: Set or list of allowed extensions (e.g., {"pdf", "jpg"})
    
    Returns:
        bool: True if extension is allowed, False otherwise
    """
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in allowed_extensions


def save_uploaded_file(uploaded_file, storage_root, allowed_extensions, max_size_mb=8):
    """
    Safely save an uploaded file with validation.
    
    Args:
        uploaded_file: werkzeug FileStorage object
        storage_root: Absolute path to directory where file will be saved
        allowed_extensions: Set of allowed file extensions
        max_size_mb: Maximum file size in MB (default 8)
    
    Returns:
        str: New secure filename (UUID-based)
    
    Raises:
        ValueError: If file is invalid (extension, size, etc.)
    """
    # Validate file is present
    if not uploaded_file or uploaded_file.filename == "":
        raise ValueError("No file provided")
    
    # Validate extension
    if not allowed_file(uploaded_file.filename, allowed_extensions):
        ext = uploaded_file.filename.rsplit(".", 1)[-1] if "." in uploaded_file.filename else "unknown"
        raise ValueError(f"File extension '.{ext}' is not allowed. Allowed: {', '.join(allowed_extensions)}")
    
    # Validate size (rough check)
    uploaded_file.seek(0, os.SEEK_END)
    size = uploaded_file.tell()
    max_bytes = max_size_mb * 1024 * 1024
    if size > max_bytes:
        raise ValueError(f"File size exceeds maximum ({max_size_mb} MB)")
    uploaded_file.seek(0)  # Reset to beginning for save
    
    # Generate secure filename (UUID + original extension)
    filename = secure_filename(uploaded_file.filename)
    ext = filename.rsplit(".", 1)[1] if "." in filename else ""
    new_filename = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    
    # Ensure storage directory exists
    storage_root = os.path.abspath(storage_root)
    os.makedirs(storage_root, exist_ok=True)
    
    # Save file
    destination = os.path.join(storage_root, new_filename)
    uploaded_file.save(destination)
    
    return new_filename


def safe_send_file(directory, filename):
    """
    Safely serve a file with path traversal protection.
    
    Args:
        directory: Absolute path to directory containing files
        filename: Filename to serve
    
    Returns:
        Flask response with file or 400/404 error
    """
    # Normalize paths
    directory = os.path.abspath(directory)
    file_path = os.path.abspath(os.path.join(directory, filename))
    
    # Prevent path traversal: ensure file is within directory
    if not file_path.startswith(directory + os.sep):
        abort(400, description="Invalid file path")
    
    # Verify file exists
    if not os.path.isfile(file_path):
        abort(404, description="File not found")
    
    # Serve file
    return send_from_directory(
        directory,
        os.path.basename(file_path),
        as_attachment=True,
        download_name=os.path.basename(file_path)
    )


def validate_file_ownership(user_email, file_owner_email):
    """
    Check if a user owns a file (basic ownership check).
    
    Args:
        user_email: Current user's email
        file_owner_email: File owner's email from database
    
    Returns:
        bool: True if user is owner, False otherwise
    """
    return user_email.lower() == file_owner_email.lower()
