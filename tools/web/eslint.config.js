import js from '@eslint/js';
import globals from 'globals';

export default [
  {
    ignores: [
      'src/swing_signal/web/vendor/**',
      '**/node_modules/**',
      '.tmp/**',
      'data/**',
      'playwright-report/**',
      'test-results/**',
    ],
  },
  js.configs.recommended,
  {
    files: ['src/swing_signal/web/*.js'],
    languageOptions: { globals: { ...globals.browser, LightweightCharts: 'readonly' } },
  },
  {
    files: ['tools/web/**/*.js'],
    languageOptions: { globals: { ...globals.node, ...globals.browser } },
  },
  {
    rules: {
      'no-unused-vars': ['error', { argsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' }],
    },
  },
];
