def validate_required_fields(data, required_fields):
    missing = [
        field
        for field in required_fields
        if data.get(field) in (None, "")
    ]
    return missing


def is_non_empty_string(value):
    return isinstance(value, str) and bool(value.strip())
