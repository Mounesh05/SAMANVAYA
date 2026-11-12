"""Repeat the existing suite from backend/, isolating cached audit writes.

The optional probes are run separately; this command does not discover the
characterization module. Existing opt-in Mongo/Docker environment flags apply.
"""

import hashlib
from pathlib import Path

import pytest


class BaselineEnvironment:
    def pytest_configure(self):
        # Initial conftest has set test-only settings before this hook runs.
        from core import audit
        from mongomock_motor import AsyncMongoMockClient
        self.client = AsyncMongoMockClient()
        self.original_collection = audit.audit_logger.collection
        audit.audit_logger.collection = self.client.phase0_baseline.audit_logs

    def pytest_collection_modifyitems(self, items):
        # Existing 200KB source parameters otherwise exceed Windows path limits
        # in per-test temporary directories. Only reporting IDs are shortened.
        for item in items:
            if len(item.nodeid) > 180:
                digest = hashlib.sha256(item.nodeid.encode("utf-8", "surrogatepass")).hexdigest()[:12]
                item._nodeid = f"{item.nodeid[:150]}...[{digest}]"

    def pytest_unconfigure(self):
        from core import audit
        audit.audit_logger.collection = self.original_collection
        self.client.close()


if __name__ == "__main__":
    if Path.cwd().resolve() != Path(__file__).resolve().parents[2]:
        raise SystemExit("Run from the backend directory")
    raise SystemExit(pytest.main(["tests", "-q", "--tb=short", "-p", "no:cacheprovider"], plugins=[BaselineEnvironment()]))
