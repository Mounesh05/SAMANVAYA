"""
Tests for intelligence.metrics.duplication (token windows + Rabin-Karp).
"""

import random
import textwrap

import pytest

from intelligence.metrics.duplication import (
    _direct_hash,
    _rolling_hashes,
    analyze_files,
    detect_duplicates,
    tokenize_source,
)

FUNC = textwrap.dedent('''
    def process_order(order, inventory):
        total = 0
        for item in order.items:
            if item.sku not in inventory:
                raise ValueError("missing sku")
            stock = inventory[item.sku]
            if stock.quantity < item.quantity:
                raise ValueError("insufficient stock")
            stock.quantity -= item.quantity
            total += item.price * item.quantity
        order.total = total
        return total
''')

RENAMED = textwrap.dedent('''
    def handle(o, stock_map):
        s = 0.0
        for line in o.items:
            if line.sku not in stock_map:
                raise KeyError("no sku")
            entry = stock_map[line.sku]
            if entry.quantity < line.quantity:
                raise KeyError("short")
            entry.quantity -= line.quantity
            s += line.price * line.quantity
        o.total = s
        return s
''')

UNRELATED = textwrap.dedent('''
    class Greeter:
        def __init__(self, name):
            self.name = name

        def greet(self, loud=False):
            text = f"Hello, {self.name}"
            return text.upper() if loud else text
''')

SMALL = dict(min_tokens=30, min_lines=5)


# ── tokens and hashing ────────────────────────────────────────────

def test_tokenizer_drops_comments_layout_and_imports_and_normalizes():
    tokens = tokenize_source("import os\nfrom x import y\n\nx = 1  # note\nname = 'a'\n")
    assert [t.value for t in tokens] == ["ID", "=", "NUM", "ID", "=", "STR"]
    assert [t.start_line for t in tokens] == [4, 4, 4, 5, 5, 5]


def test_tokenizer_exact_mode_keeps_names_and_literals():
    tokens = tokenize_source("x = 1\n", normalize=False)
    assert [t.value for t in tokens] == ["x", "=", "1"]


def test_rolling_hash_matches_direct_hash_for_every_window():
    rng = random.Random(7)
    seq = [rng.randint(1, 50) for _ in range(300)]
    window = 25
    for pos, h in _rolling_hashes(seq, window):
        assert h == _direct_hash(seq[pos:pos + window])
    assert len(list(_rolling_hashes(seq, window))) == len(seq) - window + 1
    assert list(_rolling_hashes(seq[:10], window)) == []


# ── clone detection ───────────────────────────────────────────────

def test_exact_copy_in_two_files():
    report = detect_duplicates({"a.py": FUNC, "b.py": FUNC}, **SMALL)
    assert len(report.clones) == 1
    clone = report.clones[0]
    assert (clone.original.path, clone.copy.path) == ("a.py", "b.py")
    assert (clone.original.start_line, clone.original.end_line) == (2, 13)
    assert report.density == 100.0
    assert all(f.density == 100.0 for f in report.files)


def test_renamed_copy_found_only_when_normalizing():
    sources = {"a.py": FUNC, "b.py": RENAMED}
    assert len(detect_duplicates(sources, **SMALL).clones) == 1
    assert detect_duplicates(sources, normalize=False, **SMALL).clones == []


def test_comments_and_blank_lines_do_not_hide_a_copy():
    noisy = FUNC.replace("        stock = inventory", "\n        # look up stock\n\n        stock = inventory")
    report = detect_duplicates({"a.py": FUNC, "b.py": noisy}, **SMALL)
    assert len(report.clones) == 1
    clone = report.clones[0]
    assert clone.copy.lines == clone.original.lines + 3
    # comment and blank lines are not code lines, so both files are 100% duplicated
    assert report.density == 100.0


def test_shared_imports_are_not_duplication():
    imports = "".join(f"from package.module{i} import name{i}\n" for i in range(30))
    report = detect_duplicates({"a.py": imports, "b.py": imports}, **SMALL)
    assert report.clones == []
    # import lines are code lines (NCLOC) but never count as duplicated
    assert report.code_lines == 60 and report.density == 0.0


def test_docstrings_are_not_code_lines():
    documented = '"""Module\ndocstring."""\n' + FUNC
    report = detect_duplicates({"a.py": documented, "b.py": FUNC}, **SMALL)
    assert {f.path: f.code_lines for f in report.files} == {"a.py": 12, "b.py": 12}
    assert report.density == 100.0
    docstring_only = detect_duplicates({"pkg/__init__.py": '"""Package docs."""\n'}, **SMALL)
    assert docstring_only.files[0].code_lines == 0


def test_unrelated_code_has_no_clones():
    report = detect_duplicates({"a.py": FUNC, "b.py": UNRELATED}, **SMALL)
    assert report.clones == []
    assert report.density == 0.0


def test_snippet_below_token_threshold_is_ignored():
    snippet = "def f(a):\n    return a + 1\n"
    assert detect_duplicates({"a.py": snippet, "b.py": snippet}, **SMALL).clones == []


def test_min_lines_filters_clones_squeezed_onto_few_lines():
    one_liner = "; ".join(f"v{i} = w{i} + {i}" for i in range(20)) + "\n"
    sources = {"a.py": one_liner, "b.py": one_liner}
    exact = dict(min_tokens=30, normalize=False)  # exact names: no self-repetition
    assert len(detect_duplicates(sources, min_lines=1, **exact).clones) == 1
    assert detect_duplicates(sources, min_lines=5, **exact).clones == []


def test_repetitive_code_is_reported_once_not_at_every_offset():
    # 20 lines of the same shape match themselves at many offsets once normalized
    repetitive = "".join(f"value_{i} = base_{i} + {i}\n" for i in range(20))
    report = detect_duplicates({"a.py": repetitive, "b.py": repetitive}, min_tokens=30, min_lines=5)
    assert 1 <= len(report.clones) <= 4  # was 25 overlapping matches before de-overlapping
    for path in ("a.py", "b.py"):
        copies = sorted((c.copy.start_line, c.copy.end_line) for c in report.clones if c.copy.path == path)
        assert all(prev_end < start for (_, prev_end), (start, _) in zip(copies, copies[1:]))
    assert report.density == 100.0


def test_copy_inside_the_same_file():
    second = FUNC.replace("process_order", "process_refund")
    report = detect_duplicates({"a.py": FUNC + second}, **SMALL)
    assert len(report.clones) == 1
    clone = report.clones[0]
    assert clone.original.path == clone.copy.path == "a.py"
    assert clone.original.end_line < clone.copy.start_line  # no overlap
    assert report.density == 100.0


def test_three_copies_cover_every_file():
    report = detect_duplicates({"a.py": FUNC, "b.py": FUNC, "c.py": RENAMED}, **SMALL)
    assert len(report.clones) == 2
    assert {c.copy.path for c in report.clones} == {"b.py", "c.py"}
    assert all(f.density == 100.0 for f in report.files)


def test_partial_duplication_density():
    mixed = FUNC + UNRELATED
    report = detect_duplicates({"a.py": FUNC, "b.py": mixed}, **SMALL)
    b = next(f for f in report.files if f.path == "b.py")
    assert 0 < b.density < 100
    assert b.duplicated_lines == 12
    assert len(report.clones) == 1


def test_report_is_deterministic_regardless_of_input_order():
    one = detect_duplicates({"a.py": FUNC, "b.py": RENAMED, "c.py": UNRELATED}, **SMALL)
    two = detect_duplicates({"c.py": UNRELATED, "b.py": RENAMED, "a.py": FUNC}, **SMALL)
    assert one.to_dict() == two.to_dict()


# ── errors, files, output ─────────────────────────────────────────

def test_untokenizable_file_is_reported_and_others_still_analyzed():
    report = detect_duplicates({"a.py": FUNC, "b.py": FUNC, "bad.py": 's = """never closed\n'}, **SMALL)
    assert "bad.py" in report.parse_errors
    assert len(report.clones) == 1


@pytest.mark.parametrize("kwargs", [{"min_tokens": 1}, {"min_lines": 0}])
def test_invalid_thresholds_rejected(kwargs):
    with pytest.raises(ValueError):
        detect_duplicates({"a.py": FUNC}, **kwargs)


def test_analyze_files_reads_disk_with_relative_paths(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text(FUNC, encoding="utf-8")
    (tmp_path / "pkg" / "b.py").write_bytes(b"\xef\xbb\xbf" + FUNC.encode("utf-8"))
    report = analyze_files(sorted((tmp_path / "pkg").glob("*.py")) + [tmp_path / "missing.py"], root=tmp_path, **SMALL)
    assert len(report.clones) == 1
    assert report.clones[0].original.path.replace("\\", "/") == "pkg/a.py"
    assert "missing.py" in report.parse_errors


def test_to_dict_shape():
    data = detect_duplicates({"a.py": FUNC, "b.py": FUNC}, **SMALL).to_dict()
    assert data["clone_count"] == 1
    assert data["density"] == 100.0
    assert set(data["clones"][0]) == {"original", "copy", "tokens", "lines"}
    assert data["files"][0]["code_lines"] == 12
