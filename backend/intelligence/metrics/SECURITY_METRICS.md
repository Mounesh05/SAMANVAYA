# Security metrics (Intelligence Engine)

Branch: `feature/security-metrics` (based on `feature/code-quality-metrics`). This document is for reviewers.

## What this branch adds

| Module | What it does |
|---|---|
| `security.py` | Python security rules: **13 pattern rules + taint analysis**, every finding mapped to a CWE; security rating A–E; vulnerabilities per 1,000 lines |
| `secrets.py` | Hard-coded secret detection for all languages and config files: known key formats + keyword assignments + **Shannon entropy**, with a placeholder allowlist and test-file downgrade |
| `dependencies.py` | Manifest parsers (`requirements*.txt`, `pyproject.toml`, `package-lock.json`), the **CVSS 3.1 base-score formula**, pip-audit / npm audit parsers, an optional **OSV** lookup |
| `analyzers/common/security_checks.py` | Connects the above to the evidence package and merges with bandit |

All standard library only; no network access unless the OSV lookup is switched on.

## Algorithms

### Code vulnerabilities (`security.py`)

**Taint analysis** (one function at a time): follows user input from a *source* to a *sink*.

- **Sources:** parameters of web route handlers (`@router.get`, `@app.route`, …) except those filled by
  `Depends()` / `Security()`; `request.json`, `.form`, `.args`, `.query_params`, `.headers`, `.cookies`,
  `.body()`, …; `input()`.
- **Propagation:** assignment, f-strings, `+` and `%`, `str.format` / `join`, string methods, attribute and
  item access, containers, `Path(...)`. `if`/`else` branches are merged; loop bodies are visited twice.
- **Sanitizers:** `int`, `float`, `bool`, `re.escape`, `html.escape`, `shlex.quote`, `urllib.parse.quote`,
  `uuid.UUID`, `ObjectId`, `secure_filename`, `os.path.basename`.
- **Sinks:**

  | Sink | CWE |
  |---|---|
  | SQL `execute` / `text` | 89 |
  | shell commands (`os.system`, `subprocess` with `shell=True`) | 78 |
  | `eval` / `exec` | 95 |
  | `pickle` / `yaml.load` | 502 |
  | file paths (`open`, `Path(...).read_text`, `shutil`, `FileResponse`) | 22 |
  | outgoing HTTP to a user-controlled host (SSRF) | 918 |
  | templates (`render_template_string`) | 1336 |
  | redirects | 601 |
  | MongoDB `$where` / `$regex` | 943 |
  | regex patterns | 1333 |

- A URL whose host is fixed in code (`f"https://api.github.com/repos/{owner}"`) is not treated as SSRF.

**Pattern rules** (risky whatever the input): `eval`/`exec` on runtime values, `shell=True`, pickle/marshal,
`yaml.load` without a safe loader, `verify=False`, `ssl.CERT_NONE` / unverified contexts, MD5/SHA1
(unless `usedforsecurity=False`), `random` for tokens/secrets, JWT decoded without verification,
`tempfile.mktemp`, binding to `0.0.0.0`, `debug=True`, SQL built with string formatting.

One finding per (file, line, CWE): a taint-confirmed finding replaces a pattern finding on the same line.
Each finding has a fix suggestion.

**Security rating** (SonarQube's rule): A = no vulnerabilities, B = worst is low, C = medium, D = high,
E = critical. Hard-coded secrets count as vulnerabilities, as in SonarQube.

**Limits:** one function at a time (no flow between functions or files), Python only, and unknown
function calls are assumed to return clean data (fewer false alarms; some flows can be missed).

### Secrets (`secrets.py`)

1. **Known formats:** AWS, GitHub, GitLab, Stripe, Slack, SendGrid, JWT, private-key blocks, database URLs
   with a password.
2. **Keyword assignment:** a literal value assigned to a clearly secret name (password, secret, token,
   api_key, access_key, client_secret, …), unless it is a placeholder, a reference or a sentence.
3. **High entropy:** for weaker name hints (key, auth, cookie, session, salt, …) only random-looking values:
   ≥ 4.5 bits/char (base64-style) or ≥ 3.0 (hex), ≥ 16 characters, the defaults detect-secrets uses.

- **Never flagged:** `CHANGE_ME`, `your-key-here`, `<token>`, `${VAR}`, `{{ var }}`, `xxx`, all-caps
  constant names, password hashes (`$2b$…`), paths, URLs without credentials, values with spaces.
- **Unquoted values** (`NAME=value`, `name: value`) count only in config files (`.env*`, `.ini`, `.cfg`,
  `.conf`, `.properties`, YAML, Dockerfile). In code, `password = get_password()` is not a secret.
- **Test files** are downgraded to low and marked "(test file)".
- The secret value is never stored; snippets show its first 3 characters.

### Dependencies (`dependencies.py`)

- **CVSS 3.1** base score from the FIRST specification (including its float-safe "Roundup"); severity bands
  0.1–3.9 low, 4.0–6.9 medium, 7.0–8.9 high, 9.0–10.0 critical. Verified against reference vectors
  (9.8, 10.0, 9.9, 7.8, 7.5, 6.1, 0.0).
- **OSV lookup** (`OSV_LOOKUP_ENABLED`, default `false`): sends pinned package names and versions to
  osv.dev, so it is opt-in.

## Bugs fixed on this branch

1. **Hard-coded secrets were counted twice** in the quality score. Every analyzer puts them in
   `static_findings` **and** in the security counts, and the QualityEngine added both, so one critical
   secret cost 20 points instead of 10. `CodeQualityEvidence.severity_totals()` now counts each finding once
   (plus counts that have no listed finding, which some C/C++/Java tools report). It is used by the engine
   and by `total_critical_findings` / `total_high_findings`. Scores of code with secrets go **up** slightly.
2. **pip-audit results were always lost.** `PythonAnalyzer._parse_dep_vulns` only accepted a JSON list;
   pip-audit 2.x prints an object (`{"dependencies": [...]}`), so it returned `[]` even for real
   vulnerabilities. It now parses both forms and keeps the original keys (`package`, `severity`, `cve`,
   `description`) plus `version`, `id`, `fix_versions`, `cvss_score`, `source`.
3. **Secrets scanner false alarms and misses.** The old regexes flagged placeholders (`"CHANGE_ME_PLEASE"`)
   and test fixtures at full severity, but missed real random tokens without a known prefix. The scanner
   (`analyzers/common/secrets_scanner.py`) keeps its interface and rule-id format, uses the new detector
   for all languages, and only reads files inside the repository.
4. **bandit paths.** bandit reports absolute paths; they are now repo-relative with `/`, so its findings
   can be matched with SAMANVAYA's. bandit's CWE id is now stored (`Finding.cwe`).

## Behaviour changes reviewers should check

- **New fields (optional, backward compatible):**
  - `Finding.cwe`
  - `SecurityEvidence.rating`, `vulnerability_density`, `by_cwe`, `dependency_summary`
  - `QualityEngine` result `"security"` section, present only when SAMANVAYA's security metrics ran
- **Security counts** in the Python analyzer are rebuilt from the merged findings list (bandit +
  SAMANVAYA + secrets), one per (file, line, CWE).
- **New setting** `OSV_LOOKUP_ENABLED` in `core/config.py` (default `false`).
- `security.py` contains the strings it looks for (`"0.0.0.0"`, `verify=False` examples). Exclude
  `intelligence/metrics` when scanning SAMANVAYA itself, as the evaluation scripts do.

## Results

### Labelled corpora

`evaluation/compare_security.py` → `evaluation/results/security_comparison.md`.

> Both corpora were written for this project, alongside SAMANVAYA's rules, so they favour the constructs
> SAMANVAYA targets. They show what each tool can detect; an independent benchmark is still needed for
> unbiased accuracy.

| Code vulnerabilities (52 samples) | Precision | Recall | F1 |
|---|---|---|---|
| SAMANVAYA | 100% | 100% | 100% |
| bandit 1.9.4 (all findings) | 92.0% | 69.7% | 79.3% |

- **bandit misses** the categories that need taint analysis (path traversal, SSRF, NoSQL injection, template
  injection, open redirect, regex injection), plus JWT verification and a plain `app.run(debug=True)`.
- **bandit's 2 false alarms:** any use of `random` (even `random.choice(['red', 'green'])`) and `eval` of a
  constant string.

| Secrets (27 samples) | Precision | Recall | F1 |
|---|---|---|---|
| SAMANVAYA | 100% | 100% | 100% |
| detect-secrets 1.5.0 | 72.2% | 92.9% | 81.3% |

- **detect-secrets' false alarms:** `CHANGE_ME` and `your-api-key-here` placeholders, a sentence, a commit
  SHA and an integrity hash.
- **detect-secrets missed:** a base64 token passed as `token="..."`.

### SAMANVAYA's backend

- **Code:** one low-severity finding: `start.py:98` starts uvicorn on `host="0.0.0.0"` (all interfaces).
  bandit reports the same line.
- **bandit's 3 "hard-coded password" findings are false alarms:** two empty strings in
  `create_first_user.py`, and `"pass_rate_excludes_blocked": True` in `qa_service.py` (it reads "pass" as
  "password").
- **Secrets:** none in code. The repository's test files contain test passwords and tokens, now reported as
  low "(test file)" instead of high.
- **Dependencies:** `requirements.txt` has 38 entries, 28 pinned to exact versions. No vulnerability lookup
  was run (pip-audit is not installed here and OSV is off).

### Note on bandit's version

`requirements.txt` pins `bandit==1.7.10`, which crashes on Python 3.14 (`ast.Num` was removed). It works in
the Docker image (Python 3.12). The comparison used bandit 1.9.4.

## Tests

- `test_metrics_security.py`: 117 tests (the labelled corpus, taint details, rating, secrets, manifests,
  CVSS, audit parsers, OSV with fakes)
- `test_security_integration.py`: 12 tests (single counting, secrets scanner adapter, bandit merge,
  analyzer end to end, engine, merger, pip-audit, OSV opt-in)

```bash
SECRET_KEY=test python -m pytest tests/test_metrics_security.py tests/test_security_integration.py --noconftest
```

The existing tests that can run here also pass: quality engine, risk engine, contribution credit,
evaluation validation, GitHub client, security (332 tests in total with the code-quality ones).
