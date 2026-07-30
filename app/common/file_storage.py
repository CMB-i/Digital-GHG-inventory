import os
import uuid
import logging
from flask import current_app, has_app_context
from werkzeug.utils import secure_filename

# Upload directory: workspace/uploads
UPLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'uploads'))

def get_storage_folder():
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    return UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.webp', '.xls', '.xlsx', '.csv'}
ALLOWED_MIMETYPES = {
    'application/pdf',
    'image/jpeg',
    'image/png',
    'image/webp',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/csv',
    'application/csv',
    'text/plain',
}

DEFAULT_MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024


def _configured_max_upload_size():
    if has_app_context():
        return int(current_app.config.get("MAX_PROOF_UPLOAD_BYTES") or DEFAULT_MAX_UPLOAD_SIZE_BYTES)
    return DEFAULT_MAX_UPLOAD_SIZE_BYTES


def _stream_size(file_storage):
    content_length = getattr(file_storage, "content_length", None)
    if content_length:
        return content_length

    stream = getattr(file_storage, "stream", None)
    if not stream or not hasattr(stream, "tell") or not hasattr(stream, "seek"):
        return None

    position = stream.tell()
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(position)
    return size


def validate_file_size(file_storage, max_size_bytes=None):
    limit = int(max_size_bytes or _configured_max_upload_size())
    size = _stream_size(file_storage)
    if size is not None and size > limit:
        limit_mb = limit / (1024 * 1024)
        raise ValueError(f"File is too large. Maximum size is {limit_mb:.1f} MB.")
    return size


def delete_file(storage_key):
    if not storage_key:
        return True
    try:
        path = get_file_path(storage_key)
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        logger = current_app.logger if has_app_context() else logging.getLogger("file_storage")
        logger.exception("Failed to remove stored upload during cleanup.")
        return False
    return True


def save_file(file_storage, folder="proofs", max_size_bytes=None):
    """
    Saves a Flask FileStorage object to the local directory.
    Returns a dict with: storage_key, original_name, mime_type, file_size_bytes
    """
    if not file_storage or not file_storage.filename:
        raise ValueError("No file provided.")
        
    original_name = secure_filename(file_storage.filename)
    if not original_name:
        original_name = "uploaded_file"
        
    ext = os.path.splitext(original_name)[1].lower()
    mime_type = file_storage.content_type or "application/octet-stream"
    
    if ext not in ALLOWED_EXTENSIONS or mime_type.lower() not in ALLOWED_MIMETYPES:
        raise ValueError(
            f"File type not allowed. Allowed extensions are: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    limit = int(max_size_bytes or _configured_max_upload_size())
    validate_file_size(file_storage, max_size_bytes=limit)
        
    # Generate unique ID and relative key
    unique_id = uuid.uuid4().hex
    storage_key = f"{folder}/{unique_id}{ext}"
    
    # Absolute path for saving
    save_path = os.path.join(get_storage_folder(), folder, f"{unique_id}{ext}")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    # Save file content
    file_storage.save(save_path)
    
    # Measure size
    size_bytes = os.path.getsize(save_path)
    if size_bytes > limit:
        os.remove(save_path)
        limit_mb = limit / (1024 * 1024)
        raise ValueError(f"File is too large. Maximum size is {limit_mb:.1f} MB.")
    
    return {
        "storage_key": storage_key,
        "original_name": original_name,
        "mime_type": mime_type,
        "file_size_bytes": size_bytes
    }

def get_file_path(storage_key):
    """
    Returns the absolute path to a file given its storage key.
    """
    # Prevent directory traversal attacks
    normalized_key = os.path.normpath(storage_key).lstrip('/')
    if normalized_key.startswith('..') or os.path.isabs(normalized_key):
        raise ValueError("Invalid storage key path.")
    return os.path.join(get_storage_folder(), normalized_key)
