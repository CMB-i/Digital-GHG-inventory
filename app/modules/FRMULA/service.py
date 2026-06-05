from simpleeval import FunctionNotDefined, NameNotDefined, SimpleEval


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
