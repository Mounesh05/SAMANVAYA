'use strict';
// Source-only, deliberately restricted cost model. Unknown constructs abstain.
function estimate(ts, fn, source) {
  const dims = new Map();
  const notes = [];
  const unknown = new Set();
  const one = ['1'];
  const fail = reason => { unknown.add(reason); return null; };
  const bounded = values => values.length>32 ? fail('Symbolic term limit reached') : [...new Set(values)];
  const plus = (a,b) => !a || !b ? null : bounded([...a,...b]);
  const times = (a,b) => !a || !b ? null : a.length*b.length>32 ? fail('Symbolic product limit reached') : bounded(a.flatMap(x => b.map(y => x==='1'?y:y==='1'?x:[...x.split('·'),...y.split('·')].sort((u,v)=>['n','m','p','q','r','s','t','u'].indexOf(u)-['n','m','p','q','r','s','t','u'].indexOf(v)).join('·'))));
  const exprName = n => n && ts.isIdentifier(n) ? n.text : null;
  const params = new Set(fn.parameters.map(p => exprName(p.name)).filter(Boolean));
  const locals = new Set(params);
  const indices = new Map();
  const elements = new Map();
  function size(name, kind) {
    if (!params.has(name)) return fail('Input size is not bound to a direct parameter');
    const key = name + ':' + kind;
    if (!dims.has(key)) dims.set(key, ['n','m','p','q','r','s','t','u'][dims.size]);
    return dims.get(key) ? [dims.get(key)] : fail('Input dimension limit reached');
  }
  const line = n => source.getLineAndCharacterOfPosition(n.getStart(source)).line + 1;
  const addNote = (n, text) => { if(notes.length<24) notes.push('Line '+line(n)+': '+text); };
  let count=0;
  function expression(n, depth=0) {
    if (!n) return one;
    if (++count>6000 || depth>40) return fail('Expression analysis limit reached');
    const e = x => expression(x,depth+1);
    if (ts.isStringLiteral(n)) return fail('String values require a length and allocation model');
    if (ts.isNumericLiteral(n) || [ts.SyntaxKind.TrueKeyword,ts.SyntaxKind.FalseKeyword,ts.SyntaxKind.NullKeyword].includes(n.kind)) return one;
    if (ts.isIdentifier(n)) return locals.has(n.text) ? one : fail('Unresolved value '+n.text);
    if (ts.isParenthesizedExpression(n) || ts.isAsExpression(n) || ts.isNonNullExpression(n)) return e(n.expression);
    if (ts.isPropertyAccessExpression(n) && n.name.text==='length' && params.has(exprName(n.expression))) return one;
    if (ts.isElementAccessExpression(n) && params.has(exprName(n.expression))) return e(n.argumentExpression);
    if (ts.isBinaryExpression(n)) {
      const allowed = new Set([ts.SyntaxKind.PlusToken,ts.SyntaxKind.MinusToken,ts.SyntaxKind.AsteriskToken,ts.SyntaxKind.SlashToken,ts.SyntaxKind.PercentToken,ts.SyntaxKind.LessThanToken,ts.SyntaxKind.LessThanEqualsToken,ts.SyntaxKind.GreaterThanToken,ts.SyntaxKind.GreaterThanEqualsToken,ts.SyntaxKind.EqualsEqualsEqualsToken,ts.SyntaxKind.ExclamationEqualsEqualsToken,ts.SyntaxKind.AmpersandAmpersandToken,ts.SyntaxKind.BarBarToken]);
      if (allowed.has(n.operatorToken.kind)) return plus(e(n.left),e(n.right));
      if ([ts.SyntaxKind.EqualsToken,ts.SyntaxKind.PlusEqualsToken,ts.SyntaxKind.MinusEqualsToken].includes(n.operatorToken.kind) && locals.has(exprName(n.left)) && !params.has(exprName(n.left)) && !indices.has(exprName(n.left))) return e(n.right);
    }
    if (ts.isPrefixUnaryExpression(n) && [ts.SyntaxKind.PlusToken,ts.SyntaxKind.MinusToken,ts.SyntaxKind.ExclamationToken].includes(n.operator)) return e(n.operand);
    if (ts.isConditionalExpression(n)) return plus(e(n.condition),plus(e(n.whenTrue),e(n.whenFalse)));
    return fail('Unsupported expression: '+ts.SyntaxKind[n.kind]);
  }
  function containsWrite(n, names) {
    let bad=false;
    function visit(x) {
      if(bad) return;
      if (ts.isCallExpression(x) || ts.isNewExpression(x) || ts.isFunctionLike(x) || ts.isAwaitExpression(x)) {bad=true;return;}
      if (ts.isVariableDeclaration(x) && names.has(exprName(x.name))) {bad=true;return;}
      if (ts.isBinaryExpression(x) && x.operatorToken.kind>=ts.SyntaxKind.FirstAssignment && x.operatorToken.kind<=ts.SyntaxKind.LastAssignment && names.has(exprName(x.left))) {bad=true;return;}
      if ((ts.isPrefixUnaryExpression(x)||ts.isPostfixUnaryExpression(x)) && [ts.SyntaxKind.PlusPlusToken,ts.SyntaxKind.MinusMinusToken].includes(x.operator) && names.has(exprName(x.operand))) {bad=true;return;}
      ts.forEachChild(x,visit);
    }
    visit(n); return bad;
  }
  function block(statements, depth) {
    let result=one;
    for (const st of statements) result=plus(result,statement(st,depth+1));
    return result;
  }
  function statement(n,depth=0) {
    if (++count>6000||depth>40) return fail('Statement analysis limit reached');
    const st=x=>statement(x,depth+1);
    if(ts.isBlock(n)) return block(n.statements,depth);
    if(ts.isReturnStatement(n)||ts.isExpressionStatement(n)) return expression(n.expression);
    if(ts.isBreakStatement(n)||ts.isContinueStatement(n)||ts.isEmptyStatement(n)) return one;
    if(ts.isVariableStatement(n)) {
      let cost=one;
      for(const d of n.declarationList.declarations){const name=exprName(d.name);if(!name||locals.has(name))return fail('Unsupported or shadowed binding');cost=plus(cost,expression(d.initializer));locals.add(name);}
      return cost;
    }
    if(ts.isIfStatement(n)) return plus(expression(n.expression),plus(st(n.thenStatement),n.elseStatement?st(n.elseStatement):one));
    if(ts.isForOfStatement(n) && !n.awaitModifier && ts.isVariableDeclarationList(n.initializer) && n.initializer.declarations.length===1) {
      const name=exprName(n.initializer.declarations[0].name), input=exprName(n.expression);
      if(!name||locals.has(name)||!params.has(input)||containsWrite(n.statement,new Set([name,input])))return fail('Unsupported or mutable for-of loop');
      const trips=size(input,'length');
      locals.add(name);
      elements.set(name,input);
      const body=st(n.statement);
      elements.delete(name);
      locals.delete(name);
      addNote(n,'One iteration per input element');return times(trips,body);
    }
    if(ts.isForStatement(n) && n.initializer && ts.isVariableDeclarationList(n.initializer) && n.initializer.declarations.length===1 && n.condition && ts.isBinaryExpression(n.condition)) {
      const d=n.initializer.declarations[0], name=exprName(d.name), cond=n.condition, inc=n.incrementor;
      if(!name||locals.has(name)||!d.initializer||!ts.isNumericLiteral(d.initializer)||d.initializer.text!=='0'||exprName(cond.left)!==name||cond.operatorToken.kind!==ts.SyntaxKind.LessThanToken||!inc||!(ts.isPostfixUnaryExpression(inc)||ts.isPrefixUnaryExpression(inc))||inc.operator!==ts.SyntaxKind.PlusPlusToken||exprName(inc.operand)!==name)return fail('Loop progress or termination not established');
      const bound=cond.right, input=ts.isPropertyAccessExpression(bound)&&bound.name.text==='length'?exprName(bound.expression):null;
      const boundName=exprName(bound);
      let trips;
      if (input) trips=size(input,'length');
      else if (indices.has(boundName)) trips=indices.get(boundName);
      else if (elements.has(boundName)) {
        trips=size(elements.get(boundName),'max(1, maximum nonnegative element)');
        addNote(n,'Each element bounds this loop by the maximum element magnitude, independently of collection length');
      } else if (boundName) trips=size(boundName,'numeric');
      else if (ts.isNumericLiteral(bound)) trips=one;
      if(!trips||containsWrite(n.statement,new Set([name,input,boundName].filter(Boolean))))return fail('Loop bound is unresolved or mutable');
      locals.add(name);indices.set(name,trips);const body=st(n.statement);indices.delete(name);locals.delete(name);
      addNote(n,'Zero-based unit-increment loop with stable upper bound');return times(trips,body);
    }
    return fail('Unsupported statement: '+ts.SyntaxKind[n.kind]);
  }
  if(fn.parameters.some(p=>!exprName(p.name)||p.initializer||p.dotDotDotToken)||fn.asteriskToken||fn.modifiers?.some(m=>m.kind===ts.SyntaxKind.AsyncKeyword)) fail('Unsupported signature');
  const terms=unknown.size?null:ts.isBlock(fn.body)?block(fn.body.statements,0):expression(fn.body);
  const render = t => {
    if(!t) return null;
    const tokens=t.map(x=>x==='1'?[]:x.split('·'));
    const kept=tokens.filter((x,i)=>!tokens.some((y,j)=>i!==j&&y.length>x.length&&x.every((v,k)=>x.slice(0,k+1).filter(a=>a===v).length<=y.filter(a=>a===v).length)));
    return 'O('+kept.map(x=>x.length===0?'1':x.every(v=>v===x[0])&&x.length===2?x[0]+'²':x.join('·')).join(' + ')+')';
  };
  const time=unknown.size?null:render(terms);
  const bindings=Object.fromEntries([...dims].map(([k,v])=>[v,k]));
  return {method:'static-ts-ast-cost-v1',status:time?'estimated':'unknown',time_complexity:time,space_complexity:time?'O(1)':null,dimensions:Object.keys(bindings),dimension_bindings:bindings,derivation:notes,space_derivation:time?['Only fixed-size scalar locals; no supported allocation or recursion.']:[],assumptions:['Ordinary dense arrays with fixed-size numeric or boolean scalar elements and locals, constant-cost indexed access and arithmetic; numeric bounds are nonnegative safe integers. No getters, proxies, coercion side effects or mutated input bounds. Output allocation is not supported.'],unknown_reasons:[...unknown],evidence_refs:[],limitations:['Conditional source-only upper bound; unsupported calls, allocations and control flow are unknown.']};
}
module.exports={estimate};
