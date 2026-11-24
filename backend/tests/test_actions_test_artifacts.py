"""Bounded, source-linked CI reports must never be inferred from workflow success."""
import io
import json
import zipfile

import pytest

from integrations.github.test_artifacts import parse_archive


def archive(name, content):
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(name, content)
    return data.getvalue()


def test_real_junit_counts_and_missing_coverage():
    rows, coverage = parse_archive(archive('pytest-results.xml', '<testsuites><testsuite tests="3" failures="1" errors="0" skipped="1"><testcase/><testcase><failure/></testcase><testcase><skipped/></testcase></testsuite></testsuites>'))
    assert rows[0]['tests_run'] == 3 and rows[0]['tests_passed'] == 1
    assert rows[0]['tests_failed'] == 1 and rows[0]['tests_skipped'] == 1
    assert coverage is None


@pytest.mark.parametrize('xml', [
    '<!DOCTYPE x [<!ENTITY x "secret">]><testsuite tests="1"><testcase/></testsuite>',
    '<testsuite tests="10"><testcase/></testsuite>',
    '<testsuite tests="1"><testcase><failure/><skipped/></testcase></testsuite>',
    '<testsuite tests="0"/>', '<invalid>',
])
def test_untrusted_or_inconsistent_reports_fail_closed(xml):
    with pytest.raises(ValueError):
        parse_archive(archive('pytest-results.xml', xml))


def test_archive_paths_and_expansion_are_bounded():
    for name, data in [('../pytest-results.xml', 'x'), ('pytest-results.xml', 'x' * 1_100_000)]:
        with pytest.raises(ValueError):
            parse_archive(archive(name, data))


def test_reported_coverage_is_derived_from_consistent_line_counts():
    document = {'totals': {'covered_lines': 3, 'num_statements': 4},
                'files': {'sample.py': {'summary': {'covered_lines': 3, 'num_statements': 4}}}}
    rows, coverage = parse_archive(archive('coverage.json', json.dumps(document)))
    assert not rows and coverage['coverage_percentage'] == 75
    assert coverage['coverage_status'] == 'reported'
    document['totals']['covered_lines'] = 5
    with pytest.raises(ValueError):
        parse_archive(archive('coverage.json', json.dumps(document)))


@pytest.mark.anyio
@pytest.mark.parametrize('location', ['https://store.blob.core.windows.net/report', 'http://127.0.0.1/private'])
async def test_storage_download_never_forwards_github_credentials(monkeypatch, location):
    import httpx
    from integrations.github.client import GitHubClient
    original = httpx.AsyncClient
    visited = []

    def handle(request):
        visited.append(request.url.host)
        if request.url.host == 'api.github.com':
            assert request.headers['authorization'] == 'Bearer synthetic-token'
            return httpx.Response(302, headers={'location': location})
        assert 'authorization' not in request.headers
        return httpx.Response(200, content=b'report')

    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    client = GitHubClient(token='synthetic-token')
    if location.startswith('https:'):
        assert await client.download_workflow_artifact('owner', 'repo', 1) == b'report'
    else:
        with pytest.raises(ValueError):
            await client.download_workflow_artifact('owner', 'repo', 1)
        assert visited == ['api.github.com']
