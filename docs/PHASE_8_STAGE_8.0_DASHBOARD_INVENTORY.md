# Phase 8 Stage 8.0 dashboard inventory

Date: 28 July 2026

## Source-control state before conversion

- Nested repository branch: `main`
- Nested repository HEAD:
  `4651a050649a7cf0acd78be1dfd2eb5613e2507e`
- Recent commits:
  - `4651a05 Connect dashboard to investigation API`
  - `aeb1696 Publish packaged Phase 7 prototype`
  - `6319687 Build Phase 7 Claim Polygraph review console`
- Configured remotes: none
- Untracked source: `tests/accessibility.test.mjs`
- Nested Git metadata size: approximately 1.7 MB

## Product source retained in the root monorepo

- `.openai/hosting.json`
- `app/`
- `db/`
- `drizzle/`
- `examples/`
- `public/`
- `tests/`
- `worker/`
- configuration files, lockfile and dashboard README

## Generated or local-only paths

The dashboard `.gitignore` excludes dependencies, build products, local
Cloudflare/Sites state, outputs, work directories, environment files and
development logs. These paths are not product source:

- `node_modules/`
- `build/`
- `dist/`
- `.wrangler/`
- `.npm-cache/`
- `outputs/`
- `work/`
- `dev.out.log`
- `dev.err.log`

## Recovery

The complete former repository history is preserved and verified in
`dashboard-history/dashboard-pre-monorepo-4651a05.bundle`. No working-tree
source is deleted during the conversion.

