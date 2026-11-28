'use strict';

function statements(ts, fn, source) {
  let count = 0;
  const names = new Set(fn.parameters.filter(p => ts.isIdentifier(p.name)).map(p => p.name.text));
  function group(node) {
    return ts.isBlock(node) ? Array.from(node.statements, lower) : [lower(node)];
  }
  function lower(node) {
    if (++count > 96) throw new RangeError('control-flow operation limit');
    let op = 'simple', roots = [node], body = [], otherwise = [];
    if (ts.isIfStatement(node)) {
      op = 'branch';
      roots = [node.expression];
      body = group(node.thenStatement);
      otherwise = node.elseStatement ? group(node.elseStatement) : [];
    } else if (ts.isWhileStatement(node)) {
      op = 'loop';
      roots = [node.expression];
      body = group(node.statement);
    } else if (ts.isForOfStatement(node) && !node.awaitModifier &&
        ts.isVariableDeclarationList(node.initializer) && node.initializer.declarations.length === 1 &&
        ts.isIdentifier(node.initializer.declarations[0].name)) {
      const name = node.initializer.declarations[0].name.text;
      op = names.has(name) ? 'unknown' : 'loop';
      names.add(name);
      roots = [node.expression];
      body = group(node.statement);
      const line = source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;
      body.unshift({op: 'bind', line, end: line, reads: [], writes: [name], aliases: {}, body: [], otherwise: []});
    } else if (ts.isReturnStatement(node)) op = 'return';
    else if (ts.isThrowStatement(node)) op = 'raise';
    else if (ts.isBreakStatement(node) && !node.label) op = 'break';
    else if (ts.isContinueStatement(node) && !node.label) op = 'continue';
    else if (!ts.isVariableStatement(node) && !ts.isExpressionStatement(node) && !ts.isEmptyStatement(node)) {
      op = 'unknown';
      roots = [];
    }
    const reads = new Set(), writes = new Set(), aliases = Object.create(null);
    function visit(x) {
      if (ts.isFunctionLike(x) || ts.isAwaitExpression(x) || ts.isConditionalExpression(x)) {
        op = 'unknown';
        return;
      }
      if (ts.isBinaryExpression(x)) {
        const token = x.operatorToken.kind;
        if ([ts.SyntaxKind.AmpersandAmpersandToken, ts.SyntaxKind.BarBarToken, ts.SyntaxKind.QuestionQuestionToken].includes(token)) op = 'unknown';
        if (token >= ts.SyntaxKind.FirstAssignment && token <= ts.SyntaxKind.LastAssignment && ts.isIdentifier(x.left)) {
          writes.add(x.left.text);
          if (token !== ts.SyntaxKind.EqualsToken) reads.add(x.left.text);
          else if (ts.isIdentifier(x.right)) aliases[x.left.text] = x.right.text;
          visit(x.right);
          return;
        }
      }
      if (ts.isVariableDeclaration(x)) {
        if (!ts.isIdentifier(x.name) || names.has(x.name.text)) op = 'unknown';
        else {
          writes.add(x.name.text);
          names.add(x.name.text);
          if (x.initializer && ts.isIdentifier(x.initializer)) aliases[x.name.text] = x.initializer.text;
        }
        if (x.initializer) visit(x.initializer);
        return;
      }
      if ((ts.isPrefixUnaryExpression(x) || ts.isPostfixUnaryExpression(x)) &&
          [ts.SyntaxKind.PlusPlusToken, ts.SyntaxKind.MinusMinusToken].includes(x.operator) && ts.isIdentifier(x.operand)) writes.add(x.operand.text);
      if (ts.isPropertyAccessExpression(x)) {
        visit(x.expression);
        return;
      }
      if (ts.isIdentifier(x)) reads.add(x.text);
      else ts.forEachChild(x, visit);
    }
    roots.forEach(visit);
    if (reads.size + writes.size > 64 || [...reads, ...writes].some(name => name.length > 128)) {
      throw new RangeError('control-flow symbol limit');
    }
    return {op, line: source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1,
      end: source.getLineAndCharacterOfPosition(node.end - 1).line + 1, reads: [...reads].sort(),
      writes: [...writes].sort(), aliases, body, otherwise};
  }
  try {
    return fn.body && ts.isBlock(fn.body) ? group(fn.body) : null;
  } catch (error) {
    if (error instanceof RangeError) return null;
    throw error;
  }
}

module.exports = {statements};
