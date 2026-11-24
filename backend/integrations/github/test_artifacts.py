"""Parse bounded published reports as data; never extract or execute artifacts."""
import hashlib
import io
import json
from pathlib import PurePosixPath
import xml.etree.ElementTree as ET
import zipfile

MAX_ARCHIVE_BYTES = 2_000_000
MAX_REPORT_BYTES = 1_000_000


def _coverage(data):
    value = json.loads(data)
    totals, files = value.get('totals'), value.get('files')
    if not isinstance(totals, dict) or not isinstance(files, dict) or not 1 <= len(files) <= 10000:
        raise ValueError('Coverage requires measured file summaries')
    pairs = []
    for summary in [totals, *(file.get('summary') for file in files.values() if isinstance(file, dict))]:
        if not isinstance(summary, dict):
            raise ValueError('Invalid coverage summary')
        covered, statements = summary.get('covered_lines'), summary.get('num_statements')
        if type(covered) is not int or type(statements) is not int or not 0 <= covered <= statements <= 100000000:
            raise ValueError('Invalid coverage line counts')
        pairs.append((covered, statements))
    if len(pairs) != len(files) + 1 or pairs[0][1] == 0 or tuple(map(sum, zip(*pairs[1:]))) != pairs[0]:
        raise ValueError('Coverage totals conflict with files')
    return {'coverage_status': 'reported', 'coverage_percentage': 100 * pairs[0][0] / pairs[0][1],
            'covered_lines': pairs[0][0], 'statement_lines': pairs[0][1]}


def _junit(data):
    if b'\x00' in data or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('XML declarations/entities are unsupported')
    root = ET.fromstring(data)
    if root.tag not in {'testsuite', 'testsuites'}:
        raise ValueError('Expected JUnit root')
    suites = list(root.iter('testsuite'))
    cases = list(root.iter('testcase'))
    if not suites or not 1 <= len(cases) <= 100000:
        raise ValueError('Actual test cases are required')
    failed = skipped = 0
    for case in cases:
        bad = case.find('failure') is not None or case.find('error') is not None
        skip = case.find('skipped') is not None
        if bad and skip or case.find('failure') is not None and case.find('error') is not None:
            raise ValueError('Contradictory test outcome')
        failed += bad
        skipped += skip
    # Validate leaf suite declarations without double-counting nested totals.
    leaves = [s for s in suites if s.find('testsuite') is None]
    for suite in leaves:
        actual = list(suite.iter('testcase'))
        counts = {'tests': len(actual), 'failures': sum(c.find('failure') is not None for c in actual),
                  'errors': sum(c.find('error') is not None for c in actual),
                  'skipped': sum(c.find('skipped') is not None for c in actual)}
        if any(key in suite.attrib and (not suite.attrib[key].isdigit() or int(suite.attrib[key]) != value)
               for key, value in counts.items()):
            raise ValueError('JUnit summary conflicts with actual cases')
    return {'tests_run': len(cases), 'tests_passed': len(cases) - failed - skipped,
            'tests_failed': failed, 'tests_skipped': skipped, 'status': 'failed' if failed else 'passed'}


def parse_archive(data):
    if not 0 < len(data) <= MAX_ARCHIVE_BYTES:
        raise ValueError('Artifact archive exceeds bounds')
    reports, coverage = [], None
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 32 or sum(e.file_size for e in entries) > MAX_ARCHIVE_BYTES:
                raise ValueError('Artifact expansion exceeds bounds')
            seen = set()
            for entry in entries:
                path = PurePosixPath(entry.filename)
                if (path.is_absolute() or '..' in path.parts or '\\' in entry.filename or ':' in entry.filename
                        or entry.filename in seen or entry.flag_bits & 1 or entry.file_size > MAX_REPORT_BYTES):
                    raise ValueError('Unsupported artifact member')
                seen.add(entry.filename)
                if entry.is_dir():
                    continue
                if path.suffix not in {'.xml', '.json'}:
                    continue
                content = archive.read(entry)
                digest = hashlib.sha256(content).hexdigest()
                if path.suffix == '.xml':
                    reports.append({**_junit(content), 'report_path': entry.filename, 'report_sha256': digest})
                elif path.name == 'coverage.json':
                    if coverage is not None:
                        raise ValueError('Ambiguous coverage reports')
                    coverage = {**_coverage(content), 'report_path': entry.filename, 'report_sha256': digest}
    except (zipfile.BadZipFile, ET.ParseError, KeyError, TypeError, json.JSONDecodeError, RuntimeError) as error:
        raise ValueError('Invalid published report') from error
    return reports, coverage
