module.exports = {
  env: {
    browser: true,
    es2021: true,
  },
  extends: ['airbnb-base', 'airbnb-typescript/base'],
  overrides: [
  ],
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    tsconfigRootDir: __dirname,
    project: './tsconfig.json',
  },
  rules: {
    'max-len': ['warn', { code: 120 }],
    'no-await-in-loop': 'off',
    // Removed 'ForOfStatement'
    'no-restricted-syntax': ['error', 'ForInStatement', 'LabeledStatement', 'WithStatement'],
    'no-console': 'off',
    'no-continue': 'off',
    'max-classes-per-file': 'off',
    'prefer-template': 'off',
    '@typescript-eslint/no-floating-promises': ['error'],
  },
};
