import re


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Office/site contact numbers are allowed, so do not restrict to Indian mobile prefixes.
PHONE_RE = re.compile(r"^[0-9]{10}$")
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9 .,'_-]+$")
CODE_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class ValidationError(ValueError):
    pass


def validate_required_fields(data, required_fields):
    missing = [
        field
        for field in required_fields
        if data.get(field) in (None, "")
    ]
    return missing


def is_non_empty_string(value):
    return isinstance(value, str) and bool(value.strip())


def validate_email(value):
    email = (value or "").strip().lower()
    if not email:
        raise ValidationError("Email is required.")
    if len(email) > 255 or not EMAIL_RE.match(email):
        raise ValidationError("Enter a valid email address up to 255 characters.")
    return email


def validate_phone(value):
    phone = (value or "").strip()
    if not phone:
        return None

    if not PHONE_RE.fullmatch(phone):
        raise ValidationError("Enter a valid 10-digit phone number.")
    return phone


def validate_temporary_password(value):
    password = value or ""
    if len(password) < 8 or len(password) > 128:
        raise ValidationError("Temporary password must be 8-128 characters.")
    return password


def validate_full_name(value):
    full_name = (value or "").strip()
    if not full_name:
        raise ValidationError("Full name is required.")
    if len(full_name) > 255:
        raise ValidationError("Full name must be 255 characters or fewer.")
    if not SAFE_NAME_RE.match(full_name):
        raise ValidationError("Full name contains unsupported special characters.")
    return full_name


def validate_code(value, field_name="Code", max_length=100):
    code = (value or "").strip()
    if not code:
        raise ValidationError(f"{field_name} is required.")
    if len(code) > max_length or not CODE_RE.match(code):
        raise ValidationError(f"{field_name} must use only letters, numbers, underscore, or hyphen.")
    return code


def validate_text_length(value, field_name, max_length, required=False):
    text = (value or "").strip()
    if required and not text:
        raise ValidationError(f"{field_name} is required.")
    if len(text) > max_length:
        raise ValidationError(f"{field_name} must be {max_length} characters or fewer.")
    return text
