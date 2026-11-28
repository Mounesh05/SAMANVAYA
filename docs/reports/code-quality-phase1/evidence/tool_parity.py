"""CQ-49: standalone ruff/bandit (separate install) versus the isolated worker on the same Python fixtures."""
import json
import os
import subprocess
import sys
import tempfile

cases = json.load(open("/fx/analyzer_cases.json"))["cases"]
worker = json.load(open("/fx/" + sys.argv[1]))
evidence = worker.get("evidence", worker)
worker_rows = {(f["file_path"].split("/")[1], f["rule_id"].split("-", 1)[-1], f.get("line_number"))
               for f in evidence.get("static_findings", []) + evidence.get("security", {}).get("findings", [])
               if f["file_path"].endswith(".py")}

root = tempfile.mkdtemp()
for case in cases:
    if case.get("path", "").endswith(".py"):
        os.makedirs(os.path.join(root, case["id"]), exist_ok=True)
        with open(os.path.join(root, case["id"], case["path"]), "w") as handle:
            handle.write(case["source"])

ruff = json.loads(subprocess.run(["ruff", "check", "--output-format", "json", "--select", "E9,F,B", root],
                                 capture_output=True, text=True).stdout or "[]")
bandit = json.loads(subprocess.run(["bandit", "-r", root, "-f", "json", "-q"], capture_output=True, text=True).stdout or "{}")
standalone = {(os.path.relpath(r["filename"], root).split(os.sep)[0], r["code"] or "syntax", r["location"]["row"]) for r in ruff}
standalone |= {(os.path.relpath(r["filename"], root).split(os.sep)[0], r["test_id"], r["line_number"])
               for r in bandit.get("results", [])}
print("ruff", subprocess.run(["ruff", "--version"], capture_output=True, text=True).stdout.strip(),
      "| bandit", subprocess.run(["bandit", "--version"], capture_output=True, text=True).stdout.split()[1])
print("worker     ", sorted(worker_rows))
print("standalone ", sorted(standalone))
print("only worker", sorted(worker_rows - standalone))
print("only standalone", sorted(standalone - worker_rows))
