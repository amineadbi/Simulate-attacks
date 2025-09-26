# Frontend Agent Rules

1. Stick to React + Next.js (Pages Router) with TypeScript; keep components client-side unless they are static.
2. Prefer functional components, React hooks, and minimal local state; lift shared state into the page when multiple components need access.
3. Keep components focused: visualization (Sigma) lives in `components/GraphCanvas.tsx`, API helpers in `lib/api.ts`, and UI shells inside `pages/`.
4. Always validate JSON payload shape before wiring to the graph; never assume optional fields exist.
5. No direct DOM manipulation outside refs; avoid `document.querySelector`.
6. Use CSS modules or global utility classes in `styles/globals.css`; avoid inline style objects except for dynamic layout sizing.
7. All MCP interactions go through `lib/api.ts`; do not call `fetch` directly from components.
8. Prefer descriptive prop names and TypeScript interfaces; keep prop drilling shallow by composing feature-specific containers.
9. Guard async actions with loading/error UI; surface errors to the user with friendly text plus console debug logging.
10. Keep mock/sample data in `public/` for local dev; flag placeholder logic with TODO comments for easy follow-up.
