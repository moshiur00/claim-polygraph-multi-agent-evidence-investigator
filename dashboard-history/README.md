# Dashboard pre-monorepo history

Stage 8.0 moved the dashboard from an accidental nested Git repository into
the root monorepo.

Preserved source repository:

- branch: `main`
- HEAD: `4651a050649a7cf0acd78be1dfd2eb5613e2507e`
- remote: none
- bundle: `dashboard-pre-monorepo-4651a05.bundle`

Verify the bundle:

```powershell
git bundle verify dashboard-history/dashboard-pre-monorepo-4651a05.bundle
```

Restore it into a separate directory:

```powershell
git clone dashboard-history/dashboard-pre-monorepo-4651a05.bundle restored-dashboard
```

The accessibility test that was untracked by the nested repository remains in
`dashboard/tests/accessibility.test.mjs` and becomes root-monorepo source.

