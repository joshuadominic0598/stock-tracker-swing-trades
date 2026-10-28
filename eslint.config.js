import js from '@eslint/js';
import globals from 'globals';

export default [
  {
    ignores: [
      'web/vendor/**',
      'node_modules/**',
      '.tmp/**',
      'data/**',
      'playwright-report/**',
      'test-results/**',
    ],
  },
  js.configs.recommended,
  {
    files: ['web/*.js'],
    languageOptions: { globals: { ...globals.browser, LightweightCharts: 'readonly' } },
  },
  {
    files: ['*.js', 'tests/browser/*.js'],
    languageOptions: { globals: { ...globals.node, ...globals.browser } },
  },
  {
    rules: {
      'no-unused-vars': ['error', { argsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' }],
    },
  },
];
