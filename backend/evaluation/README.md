# Evaluation: SAMANVAYA metrics vs reference tools

Scripts that check SAMANVAYA's own code-quality metrics
(`backend/intelligence/metrics`) against established tools. Reports go to
`evaluation/results/`.

| Script | Compares with | Needs |
|---|---|---|
| `compare_reference_tools.py` | radon, lizard, cognitive_complexity | Python packages (separate venv) |
| `compare_duplication.py` | jscpd and/or SonarQube | a jscpd report and/or `sonar_measures.json` |
| `compare_sonarqube.py` | SonarQube (debt, rating, complexity, code smells) | `sonar_measures.json` |
| `backtest_forecast.py` | Monte Carlo sprint forecast vs average velocity (simulated teams) | nothing extra: `python evaluation\backtest_forecast.py` |
| `evaluate_risk_model.py` | PR risk model vs current rules, size baselines, LightGBM (SZZ-labelled history of real projects) | local clones; `lightgbm` + `numpy` only for `--lightgbm` (section 4) |

All commands below are for **PowerShell**, run from the `backend` folder:

```powershell
cd C:\Users\shiva\Projects\SAMANVAYA\backend
```

The same folders are excluded everywhere so every tool sees the same files:
`tests`, `evaluation`, `intelligence/metrics`, virtual environments.

---

## 1. radon, lizard, cognitive_complexity

The reference tools go in their own virtual environment **outside the repository**, so they are
neither scanned nor committed:

```powershell
python -m venv $env:USERPROFILE\samanvaya-refvenv
& $env:USERPROFILE\samanvaya-refvenv\Scripts\python -m pip install radon==6.0.1 lizard==1.17.10 cognitive_complexity==1.3.0
& $env:USERPROFILE\samanvaya-refvenv\Scripts\python evaluation\compare_reference_tools.py
```

Output: `results/reference_comparison.md`, `results/reference_disagreements.csv`.

## 2. jscpd (duplication)

Needs Node.js. `npx` downloads jscpd 4.0.5 from npm the first time.

```powershell
npx -y jscpd@4.0.5 . --format python --min-tokens 100 --min-lines 10 --reporters json --output evaluation\results\jscpd --ignore "**/tests/**,**/evaluation/**,**/metrics/**,**/venv/**,**/refvenv/**,**/node_modules/**"
python evaluation\compare_duplication.py --jscpd evaluation\results\jscpd\jscpd-report.json
```

Output: `results/duplication_comparison.md`.

## 3. SonarQube (duplication, technical debt, rating)

Needs Docker Desktop with about 4 GB of memory available.

**3.1 Start SonarQube** (first start takes 1-2 minutes):

```powershell
docker compose -f evaluation\sonarqube\docker-compose.yml up -d
```

**3.2 Sign in and create a token** (in your browser, by you):

1. Open http://localhost:9000 and sign in as `admin` / `admin`; set a new password when asked.
2. Click your avatar → **My Account** → **Security**.
3. Under **Generate Tokens**: name `samanvaya`, type **Global Analysis Token**, then **Generate**. Copy the token.

**3.3 Put the token in an environment variable** (only for this PowerShell window):

```powershell
$env:SONAR_TOKEN = "paste-your-token-here"
```

**3.4 Scan the backend:**

```powershell
docker run --rm -e SONAR_HOST_URL="http://host.docker.internal:9000" -e SONAR_TOKEN=$env:SONAR_TOKEN -v "${PWD}:/usr/src" sonarsource/sonar-scanner-cli -D"sonar.projectKey=samanvaya-backend" -D"sonar.sources=." -D"sonar.exclusions=**/tests/**,**/evaluation/**,**/metrics/**,**/venv/**,**/refvenv/**,**/node_modules/**" -D"sonar.python.version=3.12"
```

Wait until the project page at http://localhost:9000 shows results (background processing can take a minute after the scan ends).

**3.5 Download the results and compare:**

```powershell
python evaluation\sonarqube\fetch_sonar_measures.py --project samanvaya-backend
python evaluation\compare_sonarqube.py
python evaluation\compare_duplication.py --sonar evaluation\results\sonar_measures.json --jscpd evaluation\results\jscpd\jscpd-report.json
```

Output: `results/sonar_measures.json`, `results/sonarqube_comparison.md`, `results/duplication_comparison.md`.
The token is read from `SONAR_TOKEN` and is not stored in any output file.

**3.6 Stop SonarQube** when done (`down -v` also deletes its data):

```powershell
docker compose -f evaluation\sonarqube\docker-compose.yml down
```

---

## Reading the results

- **Cyclomatic / cognitive**: every disagreement is checked against documented rule differences
  between the tools (listed in the report).
- **Duplication**: compared by *which lines* are duplicated (precision, recall, F1), because each tool
  divides by a different line count. SAMANVAYA's normalized mode also finds renamed copies (type-2
  clones) that exact-match tools do not look for; some of those are false alarms on declaration-heavy
  code (for example data models with similar field lists), so their precision should be measured by
  a person labelling a sample.
- **Technical debt**: compare the *shared-rule* row (cognitive complexity > 15 and duplicated blocks,
  both tools use the same thresholds) for a like-for-like result. SonarQube's all-rule debt is
  expected to be higher because it applies hundreds of rules.

---

## 4. PR risk model (just-in-time defect prediction)

Clone the evaluation projects (any folder outside the repository), then run:

```powershell
git clone https://github.com/encode/httpx C:\jitdata\httpx
git clone https://github.com/psf/requests C:\jitdata\requests
git clone https://github.com/pallets/flask C:\jitdata\flask
python evaluation\evaluate_risk_model.py --repos C:\jitdata\httpx C:\jitdata\requests C:\jitdata\flask --cache C:\jitdata\cache
```

Labelling takes about 1 to 2 minutes per project the first time (`--cache` skips it afterwards).
Add `--lightgbm` in an environment with `pip install lightgbm numpy` for the reference model.
The committed results (`results/risk_model_evaluation.md`) were made at the HEAD commits named in
the report. Method and interpretation: `intelligence/risk_model/RISK_MODEL.md`.
