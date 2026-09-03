import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
    rules: {
      // shadcn/cva convention: components export their variant helper alongside
      // (button/badge/table). Splitting those into separate files is not the
      // convention here — the "components only" rule is off.
      'react-refresh/only-export-components': 'off',
      // The established data pattern is fetch-in-effect + reset state on prop
      // change (rail/workspace/catalog). Rewriting that to dodge a
      // stylistic rule would be a large, lower-idiom diff — off.
      'react-hooks/set-state-in-effect': 'off',
    },
  },
])
