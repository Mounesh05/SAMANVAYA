"""
Transfer repository for organizational transfer operations.
"""

from .base import BaseRepository
from core.database import col
from typing import Optional, List


class TransferRepository(BaseRepository):
    def __init__(self):
        super().__init__(col("transfers"))

    async def find_by_id(self, transfer_id: str) -> Optional[dict]:
        """Find transfer by ID."""
        return await self.find_one({"id": transfer_id})

    async def find_by_employee_id(self, employee_id: str) -> list:
        """Find all transfers for an employee."""
        return await self.find_all({"employee_id": employee_id})

    async def find_by_status(self, status: str, limit: int = 50, skip: int = 0) -> dict:
        """Find transfers by status with pagination."""
        return await self.find_many(
            {"status": status},
            limit=limit,
            skip=skip,
            sort_field="created_at",
            sort_dir=-1
        )

    async def find_by_initiated_by(self, initiated_by_id: str) -> list:
        """Find all transfers initiated by a user."""
        return await self.find_all({"initiated_by_id": initiated_by_id})

    async def find_pending_for_manager(self, manager_id: str) -> list:
        """Find transfers pending action from a specific manager."""
        # Transfers where manager needs to release or accept
        return await self.find_all({
            "$or": [
                {
                    "status": "pending_current_manager_release",
                    "current_manager_id": manager_id
                },
                {
                    "status": "pending_receiving_manager_acceptance",
                    "receiving_manager_id": manager_id
                }
            ]
        })

    async def find_pending_for_management(self) -> list:
        """Find transfers pending management approval (PM/CEO)."""
        return await self.find_all({"status": "pending_management_approval"})

    async def find_pending_for_hr(self) -> list:
        """Find transfers pending HR review or validation."""
        return await self.find_all({
            "status": {
                "$in": ["pending_hr_validation", "pending_hr_review"]
            }
        })

    async def find_active_transfers_for_employee(self, employee_id: str) -> list:
        """Find all active (non-terminal) transfers for an employee."""
        terminal_statuses = ["effective", "rejected", "cancelled"]
        return await self.find_all({
            "employee_id": employee_id,
            "status": {"$nin": terminal_statuses}
        })

    async def add_approval(
        self,
        transfer_id: str,
        approval: dict
    ) -> bool:
        """Add an approval to the transfer."""
        return await self.update_one(
            {"id": transfer_id},
            {"$push": {"approvals": approval}}
        )

    async def add_hr_flag(self, transfer_id: str, flag: str) -> bool:
        """Add an HR flag to the transfer."""
        return await self.update_one(
            {"id": transfer_id},
            {"$push": {"hr_flags": flag}}
        )

    async def update_status(
        self,
        transfer_id: str,
        new_status: str,
        updated_at: str
    ) -> bool:
        """Update transfer status."""
        return await self.update(
            {"id": transfer_id},
            {"status": new_status, "updated_at": updated_at}
        )

    async def ensure_indexes(self):
        """Create indexes for common queries."""
        await self.col.create_index("id", unique=True)
        await self.col.create_index("employee_id")
        await self.col.create_index("status")
        await self.col.create_index("created_at")
        await self.col.create_index("initiated_by_id")
        await self.col.create_index("current_manager_id")
        await self.col.create_index("receiving_manager_id")
