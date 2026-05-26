# Security policy

## Supported versions

AMR Sentinel is in pre-1.0 development. Only the latest release on `main` receives security updates.

| Version | Supported          |
| ------- | ------------------ |
| `main` (latest) | :white_check_mark: |
| Pre-release tags | :x: |

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues, discussions, or pull requests.**

If you believe you have found a security vulnerability in AMR Sentinel, please report it privately using one of the following channels:

1. **GitHub Security Advisories** *(preferred)*: open a private security advisory at https://github.com/Tej-Katika/amr-sentinel/security/advisories/new. GitHub will keep the report confidential between you and the maintainers until it is resolved.
2. **Email**: send a report to `tejashwarreddykatika@my.unt.edu` with the subject line `[SECURITY] AMR Sentinel — <short description>`. PGP encryption is not currently required; if you need it for sensitive disclosures, please request a key via the email above.

When reporting, please include as much of the following as you can:

- A description of the vulnerability and its potential impact.
- The component or file path where the vulnerability was found, with line numbers if possible.
- Steps to reproduce the issue, including a minimal proof-of-concept where applicable.
- The version, commit hash, or release tag you tested against.
- Any suggested remediation or mitigation, if you have one.

## Response timeline

We aim to:

- Acknowledge your report within **5 business days** of receipt.
- Provide an initial assessment of severity and a remediation plan within **15 business days**.
- Issue a fix and a coordinated disclosure within **90 days** of the initial report for vulnerabilities of high or critical severity. Lower-severity issues may be batched into a subsequent release.

If a vulnerability is being actively exploited or poses imminent risk to users, please indicate this in your report and we will prioritize accordingly.

## Disclosure policy

We follow a coordinated disclosure model:

- Vulnerabilities are fixed in a private branch and reviewed before being merged to `main`.
- A security advisory is published on GitHub once the fix has been released, crediting the reporter unless they request anonymity.
- CVE identifiers are requested for vulnerabilities of medium severity or higher.

## Scope

The following are in scope:

- Code in the `services/`, `frontend/`, `scripts/`, and `data/` directories.
- Build configuration (`Dockerfile`s, `docker-compose*.yml`, `Makefile`, GitHub Actions workflows).
- Documentation that could mislead users into insecure deployments (e.g., default credentials in production).

The following are **out of scope** for this repository:

- Vulnerabilities in upstream dependencies (Kafka, TimescaleDB, Neo4j, Redis, FastAPI, etc.) — please report those to the upstream projects.
- Issues that require physical access to a deployed system, or that depend on a compromised local machine.
- Social-engineering attacks against contributors or maintainers.
- Denial-of-service issues that require unrealistic resource volumes against a single tenant.
- Findings from automated scanners without a demonstrable exploit path.

## Safe harbor

We support responsible security research. If you make a good-faith effort to comply with this policy, we will:

- Not pursue or support legal action against you for research conducted in accordance with this policy.
- Work with you to understand and resolve the issue quickly.
- Recognize your contribution publicly (with your permission) in the security advisory and release notes.

Researchers acting in good faith under this policy are exempt from violating our `LICENSE` or `CODE_OF_CONDUCT.md` for the limited purpose of vulnerability research.

## Out-of-scope: clinical use

AMR Sentinel is research software. It is not FDA-cleared, not CE-marked, and **not approved for clinical decision-making**. Reports of issues arising from clinical deployment will be treated as documentation defects (and we will tighten the warnings), but the platform must not be used for direct patient care.
