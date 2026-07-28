# ADR 0015: Track the dashboard in the root monorepo

Date: 28 July 2026

Status: Accepted

## Context

The Phase 7 dashboard was created as a nested Git repository under
`dashboard/`. The root repository therefore displayed only the directory
rather than its files, and backend/dashboard changes could not form one atomic
commit or release.

The nested repository has:

- branch: `main`;
- preserved commit: `4651a050649a7cf0acd78be1dfd2eb5613e2507e`;
- three local commits;
- no configured remote; and
- one untracked accessibility test, which remains in the working tree.

## Decision

Track `dashboard/` directly in the root repository as a monorepo directory.
Before removing the nested `.git` directory:

1. create a complete Git bundle containing every nested reference;
2. verify the bundle;
3. record the branch, commit, status and tracked-file inventory; and
4. leave all dashboard working-tree files in place.

The recovery bundle is stored at
`dashboard-history/dashboard-pre-monorepo-4651a05.bundle`. The accompanying
inventory documents how to restore the former repository.

## Consequences

- Root source control can see dashboard files and backend/dashboard changes can
  be released atomically.
- Dashboard-local generated files remain governed by `dashboard/.gitignore`.
- The historical nested repository can be reconstructed from the bundle.
- Dashboard commands continue to run from `dashboard/`; only repository
  ownership changes.
- Future tooling must not recreate `dashboard/.git`.

