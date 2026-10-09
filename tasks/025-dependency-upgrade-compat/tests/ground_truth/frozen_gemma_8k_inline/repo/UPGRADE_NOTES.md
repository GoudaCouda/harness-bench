# Upgrade Notes: python-slugify 8.x

## 1. Dependency and Source Decision
Upgraded `python-slugify` from `6.1.2` to `^8.0.0` (declared as `>=8.0.0,<9.0.0`) in `pyproject.toml`. This aligns with the security approval (SEC-2418) restricting the dependency to the 8.x line. The implementation now relies exclusively on the installed package, removing the legacy developer fallback.

## 2. Local Verification
Performed the following verification steps:
- Executed the public test suite: `PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider`.
- Result: 3 passed, 0 failed.
- Verified specific behavior for Unicode preservation, custom separators (`-` and `_`), and underscore normalization using isolated test scripts.
- Confirmed that non-string titles and invalid separators trigger `ValueError` as requested.

## 3. Compatibility and Rollback
**Risks:** The primary risk is a change in the internal slugification logic of `python-slugify` between versions 6 and 8, which could potentially alter existing URL keys. However, the current public contract tests pass, and underscore normalization was explicitly added to the wrapper to maintain consistency.

**Rollback Plan:** If regressions are detected in production, the dependency should be pinned to a specific known-good 8.x version (e.g., `python-slugify==8.0.4`) to ensure stability while remaining within the security-approved version line. Rollback to 6.x is prohibited as that line is retired.
