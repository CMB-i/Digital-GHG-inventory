from app.modules.FORMBLD.model import Field, FieldVersion


NUMERIC_FIELD_TYPES = {"integer", "number", "decimal", "float", "numeric"}


def is_formula_compatible_field(field_version):
    field_type = (field_version.field_type or "").strip().lower()
    config = field_version.field_config or {}
    configured_type = str(
        config.get("result_type")
        or config.get("value_type")
        or config.get("data_type")
        or ""
    ).lower()
    return (
        field_type in NUMERIC_FIELD_TYPES
        or configured_type in NUMERIC_FIELD_TYPES
        or config.get("is_numeric") is True
    )


def get_formula_compatible_fields(form_version_id):
    if not form_version_id:
        return []

    rows = (
        FieldVersion.query.with_entities(FieldVersion, Field)
        .join(Field, Field.id == FieldVersion.field_id)
        .filter(
            FieldVersion.form_version_id == form_version_id,
            Field.is_deleted.is_(False),
        )
        .order_by(Field.display_order.asc(), Field.id.asc())
        .all()
    )
    return [
        {
            "field_id": field_version.field_id,
            "field_version_id": field_version.id,
            "field_code": field.field_code,
            "field_name": field_version.field_name,
            "field_type": field_version.field_type,
        }
        for field_version, field in rows
        if is_formula_compatible_field(field_version)
    ]
