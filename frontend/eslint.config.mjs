import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Огноо, тоог locale-оор форматлахыг зөвхөн lib/format.ts-д: сервер (Node), хөтөч өөрөөр форматалж
  // hydration алдаа ("X/06 12:00" vs "10/06, 12:00 PM") гаргадаг.
  {
    files: ["app/**/*.{ts,tsx}", "components/**/*.{ts,tsx}", "lib/**/*.{ts,tsx}"],
    ignores: ["lib/format.ts"],
    rules: {
      "no-restricted-properties": ["error",
        ...["toLocaleString", "toLocaleDateString", "toLocaleTimeString"].map((property) => ({
          property, message: "Hydration алдаа гаргана. lib/format.ts-ийн formatDateTime() (эсвэл шинэ функц) ашиглана уу.",
        })),
        ...["DateTimeFormat", "NumberFormat", "RelativeTimeFormat"].map((property) => ({
          object: "Intl", property, message: "Форматлахыг lib/format.ts-д нэг газар (locale-оос хамааралгүй) хийнэ.",
        })),
      ],
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
