<!--
Thanks for contributing to AMR Sentinel! Please fill out this template so reviewers can evaluate your change quickly.
Delete sections that don't apply.
-->

## Summary

<!-- One or two sentences explaining what this PR does and why. -->

## Type of change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Refactor (no functional change)
- [ ] Build, CI, or tooling change
- [ ] Performance improvement
- [ ] Test-only change

## Related issues

<!-- Use "Closes #123" to auto-close on merge, or "Refs #123" for related-but-not-closing references. -->

## What changed

<!--
Describe the change in enough detail that a reviewer can follow without checking out the branch.
For non-trivial PRs, include before/after behavior or screenshots.
-->

## Testing

<!-- How did you verify this works? Which tests did you add or update? -->

- [ ] `pytest` passes locally
- [ ] `ruff check .` passes
- [ ] `ruff format --check .` passes
- [ ] Frontend `npm test` passes (if frontend was touched)
- [ ] `make smoke` passes (if ingestion / intelligence / agentic was touched)
- [ ] New tests added for new behavior
- [ ] Manual verification performed (describe below)

<!-- If manual verification: describe steps so a reviewer can reproduce. -->

## Documentation

- [ ] README.md updated (if user-facing behavior changed)
- [ ] `docs/ARCHITECTURE.md` updated (if architecture changed)
- [ ] `.env.example` updated (if new environment variables added)
- [ ] CHANGELOG entry added (if applicable)
- [ ] Docstrings / inline comments updated where intent is non-obvious

## Data handling

- [ ] No real patient data, credentials, or controlled-access dataset content is included in this PR
- [ ] Any new external data sources are documented and license-checked

## Reviewer notes

<!-- Anything specific you want reviewers to look at, push back on, or sanity-check. -->
