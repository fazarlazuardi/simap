import os
import uuid
from django.core.exceptions import ValidationError

# Batas Ukuran File Maksimal (5 MB)
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024

# Ekstensi dan Header Biner (Magic Bytes) yang Diizinkan
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'xlsx', 'docx'}

MAGIC_BYTES_SIGNATURES = {
    'pdf': [b'%PDF-'],
    'png': [b'\x89PNG\r\n\x1a\n'],
    'jpg': [b'\xff\xd8\xff'],
    'jpeg': [b'\xff\xd8\xff'],
    'xlsx': [b'PK\x03\x04'],
    'docx': [b'PK\x03\x04'],
}

def validate_secure_document(file_obj):
    """
    Validasi keamanan file upload:
    1. Memeriksa ukuran maksimal file (5MB).
    2. Memeriksa ekstensi file yang diizinkan.
    3. Memeriksa header biner (Magic Bytes) awal file.
    """
    if not file_obj:
        return

    # 1. Check Ukuran File
    if file_obj.size > MAX_FILE_SIZE_BYTES:
        raise ValidationError(f"Ukuran file {file_obj.name} melebihi batas maksimal 5 MB.")

    # 2. Check Ekstensi
    ext = os.path.splitext(file_obj.name)[1][1:].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"Ekstensi file .{ext} tidak diizinkan untuk diunggah.")

    # 3. Check Magic Bytes Biner
    expected_signatures = MAGIC_BYTES_SIGNATURES.get(ext)
    if expected_signatures:
        file_obj.seek(0)
        header_bytes = file_obj.read(16)
        file_obj.seek(0)  # Reset pointer file ke awal

        matched = any(header_bytes.startswith(sig) for sig in expected_signatures)
        if not matched:
            raise ValidationError(f"Format biner file {file_obj.name} tidak sesuai dengan ekstensi .{ext}.")


def secure_random_upload_path(instance, filename):
    """
    Menghasilkan nama file acak yang aman (UUID4) untuk mencegah Path Traversal.
    """
    ext = filename.split('.')[-1].lower() if '.' in filename else 'bin'
    secure_name = f"{uuid.uuid4().hex}.{ext}"
    return os.path.join('uploads', secure_name)
