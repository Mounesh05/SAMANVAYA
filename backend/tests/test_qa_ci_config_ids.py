"""QA CI configuration list: every item has a stable, unique `config_id`,
including records without a branch, and listing never changes stored data."""

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture
def repository(mock_db, monkeypatch):
    from repositories import qa_repository
    monkeypatch.setattr(qa_repository, "col", lambda name: mock_db[name])
    return qa_repository.QARepository()


async def test_each_config_has_a_unique_stable_id_including_branchless_records(mock_db, repository):
    await mock_db.qa_ci_configs.insert_many([
        # Registered by the test-report import: keyed by repository, no branch.
        {"project_id": "P1", "repository": "org/app", "enabled": True, "artifact_import_source": "github_actions"},
        {"project_id": "P1", "repository": "org/app", "branch": "main", "enabled": True},
        {"project_id": "P1", "repository": "org/other", "branch": "main", "enabled": True},  # repeated branch
        {"project_id": "P2", "repository": "org/app", "branch": "main", "enabled": True},
    ])
    before = await mock_db.qa_ci_configs.find({}).to_list(None)
    first = await repository.get_all_ci_configs("P1")
    second = await repository.get_all_ci_configs("P1")
    ids = [config["config_id"] for config in first]
    assert len(ids) == 3 and len(set(ids)) == 3 and all(isinstance(i, str) and i for i in ids)
    assert ids == [config["config_id"] for config in second]  # stable between reads
    assert all("_id" not in config for config in first)  # no raw ObjectId in the response
    assert {config["config_id"] for config in first} == {str(row["_id"]) for row in before if row["project_id"] == "P1"}
    assert await mock_db.qa_ci_configs.find({}).to_list(None) == before  # nothing written


async def test_existing_readers_keep_working(mock_db, repository):
    await mock_db.qa_ci_configs.insert_many([
        {"project_id": "P1", "repository": "org/app", "enabled": True},
        {"project_id": "P1", "repository": "org/lib", "branch": "dev", "enabled": True},
    ])
    assert sorted(await repository.get_allowed_repositories("P1")) == ["org/app", "org/lib"]
    assert await repository.get_all_ci_configs("NONE") == []
