from datetime import datetime, timezone
from simpleeval import FunctionNotDefined, NameNotDefined, SimpleEval

from app.database import db
from app.modules.FRMULA.model import Formula, FormulaVersion


ALLOWED_FORMULA_FUNCTIONS = {
    "min": min,
    "max": max,
}


class FormulaValidationError(ValueError):
    pass


def validate_formula(expression, operand_names):
    cleaned_expression = (expression or "").strip()
    if not cleaned_expression:
        raise FormulaValidationError("Formula expression is required.")

    evaluator = SimpleEval(
        names={name: 1.0 for name in operand_names},
        functions=ALLOWED_FORMULA_FUNCTIONS,
    )
    try:
        result = evaluator.eval(cleaned_expression)
    except NameNotDefined as error:
        raise FormulaValidationError(f"Unknown formula field: {error}.") from error
    except FunctionNotDefined as error:
        raise FormulaValidationError("Only min() and max() functions are supported.") from error
    except TypeError as error:
        raise FormulaValidationError("min() and max() require numeric operands.") from error
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
        raise FormulaValidationError("Only min() and max() functions are supported.") from error
    except TypeError as error:
        raise FormulaValidationError("min() and max() require numeric operands.") from error
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


def create_formula(name, code, expression, tokens, user_id):
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
        
    # Validate it works (optional, but a great safeguard)
    validate_formula(version.expression, set((version.tokens or {}).keys()))

    # Mark published
    version.published_at = datetime.now(timezone.utc)
    version.published_by = user_id
    
    formula = get_formula(version.formula_id)
    formula.current_version_id = version.id
    formula.updated_by = user_id
    
    return version
