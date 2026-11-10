"""
Compare SAMANVAYA's security detection with bandit (code) and detect-secrets
(secrets).

1. Labelled code corpus (evaluation/security_corpus.py): precision, recall
   and F1 per tool, and recall per vulnerability category.
2. Labelled secrets corpus (evaluation/secrets_corpus.py): the same for
   secret detection.
3. SAMANVAYA's own backend: findings per category for both tools and which
   (file, line, category) they agree on.

Tools assign CWE ids differently for the same problem (bandit files eval()
under CWE-78 and yaml.load under CWE-20), so findings are compared by
vulnerability CATEGORY. Findings outside the categories under test (bandit's
"request without timeout", "import subprocess", "assert used" ...) are listed
separately as other findings, not counted as false alarms.

NOTE: both corpora were written for this project, alongside SAMANVAYA's rules,
so they favour the constructs SAMANVAYA targets. They show what each tool can
detect; an independent benchmark is still needed for unbiased accuracy.

Reference tools are not SAMANVAYA dependencies; install them separately:
    pip install bandit==1.9.4 detect-secrets==1.5.0
    (bandit 1.7.10, pinned in requirements.txt, crashes on Python 3.14)
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from evaluation import secrets_corpus, security_corpus  # noqa: E402
from intelligence.metrics.secrets import detect_secrets  # noqa: E402
from intelligence.metrics.security import analyze_source  # noqa: E402

try:
    from detect_secrets import SecretsCollection
    from detect_secrets.settings import default_settings
except ImportError:  # pragma: no cover
    sys.exit("detect-secrets missing: pip install bandit==1.9.4 detect-secrets==1.5.0")

DEFAULT_EXCLUDE = ("tests", "evaluation", "metrics", "venv", ".venv", "refvenv", "node_modules")

CWE_CATEGORY = {
    89: "sql injection", 78: "command injection", 95: "code injection", 502: "deserialization",
    22: "path traversal", 918: "ssrf", 1336: "template injection", 601: "open redirect",
    943: "nosql injection", 1333: "regex injection", 295: "tls verification", 327: "weak hash",
    330: "weak random", 347: "jwt verification", 377: "insecure temp file", 489: "debug mode",
    605: "bind all interfaces",
}
BANDIT_CATEGORY = {
    "B608": "sql injection", "B610": "sql injection", "B611": "sql injection",
    "B602": "command injection", "B604": "command injection", "B605": "command injection",
    "B609": "command injection",
    "B307": "code injection", "B102": "code injection",
    "B301": "deserialization", "B302": "deserialization", "B506": "deserialization", "B614": "deserialization",
    "B501": "tls verification", "B502": "tls verification", "B503": "tls verification",
    "B504": "tls verification", "B323": "tls verification",
    "B324": "weak hash", "B303": "weak hash",
    "B311": "weak random",
    "B306": "insecure temp file", "B108": "insecure temp file",
    "B201": "debug mode",
    "B104": "bind all interfaces",
    "B310": "ssrf",
    "B701": "template injection", "B702": "template injection", "B703": "template injection",
}
SEVERITY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}


# ── running the tools ─────────────────────────────────────────────

def run_bandit(paths: Sequence[Path]) -> List[dict]:
    """bandit JSON results for the given files (bandit run as a subprocess)."""
    if not paths:
        return []
    results: List[dict] = []
    for start in range(0, len(paths), 200):  # keep command lines short on Windows
        cmd = [sys.executable, "-m", "bandit", "-f", "json", "-q", *[str(p) for p in paths[start:start + 200]]]
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
        try:
            results += json.loads(out).get("results", [])
        except json.JSONDecodeError:
            raise SystemExit(f"bandit produced no JSON (is it installed for {sys.executable}?)")
    return results


def detect_secrets_scan(path: Path) -> List[Tuple[int, str]]:
    with default_settings():
        collection = SecretsCollection()
        collection.scan_file(str(path))
    return [(s["line_number"], s["type"]) for found in collection.json().values() for s in found]


def bandit_category(result: dict) -> Optional[str]:
    return BANDIT_CATEGORY.get(result.get("test_id", ""))


# ── code corpus ───────────────────────────────────────────────────

class Score:
    def __init__(self, name: str) -> None:
        self.name = name
        self.tp = self.fn = self.fp = self.tn = 0

    def add(self, vulnerable: bool, detected: bool) -> None:
        if vulnerable:
            self.tp += detected
            self.fn += not detected
        else:
            self.fp += detected
            self.tn += not detected

    @property
    def precision(self) -> float:
        return 100 * self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return 100 * self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    def row(self) -> str:
        return (f"| {self.name} | {self.tp} | {self.fn} | {self.fp} | {self.tn} "
                f"| {self.precision:.1f}% | {self.recall:.1f}% | {self.f1:.1f}% |")


SCORE_HEADER = "| Tool | TP | FN | FP | TN | Precision | Recall | F1 |\n|---|---|---|---|---|---|---|---|"


def code_corpus(work: Path) -> dict:
    files: Dict[str, Path] = {}
    for case_id, _, source in security_corpus.CASES:
        path = work / f"{case_id.replace('-', '_')}.py"
        path.write_text(source, encoding="utf-8")
        files[case_id] = path
    bandit_by_file: Dict[str, List[dict]] = {}
    for r in run_bandit(list(files.values())):
        bandit_by_file.setdefault(Path(r["filename"]).name, []).append(r)

    scores = {"ours": Score("SAMANVAYA"), "bandit": Score("bandit (all)"), "bandit_med": Score("bandit (medium+)")}
    per_category: Dict[str, Dict[str, int]] = {}
    other: Counter = Counter()
    rows: List[dict] = []
    for case_id, cwe, source in security_corpus.CASES:
        ours = {CWE_CATEGORY.get(f.cwe, f"cwe-{f.cwe}") for f in analyze_source(source, case_id).findings}
        theirs_all = bandit_by_file.get(files[case_id].name, [])
        in_scope = [r for r in theirs_all if bandit_category(r)]
        other.update(f"{r['test_id']} {r['test_name']}" for r in theirs_all if not bandit_category(r))
        theirs = {bandit_category(r) for r in in_scope}
        theirs_med = {bandit_category(r) for r in in_scope if SEVERITY_RANK.get(r["issue_severity"], 0) >= 2}
        expected = CWE_CATEGORY.get(cwe) if cwe else None
        vulnerable = expected is not None
        for key, found in (("ours", ours), ("bandit", theirs), ("bandit_med", theirs_med)):
            detected = (expected in found) if vulnerable else bool(found)
            scores[key].add(vulnerable, detected)
        if vulnerable:
            stats = per_category.setdefault(expected, {"cases": 0, "ours": 0, "bandit": 0})
            stats["cases"] += 1
            stats["ours"] += expected in ours
            stats["bandit"] += expected in theirs
        rows.append({"case": case_id, "expected": expected or "safe",
                     "samanvaya": "; ".join(sorted(ours)), "bandit": "; ".join(sorted(c for c in theirs if c))})
    return {"scores": scores, "per_category": per_category, "other": other, "rows": rows}


# ── secrets corpus ────────────────────────────────────────────────

def secrets_eval(work: Path) -> dict:
    ours, theirs = Score("SAMANVAYA"), Score("detect-secrets")
    rows = []
    for case_id, name, has_secret, content in secrets_corpus.CASES:
        folder = work / case_id
        folder.mkdir()
        path = folder / name
        path.write_text(content, encoding="utf-8")
        found_ours = detect_secrets(content, name)
        found_theirs = detect_secrets_scan(path)
        ours.add(has_secret, bool(found_ours))
        theirs.add(has_secret, bool(found_theirs))
        rows.append({"case": case_id, "secret": has_secret,
                     "samanvaya": "; ".join(sorted({f.rule for f in found_ours})),
                     "detect_secrets": "; ".join(sorted({t for _, t in found_theirs}))})
    return {"scores": [ours, theirs], "rows": rows}


# ── backend ───────────────────────────────────────────────────────

def backend_eval(root: Path, exclude: Sequence[str]) -> dict:
    files = sorted(p for p in root.rglob("*.py") if not any(part in exclude for part in p.relative_to(root).parts))
    ours: Set[Tuple[str, int, str]] = set()
    for p in files:
        rel = p.relative_to(root).as_posix()
        for f in analyze_source(p.read_text(encoding="utf-8-sig", errors="replace"), rel).findings:
            ours.add((rel, f.line, CWE_CATEGORY.get(f.cwe, f"cwe-{f.cwe}")))
    theirs: Set[Tuple[str, int, str]] = set()
    other: Counter = Counter()
    for r in run_bandit(files):
        rel = Path(r["filename"]).resolve().relative_to(root).as_posix()
        category = bandit_category(r)
        if category:
            theirs.add((rel, r["line_number"], category))
        else:
            other[f"{r['test_id']} {r['test_name']}"] += 1
    secrets_ours = sum(len(detect_secrets(p.read_text(encoding="utf-8-sig", errors="replace"), p.relative_to(root).as_posix()))
                       for p in files)
    secrets_theirs = sum(len(detect_secrets_scan(p)) for p in files)
    return {"files": len(files), "ours": ours, "theirs": theirs, "other": other,
            "secrets_ours": secrets_ours, "secrets_theirs": secrets_theirs}


# ── report ────────────────────────────────────────────────────────

def write_report(code: dict, secrets: dict, backend: Optional[dict], out: Path, bandit_version: str) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    lines = [
        "# SAMANVAYA security detection vs bandit and detect-secrets",
        "",
        f"Reference tools: {bandit_version}, detect-secrets 1.5.0. Findings are compared by vulnerability category.",
        "",
        "> Both corpora were written for this project, alongside SAMANVAYA's rules, so they favour the constructs "
        "SAMANVAYA targets. They show what each tool can detect; an independent benchmark is still needed for "
        "unbiased accuracy.",
        "",
        f"## Code vulnerabilities: labelled corpus ({len(security_corpus.CASES)} samples)",
        "",
        SCORE_HEADER,
        *[s.row() for s in code["scores"].values()],
        "",
        "Recall per category:",
        "",
        "| Category | Samples | SAMANVAYA | bandit |",
        "|---|---|---|---|",
        *[f"| {c} | {v['cases']} | {v['ours']} | {v['bandit']} |" for c, v in sorted(code["per_category"].items())],
        "",
    ]
    if code["other"]:
        lines += ["Other bandit findings on the corpus (outside the categories under test, not counted):", ""]
        lines += [f"- {name}: {n}" for name, n in code["other"].most_common()]
        lines.append("")
    lines += [
        f"## Hard-coded secrets: labelled corpus ({len(secrets_corpus.CASES)} samples)",
        "",
        SCORE_HEADER,
        *[s.row() for s in secrets["scores"]],
        "",
        "| Case | Has secret | SAMANVAYA | detect-secrets |",
        "|---|---|---|---|",
        *[f"| {r['case']} | {'yes' if r['secret'] else 'no'} | {r['samanvaya'] or '-'} | {r['detect_secrets'] or '-'} |"
          for r in secrets["rows"]],
        "",
    ]
    if backend:
        ours, theirs = backend["ours"], backend["theirs"]
        both = ours & theirs
        categories = sorted({c for _, _, c in ours | theirs})
        lines += [
            f"## SAMANVAYA backend ({backend['files']} files)",
            "",
            f"Code findings in the categories above: SAMANVAYA {len(ours)}, bandit {len(theirs)}, same file+line+category {len(both)}.",
            "",
            "| Category | SAMANVAYA | bandit | Both |",
            "|---|---|---|---|",
            *[f"| {c} | {sum(1 for x in ours if x[2] == c)} | {sum(1 for x in theirs if x[2] == c)} "
              f"| {sum(1 for x in both if x[2] == c)} |" for c in categories],
            "",
            f"Secrets in code files: SAMANVAYA {backend['secrets_ours']}, detect-secrets {backend['secrets_theirs']}.",
            "",
        ]
        if backend["other"]:
            lines += ["Other bandit findings on the backend (outside the categories under test):", ""]
            lines += [f"- {name}: {n}" for name, n in backend["other"].most_common()]
            lines.append("")
    report = out / "security_comparison.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (out / "security_corpus_results.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["case", "expected", "samanvaya", "bandit"])
        writer.writeheader()
        writer.writerows(code["rows"])
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=BACKEND)
    parser.add_argument("--out", type=Path, default=BACKEND / "evaluation" / "results")
    parser.add_argument("--exclude", nargs="*", default=list(DEFAULT_EXCLUDE))
    parser.add_argument("--skip-backend", action="store_true")
    args = parser.parse_args(argv)
    version = subprocess.run([sys.executable, "-m", "bandit", "--version"], capture_output=True, text=True).stdout
    bandit_version = " ".join(version.split()[1:3]) if version else "bandit"
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "code").mkdir()
        (work / "secrets").mkdir()
        code = code_corpus(work / "code")
        secrets = secrets_eval(work / "secrets")
    backend = None if args.skip_backend else backend_eval(args.root.resolve(), args.exclude)
    report = write_report(code, secrets, backend, args.out, bandit_version)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(report.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
