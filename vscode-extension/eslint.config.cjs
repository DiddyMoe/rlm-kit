// @ts-check
const eslint = require("@eslint/js");
const tseslint = require("typescript-eslint");

module.exports = tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.strictTypeChecked,
  {
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: __dirname,
      },
    },
    rules: {
      // Enforce no floating promises (common VS Code extension bug)
      "@typescript-eslint/no-floating-promises": "error",

      // No implicit any — strict is already on in tsconfig, but double-enforce
      "@typescript-eslint/no-explicit-any": "error",

      // Complexity cap
      "complexity": ["warn", { max: 15 }],

      // No unsafe patterns
      "@typescript-eslint/no-unsafe-assignment": "error",
      "@typescript-eslint/no-unsafe-call": "error",
      "@typescript-eslint/no-unsafe-member-access": "error",
      "@typescript-eslint/no-unsafe-return": "error",

      // Allow unused variables prefixed with _
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],

      // Relax some strict rules that create noise without value
      "@typescript-eslint/restrict-template-expressions": [
        "error",
        { allowNumber: true, allowBoolean: true },
      ],
      "@typescript-eslint/no-confusing-void-expression": "off",
      "@typescript-eslint/no-unnecessary-condition": "warn",
    },
  },
  {
    // Test files get slightly relaxed rules
    files: ["src/**/*.test.ts"],
    rules: {
      "@typescript-eslint/no-unsafe-assignment": "off",
      "@typescript-eslint/no-unsafe-member-access": "off",
    },
  },
  {
    ignores: ["out/**", "node_modules/**", "eslint.config.cjs"],
  },
);
