class FormulaParser {
  constructor(expression, values) {
    this.tokens = expression.match(/[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|[()+\-*/,]/g) || [];
    const normalizedExpression = expression.replace(/\s+/g, "");
    if (this.tokens.join("") !== normalizedExpression) {
      throw new Error("Formula contains unsupported characters.");
    }
    this.position = 0;
    this.values = values;
  }

  parse() {
    const result = this.parseExpression();
    if (this.position !== this.tokens.length) {
      throw new Error("Unexpected formula token.");
    }
    return result;
  }

  parseExpression() {
    let value = this.parseTerm();
    while (this.peek() === "+" || this.peek() === "-") {
      const operator = this.next();
      const right = this.parseTerm();
      value = operator === "+" ? value + right : value - right;
    }
    return value;
  }

  parseTerm() {
    let value = this.parseFactor();
    while (this.peek() === "*" || this.peek() === "/") {
      const operator = this.next();
      const right = this.parseFactor();
      value = operator === "*" ? value * right : value / right;
    }
    return value;
  }

  parseFactor() {
    const token = this.next();
    if (token === "-") {
      return -this.parseFactor();
    }
    if (token === "(") {
      const value = this.parseExpression();
      this.expect(")");
      return value;
    }
    if (/^\d/.test(token || "")) {
      return Number(token);
    }
    if (/^[A-Za-z_]/.test(token || "")) {
      if (this.peek() === "(") {
        if (token !== "min" && token !== "max") {
          throw new Error("Only min() and max() functions are supported.");
        }
        this.next();
        const values = [this.parseExpression()];
        while (this.peek() === ",") {
          this.next();
          values.push(this.parseExpression());
        }
        this.expect(")");
        if (values.length < 2) {
          throw new Error(`${token}() requires at least two numeric operands.`);
        }
        return token === "min" ? Math.min(...values) : Math.max(...values);
      }
      if (!(token in this.values)) {
        throw new Error(`Unknown numeric field: ${token}.`);
      }
      return this.values[token];
    }
    throw new Error("Invalid formula.");
  }

  peek() {
    return this.tokens[this.position];
  }

  next() {
    return this.tokens[this.position++];
  }

  expect(token) {
    if (this.next() !== token) {
      throw new Error(`Expected ${token}.`);
    }
  }
}

const expressionInput = document.getElementById("expression");
document.querySelectorAll(".formula-field").forEach((button) => {
  button.addEventListener("click", () => {
    if (!expressionInput) {
      return;
    }
    const separator = expressionInput.value.trim() ? " " : "";
    expressionInput.value += `${separator}${button.dataset.fieldCode}`;
    expressionInput.focus();
  });
});

const previewButton = document.getElementById("preview_formula");
if (previewButton && expressionInput) {
  previewButton.addEventListener("click", () => {
    const resultElement = document.getElementById("formula_preview_result");
    const values = {};
    document.querySelectorAll(".formula-preview-value").forEach((input) => {
      values[input.dataset.fieldCode] = Number(input.value);
    });
    try {
      const result = new FormulaParser(expressionInput.value, values).parse();
      if (!Number.isFinite(result)) {
        throw new Error("Formula result must be a finite number.");
      }
      resultElement.className = "mt-3 text-sm text-emerald-700";
      resultElement.textContent = `Preview result: ${result}`;
    } catch (error) {
      resultElement.className = "mt-3 text-sm text-red-700";
      resultElement.textContent = error.message;
    }
  });
}
