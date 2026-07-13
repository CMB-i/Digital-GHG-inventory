from datetime import datetime, timezone
from simpleeval import FunctionNotDefined, NameNotDefined, SimpleEval

from app.database import db
from app.modules.FRMULA.model import Formula, FormulaVersion


ALLOWED_FORMULA_FUNCTIONS = {
    "min": min,
    "max": max,
}

AGGREGATE_FORMULA_FUNCTIONS = {"SUM_MONTHS"}


def sum_months(values):
    if values is None:
        raise FormulaValidationError("SUM_MONTHS requires monthly values.")
    if not isinstance(values, (list, tuple)):
        raise FormulaValidationError("SUM_MONTHS can only aggregate a monthly field.")

    total = 0.0
    for value in values:
        if value in (None, ""):
            raise FormulaValidationError("SUM_MONTHS cannot calculate while a month is blank.")
        try:
            total += float(value)
        except (TypeError, ValueError) as error:
            raise FormulaValidationError("SUM_MONTHS requires numeric monthly values.") from error
    return total


ALLOWED_FORMULA_FUNCTIONS["SUM_MONTHS"] = sum_months


def aggregate_operand_names(expression):
    import re

    cleaned_expression = expression or ""
    names = set()
    for helper in AGGREGATE_FORMULA_FUNCTIONS:
        pattern = rf"\b{helper}\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)"
        names.update(re.findall(pattern, cleaned_expression))
    return names


class FormulaValidationError(ValueError):
    pass


def validate_formula(expression, operand_names):
    cleaned_expression = (expression or "").strip()
    if not cleaned_expression:
        raise FormulaValidationError("Formula expression is required.")

    aggregate_names = aggregate_operand_names(cleaned_expression)
    names = {
        name: ([1.0] * 12 if name in aggregate_names else 1.0)
        for name in operand_names
    }

    evaluator = SimpleEval(
        names=names,
        functions=ALLOWED_FORMULA_FUNCTIONS,
    )
    try:
        result = evaluator.eval(cleaned_expression)
    except NameNotDefined as error:
        raise FormulaValidationError(f"Unknown formula field: {error}.") from error
    except FunctionNotDefined as error:
        raise FormulaValidationError("Only min(), max(), and SUM_MONTHS() functions are supported.") from error
    except TypeError as error:
        raise FormulaValidationError("Formula functions require numeric operands.") from error
    except ZeroDivisionError:
        raise FormulaValidationError("Division by zero in formula.")
    except Exception as error:
        raise FormulaValidationError(f"Invalid formula: {error}.") from error

    if not isinstance(result, (int, float)):
        raise FormulaValidationError("Formula must produce a numeric result.")
    return result


def evaluate_formula(expression, field_values, value_set_snapshot=None):
    cleaned_expression = (expression or "").strip()
    if not cleaned_expression:
        raise FormulaValidationError("Formula expression is required.")

    names = {}
    if field_values:
        for k, v in field_values.items():
            if v is not None and v != "":
                try:
                    names[k] = float(v)
                except (ValueError, TypeError):
                    names[k] = v

    if value_set_snapshot:
        for k, v in value_set_snapshot.items():
            if k in names:
                continue
            if v is not None and v != "":
                try:
                    names[k] = float(v)
                except (ValueError, TypeError):
                    names[k] = v

    evaluator = SimpleEval(
        names=names,
        functions=ALLOWED_FORMULA_FUNCTIONS,
    )
    try:
        result = evaluator.eval(cleaned_expression)
    except NameNotDefined as error:
        raise FormulaValidationError(f"Unknown formula variable: {error}.") from error
    except FunctionNotDefined as error:
        raise FormulaValidationError("Only min(), max(), and SUM_MONTHS() functions are supported.") from error
    except TypeError as error:
        raise FormulaValidationError("Formula functions require numeric operands.") from error
    except ZeroDivisionError:
        raise FormulaValidationError("Division by zero in formula.")
    except Exception as error:
        raise FormulaValidationError(f"Invalid formula evaluation: {error}.") from error

    if not isinstance(result, (int, float)):
        raise FormulaValidationError("Formula must produce a numeric result.")
    return result


def list_formulas():
    return Formula.query.filter_by(is_deleted=False).all()


def get_formula(formula_id):
    return Formula.query.filter_by(id=formula_id, is_deleted=False).one_or_none()


def get_formula_by_code(code):
    return Formula.query.filter_by(code=code, is_deleted=False).one_or_none()


def create_formula(name, code, expression, tokens, user_id, form_id=None):
    if not name or not name.strip():
        raise ValueError("Formula name is required.")
    if not code or not code.strip():
        raise ValueError("Formula code is required.")

    existing = get_formula_by_code(code)
    if existing:
        raise ValueError(f"Formula with code '{code}' already exists.")

    formula = Formula(
        name=name.strip(),
        code=code.strip(),
        form_id=form_id,
        created_by=user_id,
        updated_by=user_id
    )
    db.session.add(formula)
    db.session.flush()
    
    version = FormulaVersion(
        formula_id=formula.id,
        version_number=1,
        expression=expression,
        tokens=tokens or {},
        created_by=user_id
    )
    db.session.add(version)
    db.session.flush()
    
    return formula


def create_new_formula_draft(formula_id, expression, tokens, user_id):
    formula = get_formula(formula_id)
    if not formula:
        raise ValueError("Formula not found.")

    if formula.current_version_id is not None:
        raise ValueError(
            "This formula is published and cannot be revised. Create a new formula instead."
        )

    # Check if there is already a draft (published_at is None)
    pending_draft = FormulaVersion.query.filter_by(
        formula_id=formula_id,
        published_at=None
    ).first()
    
    if pending_draft:
        # Update existing draft
        pending_draft.expression = expression
        pending_draft.tokens = tokens or {}
        pending_draft.created_by = user_id
        return pending_draft
        
    max_ver = db.session.query(db.func.max(FormulaVersion.version_number)).filter_by(
        formula_id=formula_id
    ).scalar() or 0
    
    new_version = FormulaVersion(
        formula_id=formula_id,
        version_number=max_ver + 1,
        expression=expression,
        tokens=tokens or {},
        created_by=user_id
    )
    db.session.add(new_version)
    db.session.flush()
    return new_version


def publish_formula_version(version_id, user_id):
    version = FormulaVersion.query.get(version_id)
    if not version:
        raise ValueError("Formula version not found.")
    if version.published_at is not None:
        raise ValueError("Formula version is already published.")
        
    tokens_keys = set((version.tokens or {}).keys())
    
    # Cross-check tokens against actual live form field codes and current value set entry codes.
    from app.modules.FORMBLD.model import Field
    active_field_codes = {f.field_code for f in Field.query.filter_by(is_deleted=False).all()}
    
    from app.modules.VALSET.model import ValueSet, ValueSetVersion, ValueSetEntry
    current_valsets = (
        ValueSet.query.filter_by(is_deleted=False)
        .join(ValueSetVersion, ValueSetVersion.id == ValueSet.current_version_id)
        .all()
    )
    active_valset_codes = set()
    for vs in current_valsets:
        entries = ValueSetEntry.query.filter_by(
            value_set_version_id=vs.current_version_id,
            is_deleted=False,
            is_active=True
        ).all()
        for entry in entries:
            active_valset_codes.add(entry.entry_code)
            
    for t_key in tokens_keys:
        if t_key not in active_field_codes and t_key not in active_valset_codes:
            raise FormulaValidationError(f"Referenced field/constant '{t_key}' does not exist as an active field or value set entry in the system.")

    # Validate it works (optional, but a great safeguard)
    validate_formula(version.expression, tokens_keys)

    # Mark published
    version.published_at = datetime.now(timezone.utc)
    version.published_by = user_id
    
    formula = get_formula(version.formula_id)
    formula.current_version_id = version.id
    formula.updated_by = user_id
    
    return version
