'use strict';
// Source-only parser using the same pinned TypeScript compiler as structure inspection.
// This file never imports, transpiles for execution, or evaluates submitted source.
const ts = require('typescript');
const {analyzeStructure} = require('./node_worker.cjs');

function extract(sourceText, filePath) {
  if (Buffer.byteLength(sourceText, 'utf8') > 200000) throw new Error('Source size limit');
  const kind = /\.tsx$/i.test(filePath) ? ts.ScriptKind.TSX : /\.jsx$/i.test(filePath) ? ts.ScriptKind.JSX :
    /\.(ts|mts|cts)$/i.test(filePath) ? ts.ScriptKind.TS : ts.ScriptKind.JS;
  const source = ts.createSourceFile(filePath, sourceText, ts.ScriptTarget.ES2022, true, kind);
  const line = n => source.getLineAndCharacterOfPosition(n.getStart(source)).line + 1;
  const end = n => source.getLineAndCharacterOfPosition(Math.max(0, n.end - 1)).line + 1;
  const diagnostics = source.parseDiagnostics.slice(0, 16).map(d => ({
    kind: 'SyntaxError', line: source.getLineAndCharacterOfPosition(d.start || 0).line + 1,
    message: 'TypeScript parser reported incomplete or invalid source (diagnostic ' + d.code + ').',
  }));
  if (diagnostics.length) return {functions: [], diagnostics};
  const structural = analyzeStructure({source: sourceText, entrypoint: '<discovery>'}, kind === ts.ScriptKind.TS ? 'typescript' : 'javascript');
  const isFunction = n => ts.isFunctionDeclaration(n) || ts.isFunctionExpression(n) || ts.isArrowFunction(n) ||
    ts.isMethodDeclaration(n) || ts.isGetAccessor(n) || ts.isSetAccessor(n) || ts.isConstructorDeclaration(n);
  const children = n => {const result = []; ts.forEachChild(n, child => {result.push(child);}); return result;};
  const symbol = n => {
    if (!n) return '';
    if (ts.isIdentifier(n)) return n.text.slice(0, 120);
    if (ts.isPropertyAccessExpression(n)) return (symbol(n.expression) + '.' + n.name.text).slice(0, 120);
    if (ts.isParenthesizedExpression(n) || ts.isAsExpression(n) || ts.isNonNullExpression(n)) return symbol(n.expression);
    return '';
  };
  const imports = {};
  for (const n of source.statements) {
    if (ts.isImportDeclaration(n) && n.importClause && n.moduleSpecifier && ts.isStringLiteral(n.moduleSpecifier)) {
      const clause = n.importClause;
      if (clause.name) imports[clause.name.text] = n.moduleSpecifier.text + '.default';
      if (clause.namedBindings && ts.isNamedImports(clause.namedBindings)) {
        for (const binding of clause.namedBindings.elements) imports[binding.name.text] = n.moduleSpecifier.text + '.' + (binding.propertyName || binding.name).text;
      }
    }
  }
  const functions = [];
  let count = 0, truncated = false;
  const stack = [[source, '']];
  while (stack.length) {
    const [node, scope] = stack.pop();
    if (++count > 50000) throw new Error('AST node limit');
    let nestedScope = scope;
    if (ts.isClassDeclaration(node) && node.name) nestedScope = scope ? scope + '.' + node.name.text : node.name.text;
    if (isFunction(node) && node.body) {
      const binding = node.name ? node.name.getText(source) :
        (node.parent && (ts.isVariableDeclaration(node.parent) || ts.isPropertyAssignment(node.parent) || ts.isPropertyDeclaration(node.parent))) ? node.parent.name.getText(source) :
        ts.isConstructorDeclaration(node) ? 'constructor' : '<anonymous@' + line(node) + '>';
      nestedScope = scope ? scope + '.' + binding : binding;
      if (functions.length >= 128) { truncated = true; }
      else {
        const facts = [], calls = [], returns = [], assertions = [], collections = {};
        const fact = (kind, n, subject = '', related = '', detail = '', binding = '', args = []) => {
          if (facts.length < 128) facts.push({kind, line: line(n), end_line: end(n), subject: subject.slice(0, 120), related: related.slice(0, 120), detail, binding, arguments: args.slice(0, 32)});
          else truncated = true;
        };
        const collectionKind = value => !value ? null : ts.isArrayLiteralExpression(value) ? 'sequence' :
          ts.isObjectLiteralExpression(value) ? 'mapping' : ts.isNewExpression(value) ?
          ({Set: 'set', Map: 'mapping', Array: 'sequence'}[symbol(value.expression)] || null) : null;
        const pending = [node.body];
        let loops = 0, branches = 0;
        while (pending.length) {
          const n = pending.pop();
          if (n !== node.body && isFunction(n)) continue;
          if (ts.isVariableDeclaration(n) && n.initializer) {
            const collection = collectionKind(n.initializer);
            if (collection) {collections[symbol(n.name)] = collection; fact('collection_binding', n, symbol(n.name), collection);}
          }
          if (ts.isBinaryExpression(n) && n.operatorToken.kind === ts.SyntaxKind.EqualsToken && ts.isElementAccessExpression(n.left)) {
            fact('indexed_write', n, symbol(n.left.expression), symbol(n.left.argumentExpression));
          }
          if (ts.isElementAccessExpression(n)) fact('indexed_read', n, symbol(n.expression), symbol(n.argumentExpression));
          if (ts.isForOfStatement(n) || ts.isForInStatement(n)) {
            loops++; fact('iteration', n, symbol(n.expression));
            if (ts.isElementAccessExpression(n.expression)) fact('adjacency_iteration', n, symbol(n.expression.expression), symbol(n.expression.argumentExpression),
              'Iterates an indexed collection; graph interpretation requires corroborating traversal evidence.',
              ts.isVariableDeclarationList(n.initializer) ? symbol(n.initializer.declarations[0]?.name) : symbol(n.initializer));
          }
          if (ts.isForStatement(n) || ts.isWhileStatement(n) || ts.isDoStatement(n)) {
            loops++;
            const condition = n.expression;
            fact('while_loop', n, condition && ts.isPropertyAccessExpression(condition) && condition.name.text === 'length' ? symbol(condition.expression) : symbol(condition));
          }
          if (ts.isIfStatement(n)) {
            branches++; fact('conditional', n);
            const body = ts.isBlock(n.thenStatement) ? n.thenStatement.statements : [n.thenStatement];
            if (body.some(ts.isReturnStatement)) fact('conditional_return', n);
          }
          if (ts.isCallExpression(n)) {
            const target = symbol(n.expression);
            if (target && calls.length < 64) {calls.push({target, line: line(n)}); fact('call', n, target);}
            if (target === binding || target === 'this.' + binding) fact('direct_recursion', n, target, '', 'Lexical self-call, not runtime binding proof.', '', n.arguments.map(symbol));
            if (ts.isPropertyAccessExpression(n.expression)) {
              const receiver = symbol(n.expression.expression), method = n.expression.name.text;
              const parent = n.parent;
              const assigned = ts.isVariableDeclaration(parent) ? symbol(parent.name) :
                ts.isBinaryExpression(parent) && parent.operatorToken.kind === ts.SyntaxKind.EqualsToken ? symbol(parent.left) : '';
              if (method === 'shift') fact('fifo_remove', n, receiver, assigned);
              if (method === 'pop') fact('lifo_remove', n, receiver, assigned);
              const kinds = {push: 'sequence_append', add: 'set_add', sort: 'sorting_call', filter: 'filtering_call',
                find: 'searching_call', findIndex: 'searching_call', reduce: 'aggregation_call', has: 'membership_guard'};
              if (kinds[method]) fact(kinds[method], n, receiver, symbol(n.arguments[0]));
            }
            // Tests supply observed expectations, never verified requirements.
            if (target === 'expect' && n.arguments[0] && ts.isCallExpression(n.arguments[0])) {
              assertions.push({target: symbol(n.arguments[0].expression), line: line(n), detail: 'Static expect call; test not executed or proven authoritative.'});
            }
          }
          if (ts.isBinaryExpression(n) && n.operatorToken.kind === ts.SyntaxKind.PlusEqualsToken) fact('accumulator_update', n, symbol(n.left));
          if (ts.isReturnStatement(n) || ts.isArrowFunction(node) && n === node.body && !ts.isBlock(n)) {
            const value = ts.isReturnStatement(n) ? n.expression : n;
            const label = value && ts.isCallExpression(value) ? symbol(value.expression) : symbol(value);
            const type = collectionKind(value) || (value && ts.isCallExpression(value) ? 'call_result' : 'expression');
            returns.push({line: line(n), symbol: label, kind: type}); fact('return_value', n, label, type);
          }
          pending.push(...children(n));
        }
        for (const returned of returns) returned.kind = collections[returned.symbol] || returned.kind;
        for (const observed of facts) if (observed.kind === 'return_value') observed.related = collections[observed.subject] || observed.related;
        functions.push({name: binding.slice(0, 120), qualified_name: nestedScope.slice(0, 240), line: line(node), end_line: end(node),
          column: source.getLineAndCharacterOfPosition(node.getStart(source)).character,
          is_async: !!node.modifiers?.some(m => m.kind === ts.SyntaxKind.AsyncKeyword),
          parameters: node.parameters.slice(0, 32).map(p => ({name: p.name.getText(source).slice(0, 80), annotation: p.type?.getText(source).slice(0, 120) || null, has_default: !!p.initializer, variadic: !!p.dotDotDotToken})),
          return_annotation: node.type?.getText(source).slice(0, 120) || null,
          structure: structural.functions.find(f => f.line === line(node)) || {loops, branches},
          facts: facts.sort((a, b) => a.line - b.line), calls, returns: returns.slice(0, 16), collections, imports, assertions: assertions.slice(0, 32)});
      }
    }
    for (const child of children(node).reverse()) stack.push([child, nestedScope]);
  }
  return {functions, diagnostics, truncated};
}

if (require.main === module) {
  let input = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', chunk => {input += chunk; if (Buffer.byteLength(input) > 1000000) process.exit(2);});
  process.stdin.on('end', () => {
    try {const payload = JSON.parse(input); process.stdout.write(JSON.stringify(extract(payload.source, payload.path)));}
    catch {process.stdout.write(JSON.stringify({functions: [], diagnostics: [{kind: 'ParserError', message: 'Source could not be parsed within bounds.'}]}));}
  });
}
module.exports = {extract};
