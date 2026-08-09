import os
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

# Allowed standard document & image file extensions for SIMAP BAZNAS
ALLOWED_FILE_EXTENSIONS = ['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png']

# Standard file extension validator instance
validate_file_extension = FileExtensionValidator(
    allowed_extensions=ALLOWED_FILE_EXTENSIONS,
    message="Format file tidak didukung. Format yang diizinkan: PDF, DOC, DOCX, JPG, JPEG, PNG."
)

# Maximum file size validator (Default: 10 MB = 10 * 1024 * 1024 bytes)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

def validate_file_size(file_obj):
    """
    Validasi batas maksimum ukuran file upload (Max 10MB).
    """
    if file_obj and hasattr(file_obj, 'size'):
        if file_obj.size > MAX_FILE_SIZE_BYTES:
            max_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
            raise ValidationError(f"Ukuran file terlalu besar ({file_obj.size / (1024 * 1024):.2f} MB). Ukuran maksimum yang diizinkan adalah {max_mb:.0f} MB.")
