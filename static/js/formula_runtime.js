(function () {
  function tokenize(expression) {
    // Regex matches variables/function names, numbers (including floats), and math operators/brackets/commas
    const regex = /\s*([a-zA-Z_][a-zA-Z0-9_]*|[0-9]*\.?[0-9]+|[\+\-\*\/\(\),])\s*/g;
    const matches = [];
    let match;
    while ((match = regex.exec(expression)) !== null) {
      if (match[1].trim()) {
        matches.push(match[1]);
      }
    }
    return matches;
  }

  function validateAggregateSyntax(expression) {
    const source = expression || "";
    const helper = "SUM_MONTHS";
    let index = 0;

    while (index < source.length) {
      const foundAt = source.indexOf(helper, index);
      if (foundAt === -1) break;

      const before = foundAt > 0 ? source[foundAt - 1] : "";
      const afterName = source[foundAt + helper.length] || "";
      if (/[A-Za-z0-9_]/.test(before) || /[A-Za-z0-9_]/.test(afterName)) {
        index = foundAt + helper.length;
        continue;
      }

      let cursor = foundAt + helper.length;
      while (/\s/.test(source[cursor] || "")) cursor += 1;
      if (source[cursor] !== "(") {
        return { valid: false, error: "SUM_MONTHS can only aggregate a monthly field." };
      }

      const start = cursor + 1;
      let depth = 1;
      cursor += 1;
      while (cursor < source.length && depth > 0) {
        if (source[cursor] === "(") depth += 1;
        else if (source[cursor] === ")") depth -= 1;
        cursor += 1;
      }
      if (depth !== 0) {
        return { valid: false, error: "SUM_MONTHS can only aggregate a monthly field." };
      }

      const inner = source.slice(start, cursor - 1).trim();
      if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(inner)) {
        return { valid: false, error: "SUM_MONTHS can only aggregate a monthly field." };
      }
      index = cursor;
    }

    return { valid: true, error: "" };
  }

  function usesAggregateHelper(expression) {
    if (!expression) return false;
    return tokenize(expression).some((token) => token === 'SUM_MONTHS');
  }

  const precedence = {
    '+': 1,
    '-': 1,
    '*': 2,
    '/': 2
  };

  function evaluateFormulaJS(expression, values) {
    if (!expression) return null;

    try {
      const aggregateValidation = validateAggregateSyntax(expression);
      if (!aggregateValidation.valid) {
        return null;
      }
      const tokens = tokenize(expression);
      const outputQueue = [];
      const operatorStack = [];

      for (let i = 0; i < tokens.length; i++) {
        const token = tokens[i];

        // 1. If token is a number, push to output queue
        if (!isNaN(parseFloat(token)) && isFinite(token)) {
          outputQueue.push({ type: 'NUMBER', value: parseFloat(token) });
        }
        // 2. If token is a supported function, push to operator stack
        else if (token === 'min' || token === 'max' || token === 'SUM_MONTHS') {
          operatorStack.push({ type: 'FUNCTION', value: token });
        }
        // 3. Comma argument separator
        else if (token === ',') {
          while (operatorStack.length > 0 && operatorStack[operatorStack.length - 1].value !== '(') {
            outputQueue.push(operatorStack.pop());
          }
          if (operatorStack.length === 0) {
            return null; // Syntax error: mismatch parenthesis or comma
          }
        }
        // 4. Operators
        else if (precedence[token] !== undefined) {
          const o1 = token;
          while (
            operatorStack.length > 0 &&
            precedence[operatorStack[operatorStack.length - 1].value] >= precedence[o1]
          ) {
            outputQueue.push(operatorStack.pop());
          }
          operatorStack.push({ type: 'OPERATOR', value: o1 });
        }
        // 5. Left parenthesis
        else if (token === '(') {
          operatorStack.push({ type: 'PARENTHESIS', value: '(' });
        }
        // 6. Right parenthesis
        else if (token === ')') {
          while (operatorStack.length > 0 && operatorStack[operatorStack.length - 1].value !== '(') {
            outputQueue.push(operatorStack.pop());
          }
          if (operatorStack.length === 0) {
            return null; // Syntax error: mismatch parenthesis
          }
          operatorStack.pop(); // Pop '('

          // If top of stack is a function, pop it to output queue
          if (operatorStack.length > 0 && operatorStack[operatorStack.length - 1].type === 'FUNCTION') {
            outputQueue.push(operatorStack.pop());
          }
        }
        // 7. Variable / Field Code
        else {
          let val = values[token];
          // Support values format where it's { raw_value, calculated_value }
          if (val && typeof val === 'object') {
            val = val.raw_value;
          }
          if (val === undefined || val === null || val === '') {
            return null; // Operand not filled yet, return null (waiting for input)
          }
          const numVal = parseFloat(val);
          if (isNaN(numVal)) {
            return null; // Invalid numeric value, return null
          }
          outputQueue.push({ type: 'NUMBER', value: numVal });
        }
      }

      while (operatorStack.length > 0) {
        const op = operatorStack.pop();
        if (op.value === '(' || op.value === ')') {
          return null; // Syntax error: mismatch parenthesis
        }
        outputQueue.push(op);
      }

      // Evaluate postfix (RPN)
      const evalStack = [];
      for (let i = 0; i < outputQueue.length; i++) {
        const item = outputQueue[i];
        if (item.type === 'NUMBER') {
          evalStack.push(item.value);
        } else if (item.type === 'OPERATOR') {
          if (evalStack.length < 2) return null;
          const b = evalStack.pop();
          const a = evalStack.pop();
          let res = 0;
          if (item.value === '+') res = a + b;
          else if (item.value === '-') res = a - b;
          else if (item.value === '*') res = a * b;
          else if (item.value === '/') {
            if (b === 0) return null; // Division by zero
            res = a / b;
          }
          evalStack.push(res);
        } else if (item.type === 'FUNCTION') {
          if (item.value === 'SUM_MONTHS') {
            if (evalStack.length < 1) return null;
            evalStack.push(evalStack.pop());
            continue;
          }
          if (evalStack.length < 2) return null;
          const b = evalStack.pop();
          const a = evalStack.pop();
          let res = 0;
          if (item.value === 'min') res = Math.min(a, b);
          else if (item.value === 'max') res = Math.max(a, b);
          evalStack.push(res);
        }
      }

      if (evalStack.length !== 1) return null;
      return evalStack[0];
    } catch (e) {
      console.warn("Formula evaluation error on frontend:", e);
      return null;
    }
  }

  window.FormulaRuntime = {
    evaluate: evaluateFormulaJS,
    validate: validateAggregateSyntax,
    usesAggregate: usesAggregateHelper
  };
})();
