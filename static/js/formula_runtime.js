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

  const precedence = {
    '+': 1,
    '-': 1,
    '*': 2,
    '/': 2
  };

  function evaluateFormulaJS(expression, values) {
    if (!expression) return null;

    try {
      const tokens = tokenize(expression);
      const outputQueue = [];
      const operatorStack = [];

      for (let i = 0; i < tokens.length; i++) {
        const token = tokens[i];

        // 1. If token is a number, push to output queue
        if (!isNaN(parseFloat(token)) && isFinite(token)) {
          outputQueue.push({ type: 'NUMBER', value: parseFloat(token) });
        }
        // 2. If token is min or max function, push to operator stack
        else if (token === 'min' || token === 'max') {
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
    evaluate: evaluateFormulaJS
  };
})();
