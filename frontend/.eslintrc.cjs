module.exports = {
  root: true,
  env: { browser: true, es2023: true, node: true },
  parser: "@typescript-eslint/parser",
  parserOptions: { ecmaVersion: 2022, sourceType: "module" },
  plugins: ["@typescript-eslint", "react", "react-hooks", "react-refresh"],
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react/recommended",
    "plugin:react/jsx-runtime",
    "plugin:react-hooks/recommended",
  ],
  settings: { react: { version: "detect" } },
  rules: {
    "react-refresh/only-export-components": "warn",
    "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
    "@typescript-eslint/consistent-type-imports": "error",
  },
  ignorePatterns: ["dist", "node_modules", "*.config.{js,cjs,mjs,ts}"],
};
