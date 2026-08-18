# Frontend

React + TypeScript + Tailwind CSS v4 + shadcn/ui, built with Vite.

## Run

```bash
npm install
npm run dev      # dev server; /api is proxied to http://127.0.0.1:8000
npm run build    # type-check (tsc -b) + production build
npm run lint
```

## Notes

- Path alias `@/` → `src/` (see `tsconfig.app.json`).
- UI primitives live in `src/components/ui/` (shadcn, managed via
  `components.json`).
- The V5 baseline renders a placeholder shell in `src/App.tsx`; the two-panel
  chat + workspace layout from the spec lands here in the next phase.
