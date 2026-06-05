import os
import uuid
from werkzeug.utils import secure_filename

# Upload directory: workspace/uploads
UPLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'uploads'))

def get_storage_folder():
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    return UPLOAD_FOLDER

def save_file(file_storage, folder="proofs"):
    """
    Saves a Flask FileStorage object to the local directory.
    Returns a dict with: storage_key, original_name, mime_type, file_size_bytes
    """
    if not file_storage or not file_storage.filename:
        raise ValueError("No file provided.")
        
    original_name = secure_filename(file_storage.filename)
    if not original_name:
        original_name = "uploaded_file"
        
    # Generate unique ID and relative key
    unique_id = uuid.uuid4().hex
    ext = os.path.splitext(original_name)[1]
    storage_key = f"{folder}/{unique_id}{ext}"
    
    # Absolute path for saving
    save_path = os.path.join(get_storage_folder(), folder, f"{unique_id}{ext}")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    # Save file content
    file_storage.save(save_path)
    
    # Measure size
    size_bytes = os.path.getsize(save_path)
    
    return {
        "storage_key": storage_key,
        "original_name": original_name,
        "mime_type": file_storage.content_type or "application/octet-stream",
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
