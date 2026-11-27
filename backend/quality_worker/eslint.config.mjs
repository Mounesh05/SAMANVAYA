import parser from '/opt/tools/node_modules/@typescript-eslint/parser/dist/index.js';
export default [{
  files: ['**/*.{js,jsx,ts,tsx,mjs,cjs}'],
  languageOptions: { parser, ecmaVersion: 'latest', sourceType: 'module',
    globals: { console: 'readonly', module: 'readonly', require: 'readonly', exports: 'readonly', process: 'readonly', fetch: 'readonly' } },
  rules: { 'no-undef': 'error', 'no-unused-vars': 'warn', 'no-unreachable': 'error', 'no-dupe-args': 'error' },
}];
