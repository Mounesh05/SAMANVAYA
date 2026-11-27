"""Explicit read-only GitHub artifact import into existing project QA evidence."""
import hashlib
import re
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from core.database import col
from core.permissions import Permission, get_user_permissions
from core.authorization import verify_project_access
from domain.services.ai_evidence_service import _repository
from domain.services.auth_service import AuthService
from domain.services.pr_multi_agent_evidence import pr_revisions
from integrations.github.client import GitHubClient
from integrations.github.test_artifacts import MAX_ARCHIVE_BYTES, parse_archive
from repositories.project_repository import ProjectRepository
from repositories.user_repository import UserRepository


def _tenant_match(org):
    """Rows of this tenant: org_id / organization_id absent or equal (never another tenant's)."""
    return {'$and': [{'$or': [{key: {'$exists': False}}, {key: org}]} for key in ('org_id', 'organization_id')]}


def public_coverage(coverage):
    return {key: value for key, value in coverage.items() if not key.startswith('_')}


def combine_coverage(coverages):
    """One report as-is; several only when their measured files are disjoint (CI-02).

    Executable lines are summed per file, never re-estimated, so the denominator
    is exactly the union of measured statements. Overlapping files are ambiguous.
    """
    if not coverages:
        return None
    if len(coverages) == 1:
        return public_coverage(coverages[0])
    seen = set()
    for coverage in coverages:
        if seen & coverage['_paths']:
            raise HTTPException(409, 'Coverage reports overlap on the same files; map suites explicitly')
        seen |= coverage['_paths']
    covered = sum(c['covered_lines'] for c in coverages)
    statements = sum(c['statement_lines'] for c in coverages)
    return {'coverage_status': 'reported', 'coverage_percentage': 100 * covered / statements,
            'covered_lines': covered, 'statement_lines': statements, 'combined_from': len(coverages),
            'components': [{'test_suite': c['test_suite'], 'report_path': c['report_path'],
                            'covered_lines': c['covered_lines'], 'statement_lines': c['statement_lines'],
                            'artifact_id': c['artifact_provenance']['artifact_id']} for c in coverages]}


def _report_revision(pr, repository, number, run_sha):
    head, base = pr_revisions(pr, repository, number)
    if run_sha == head:
        return head, base, "pr_head"
    if (pr.get("merged") is True and pr.get("state") == "closed"
            and isinstance(run_sha, str) and re.fullmatch(r"[a-f0-9]{40}", run_sha)
            and run_sha == pr.get("merge_commit_sha")):
        return run_sha, base, "merge_commit"
    raise HTTPException(409, "Workflow must match the PR head or the confirmed merged commit")


class ActionsReportImporter:
    def __init__(self, client=None):
        self.client = client or GitHubClient()

    async def authorize(self, project_id, actor):
        account = await UserRepository().find_by_employee_id(actor.get('employee_id'))
        if not account or account.get('is_active', True) is not True:
            raise HTTPException(403, 'Current account unavailable')
        if account.get('organization_id', account.get('org_id')) != account.get('org_id'):
            raise HTTPException(403, 'Conflicting account organization')
        user = AuthService._token_payload(account)
        user['role'] = user['organizational_role']
        if Permission.MANAGE_TEST_AUTOMATION not in get_user_permissions(user['role'], False, user.get('designation')):
            raise HTTPException(403, 'QA source management permission required')
        project = await ProjectRepository().find_by_id(project_id)
        org = user.get('org_id')
        if (not isinstance(org, str) or not org or not project or project.get('org_id') != org
                or project.get('organization_id', org) != org):
            raise HTTPException(403, 'Authorized project organization required')
        await verify_project_access(user, project_id)
        owner, repo = await _repository(project_id, org)
        return org, owner, repo

    async def import_run(self, project_id, pr_number, run_id, actor):
        org, owner, repo = await self.authorize(project_id, actor)
        repository = owner + '/' + repo
        try:
            pr = await self.client.get_pull_request(owner, repo, pr_number)
            run = await self.client.get_workflow_run(owner, repo, run_id)
            head, base, revision_kind = _report_revision(pr, repository, pr_number, run.get('head_sha'))
            attempt = run.get('run_attempt')
            if (run.get('id') != run_id or run.get('head_sha') != head
                    or str(run.get('repository', {}).get('full_name', '')).casefold() != repository.casefold()
                    or type(attempt) is not int or attempt < 1 or run.get('status') != 'completed'
                    or run.get('conclusion') not in {'success', 'failure'}):
                raise HTTPException(409, 'Completed workflow must match the current exact PR revision')
            listing = await self.client.get_workflow_artifacts(owner, repo, run_id)
            artifacts = listing.get('artifacts')
            if not isinstance(artifacts, list) or listing.get('total_count') != len(artifacts) or len(artifacts) > 20:
                raise HTTPException(409, 'Complete bounded artifact listing required')
            pending = []
            coverages = []
            for item in artifacts:
                # Only explicitly named test/coverage reports; no logs or arbitrary attachments.
                name = item.get('name', '')
                if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.-]*(?:test-results|coverage)[A-Za-z0-9_.-]*', name):
                    continue
                metadata = item.get('workflow_run') or {}
                digest = item.get('digest')
                if (type(item.get('id')) is not int or item['id'] <= 0 or item.get('expired') is not False
                        or type(item.get('size_in_bytes')) is not int or not 0 < item['size_in_bytes'] <= MAX_ARCHIVE_BYTES
                        or metadata.get('id') != run_id or metadata.get('head_sha') != head
                        or not isinstance(digest, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', digest)):
                    raise HTTPException(409, 'Artifact identity, digest or availability is invalid')
                raw = await self.client.download_workflow_artifact(owner, repo, item['id'])
                if len(raw) != item['size_in_bytes'] or hashlib.sha256(raw).hexdigest() != digest[7:]:
                    raise HTTPException(409, 'Artifact integrity verification failed')
                reports, coverage = parse_archive(raw)
                provenance = {'repository': repository, 'commit_sha': head, 'revision_kind': revision_kind, 'workflow_run_id': run_id,
                    'workflow_conclusion': run['conclusion'],
                    'run_attempt': attempt, 'artifact_id': item['id'], 'artifact_sha256': digest[7:],
                    'source_reference': f'https://api.github.com/repos/{repository}/actions/artifacts/{item["id"]}',
                    'verification_scope': 'GITHUB_ARTIFACT_BYTES_AT_RUN',
                    'limitations': ['Repository-controlled published reports are not independent test execution proof']}
                for report in reports:
                    identity = f'{project_id}|{repository}|{run_id}|{attempt}|{item["id"]}|{report["report_path"]}|{report["report_sha256"]}'
                    pending.append({**report, 'id': hashlib.sha256(identity.encode()).hexdigest(),
                        'project_id': project_id, 'organization_id': org, 'repository': repository,
                        'branch': run.get('head_branch') or 'unknown', 'commit_sha': head, 'pr_number': pr_number,
                        'source': 'github_actions', 'workflow_run_id': str(run_id), 'run_attempt': attempt,
                        'workflow_name': run.get('name'), 'test_suite': name + '/' + report['report_path'],
                        'artifact_provenance': provenance, 'coverage_status': 'missing', 'coverage_percentage': None})
                if coverage:
                    coverages.append({**coverage, 'artifact_provenance': provenance, 'test_suite': name})
            if not pending:
                raise HTTPException(404, 'No published JUnit test results available for this workflow')
            # CI-02: each coverage report belongs to the artifact (suite) that published it.
            combined = combine_coverage(coverages)
            current = await self.client.get_workflow_run(owner, repo, run_id)
            latest = await self.client.get_pull_request(owner, repo, pr_number)
            if (current.get('run_attempt') != attempt or current.get('head_sha') != head
                    or current.get('status') != 'completed' or current.get('conclusion') != run['conclusion']
                    or _report_revision(latest, repository, pr_number, head) != (head, base, revision_kind)):
                raise HTTPException(409, 'Workflow attempt or PR revision changed during import')
            if await self.authorize(project_id, actor) != (org, owner, repo):
                raise HTTPException(403, 'Project scope changed')
            now = datetime.now(timezone.utc).isoformat()
            # Register only a server-validated read source; do not provision GitHub workflows/secrets.
            # CI-01: never adopt or rewrite another tenant's source registration, and keep
            # the original registrant; only the enabled flag and source are refreshed.
            source = {'project_id': project_id, 'repository': repository}
            async for existing in col('qa_ci_configs').find(source, {'_id': 0, 'org_id': 1, 'organization_id': 1}):
                if any(key in existing and existing[key] != org for key in ('org_id', 'organization_id')):
                    raise HTTPException(409, 'CI source is registered to a different organization')
            await col('qa_ci_configs').update_one({**source, **_tenant_match(org)},
                {'$set': {'enabled': True, 'artifact_import_source': 'github_actions'},
                 '$setOnInsert': {'org_id': org, 'artifact_import_registered_by': actor['employee_id']}},
                upsert=True)
            by_suite = {c['artifact_provenance']['artifact_id']: public_coverage(c) for c in coverages}
            for row in pending:
                row.update(created_at=now, received_at=now)
                own = by_suite.get(row['artifact_provenance']['artifact_id'])
                if own or len(coverages) == 1:
                    row['reported_coverage'] = own or public_coverage(coverages[0])
                # A later verified import may supply provenance missing from a
                # historical report. Keep the original observation time on retry.
                provenance = row.pop('artifact_provenance')
                # CI-01: only a receipt of this project and tenant may be refreshed. A same-id
                # row elsewhere makes the upsert hit the unique id index instead of being rewritten.
                try:
                    await col('test_runs').update_one({'id': row['id'], 'project_id': project_id, **_tenant_match(org)},
                        {'$set': {'artifact_provenance': provenance}, '$setOnInsert': row}, upsert=True)
                except DuplicateKeyError:
                    raise HTTPException(409, 'Test report receipt belongs to a different project or organization') from None
            return {'project_id': project_id, 'repository': repository, 'pr_number': pr_number, 'commit_sha': head,
                    'workflow_run_id': run_id, 'run_attempt': attempt, 'test_run_ids': [row['id'] for row in pending],
                    'coverage_status': 'reported' if coverages else 'missing',
                    'reported_coverage': combined,
                    'limitations': ['Imported counts are published CI reports, not independent correctness proof']}
        except HTTPException:
            raise
        except (httpx.HTTPError, TimeoutError):
            raise HTTPException(503, 'GitHub Actions reports are unavailable; check Actions read permission') from None
        except (ValueError, KeyError, TypeError, AttributeError):
            raise HTTPException(409, 'Published artifact/report validation failed') from None
