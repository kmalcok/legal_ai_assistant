# UI Migration Guide

This frontend now supports a staged Tailwind CSS + shadcn/ui migration.

## Stack

- Tailwind CSS v4 via `@tailwindcss/vite`
- shadcn/ui component registry via `components.json`
- `lucide-react` for icons
- `class-variance-authority`, `clsx`, `tailwind-merge` for component variants

## Path Aliases

- `@/components`
- `@/components/ui`
- `@/lib`

Configured in:

- [jsconfig.json](/Users/tolgaozkaya/DEVEL/workspace/hukuk_chat/frontend/jsconfig.json)
- [vite.config.js](/Users/tolgaozkaya/DEVEL/workspace/hukuk_chat/frontend/vite.config.js)

## Theme Source

Design tokens live in:

- [src/index.css](/Users/tolgaozkaya/DEVEL/workspace/hukuk_chat/frontend/src/index.css)

These tokens mirror the existing product direction:

- white surfaces
- restrained borders
- dark primary actions
- muted neutral copy

## Current Migration Scope

Migrated:

- [src/features/settings/pages/SettingsPage.jsx](/Users/tolgaozkaya/DEVEL/workspace/hukuk_chat/frontend/src/features/settings/pages/SettingsPage.jsx)

New shared primitives:

- [src/components/ui/button.jsx](/Users/tolgaozkaya/DEVEL/workspace/hukuk_chat/frontend/src/components/ui/button.jsx)
- [src/components/ui/card.jsx](/Users/tolgaozkaya/DEVEL/workspace/hukuk_chat/frontend/src/components/ui/card.jsx)
- [src/components/ui/input.jsx](/Users/tolgaozkaya/DEVEL/workspace/hukuk_chat/frontend/src/components/ui/input.jsx)
- [src/components/ui/textarea.jsx](/Users/tolgaozkaya/DEVEL/workspace/hukuk_chat/frontend/src/components/ui/textarea.jsx)
- [src/components/ui/badge.jsx](/Users/tolgaozkaya/DEVEL/workspace/hukuk_chat/frontend/src/components/ui/badge.jsx)
- [src/components/ui/tabs.jsx](/Users/tolgaozkaya/DEVEL/workspace/hukuk_chat/frontend/src/components/ui/tabs.jsx)
- [src/components/ui/separator.jsx](/Users/tolgaozkaya/DEVEL/workspace/hukuk_chat/frontend/src/components/ui/separator.jsx)
- [src/lib/utils.js](/Users/tolgaozkaya/DEVEL/workspace/hukuk_chat/frontend/src/lib/utils.js)

Removed from runtime:

- legacy settings stylesheet import from [src/styles/workspace.css](/Users/tolgaozkaya/DEVEL/workspace/hukuk_chat/frontend/src/styles/workspace.css)

## Migration Rules

When building new UI:

1. Use `src/components/ui/*` first.
2. Prefer Tailwind utility composition over new page-specific global CSS.
3. Keep product tokens in `src/index.css`, not per-page hardcoded palettes.
4. Add new shared primitives only when reused across screens.
5. Migrate page-by-page. Do not do global rewrites.

## Next Recommended Candidates

Best next pages to migrate:

1. `ictihat` search screen
2. auth forms
3. chat sidebar primitives

Do not migrate the whole app at once. Carry shared primitives forward and move route-by-route.
