"""v4 live E2E (DEF-V4-026): ESLint context diagnostics are not developer defects.

A real whole-repository run on sindresorhus/p-limit@a8a6fbe returned 33 findings,
all caused by the worker's ESLint setup rather than the code: inline directives
for plugins the worker does not load ("Definition for rule ... was not found",
scored HIGH), unused-directive notices, standard Node globals missing from the
config, and core no-unused-vars applied to TypeScript type signatures.
"""

import json
import re
from pathlib import Path

from intelligence.analyzers.isolated import IMAGE
from intelligence.analyzers.javascript.analyzer import JavaScriptAnalyzer

WORKER = Path(__file__).resolve().parents[1] / "quality_worker"


def eslint_output(*messages, file_path="/src/index.js"):
    return json.dumps([{"filePath": file_path, "messages": list(messages)}])


def test_unknown_inline_rule_and_unused_directive_are_not_findings():
    output = eslint_output(
        {"ruleId": "promise/param-names", "severity": 2, "line": 55,
         "message": "Definition for rule 'promise/param-names' was not found."},
        {"ruleId": None, "severity": 1, "line": 99,
         "message": "Unused eslint-disable directive (no problems were reported from 'no-unmodified-loop-condition')."},
        {"ruleId": "no-undef", "severity": 2, "line": 3, "message": "'undefinedThing' is not defined."},
    )
    findings = JavaScriptAnalyzer._parse_eslint(output, ["index.js"], "/src")
    assert [(f.rule_id, f.line_number) for f in findings] == [("ESLINT-no-undef", 3)]


def test_fatal_parse_error_is_a_syntax_finding_not_eslint_none():
    output = eslint_output({"ruleId": None, "fatal": True, "severity": 2, "line": 7,
                            "message": "Parsing error: Unexpected token )"})
    (finding,) = JavaScriptAnalyzer._parse_eslint(output, ["index.js"], "/src")
    assert finding.rule_id == "ESLINT-SYNTAX-ERROR"
    assert finding.category == "syntax"
    assert finding.severity.value.lower() == "critical"
    assert finding.line_number == 7


def test_worker_config_declares_standard_globals_and_typescript_overrides():
    config = (WORKER / "eslint.config.mjs").read_text()
    # Standard global sets from the pinned `globals` package (an ESLint dependency).
    assert "node_modules/globals" in config
    for name in ("builtin", "node", "browser"):
        assert f"globals.{name}" in config
    assert re.search(r"reportUnusedDisableDirectives:\s*'off'", config)
    # typescript-eslint guidance: core no-undef / no-unused-vars misreport TS types.
    ts_block = config[config.index("files: ['**/*.{ts,tsx}']"):]
    assert "'no-undef': 'off'" in ts_block and "'no-unused-vars': 'off'" in ts_block


def test_changed_worker_config_ships_under_a_new_image_tag():
    # Changing the worker image contents requires a new tag (worker_broker/README.md).
    assert IMAGE == "samanvaya-quality:3"
