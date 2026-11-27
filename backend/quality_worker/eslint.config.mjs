import parser from '/opt/tools/node_modules/@typescript-eslint/parser/dist/index.js';
// v4 DEF-V4-026: standard global sets from the pinned `globals` package (an ESLint
// dependency), so built-ins such as AbortSignal or queueMicrotask are not reported
// as undefined. Node and browser sets are combined because the worker cannot know
// a file's runtime; a browser-only global used in Node code is therefore not flagged.
import globals from '/opt/tools/node_modules/globals/index.js';
export default [
  // Repositories reference rules from plugins the worker does not load; their
  // disable directives are repository context, not findings.
  { linterOptions: { reportUnusedDisableDirectives: 'off' } },
  {
    files: ['**/*.{js,jsx,ts,tsx,mjs,cjs}'],
    languageOptions: { parser, ecmaVersion: 'latest', sourceType: 'module',
      globals: { ...globals.builtin, ...globals.node, ...globals.browser } },
    rules: { 'no-undef': 'error', 'no-unused-vars': 'warn', 'no-unreachable': 'error', 'no-dupe-args': 'error' },
  },
  // typescript-eslint guidance: the core rules misreport type names and parameters
  // in type signatures. Type checking of TypeScript belongs to tsc.
  { files: ['**/*.{ts,tsx}'], rules: { 'no-undef': 'off', 'no-unused-vars': 'off' } },
];
