import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// eslint-config-next is still published in the legacy (eslintrc) format, so the
// flat config needs this compat shim. Delete it if Next ever ships a native
// flat export.
const compat = new FlatCompat({ baseDirectory: __dirname });

export default [
  { ignores: [".next/**", "node_modules/**", "out/**", "build/**"] },
  ...compat.extends("next/core-web-vitals"),
  {
    rules: {
      // This is a prototype/demo codebase and is full of legitimate escape
      // hatches (dangerouslySetInnerHTML, any-typed catch blocks, console noise
      // in seed scripts). Turning these into errors would bury the signal.
      "no-unused-vars": "off",
      "@typescript-eslint/no-unused-vars": "off",
      "no-console": "off",
      "react-hooks/exhaustive-deps": "warn",
    },
  },
];