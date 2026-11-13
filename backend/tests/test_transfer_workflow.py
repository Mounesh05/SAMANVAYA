"""
Tests for organizational transfer workflow.

Coverage:
- Manager-initiated transfer: full approval chain
- Employee-initiated transfer: HR validation first
- Grievance bypass: skip current manager
- HR review: can flag, cannot execute team changes
- Engineering execution: PM/CEO updates team membership
- Concurrent transfers: handle safely
- Rejected transfer: no record changes
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from services.transfer_service import TransferService
from repositories.transfer_repository import TransferRepository
from repositories.user_repository import UserRepository
from domain.models.transfer import (
    TransferCreate,
    TransferStatus,
    WorkflowType
)


@pytest.fixture
def transfer_service():
    """Transfer service instance."""
    return TransferService()


@pytest.fixture
def mock_user_repo():
    """Mock user repository."""
    with patch.object(UserRepository, 'find_by_employee_id') as mock:
        yield mock


@pytest.fixture
def mock_transfer_repo():
    """Mock transfer repository."""
    with patch.object(TransferRepository, 'insert') as mock_insert, \
         patch.object(TransferRepository, 'find_by_id') as mock_find, \
         patch.object(TransferRepository, 'find_active_transfers_for_employee') as mock_active, \
         patch.object(TransferRepository, 'add_approval') as mock_approval, \
         patch.object(TransferRepository, 'add_hr_flag') as mock_flag, \
         patch.object(TransferRepository, 'update_status') as mock_status:
        yield {
            'insert': mock_insert,
            'find_by_id': mock_find,
            'find_active': mock_active,
            'add_approval': mock_approval,
            'add_hr_flag': mock_flag,
            'update_status': mock_status
        }


@pytest.fixture
def sample_employee():
    """Sample employee."""
    return {
        "employee_id": "EMP001",
        "name": "John Developer",
        "email": "john@example.com",
        "role": "DEVELOPER",
        "dept": "Engineering",
        "team_id": "TEAM-A",
        "is_active": True
    }


@pytest.fixture
def sample_lead():
    """Sample team lead."""
    return {
        "employee_id": "LEAD001",
        "name": "Alice Lead",
        "email": "alice@example.com",
        "role": "LEAD",
        "dept": "Engineering",
        "team_id": "TEAM-A",
        "is_active": True
    }


@pytest.fixture
def sample_receiving_lead():
    """Sample receiving team lead."""
    return {
        "employee_id": "LEAD002",
        "name": "Bob Lead",
        "email": "bob@example.com",
        "role": "LEAD",
        "dept": "Engineering",
        "team_id": "TEAM-B",
        "is_active": True
    }


@pytest.fixture
def sample_pm():
    """Sample PM."""
    return {
        "employee_id": "PM001",
        "name": "Carol PM",
        "email": "carol@example.com",
        "role": "PM",
        "dept": "Engineering",
        "is_active": True
    }


@pytest.fixture
def sample_hr():
    """Sample HR user."""
    return {
        "employee_id": "HR001",
        "name": "David HR",
        "email": "david@example.com",
        "role": "HR",
        "dept": "Human Resources",
        "is_active": True
    }


@pytest.fixture
def sample_ceo():
    """Sample CEO."""
    return {
        "employee_id": "CEO001",
        "name": "Eve CEO",
        "email": "eve@example.com",
        "role": "CEO",
        "dept": "Executive",
        "is_active": True,
        "is_admin": True
    }


class TestManagerInitiatedTransfer:
    """Test manager-initiated transfer workflow."""

    @pytest.mark.asyncio
    async def test_manager_initiated_flow(
        self,
        transfer_service,
        mock_user_repo,
        mock_transfer_repo,
        sample_employee,
        sample_lead,
        sample_receiving_lead,
        sample_pm,
        sample_hr
    ):
        """Test full manager-initiated transfer approval chain."""
        # Setup mocks
        mock_user_repo.return_value = sample_employee
        mock_transfer_repo['find_active'].return_value = []
        
        with patch.object(UserRepository, 'find_by_team') as mock_find_team:
            # Mock team members for both teams
            async def find_team_side_effect(team_id):
                if team_id == "TEAM-A":
                    return [sample_lead]
                elif team_id == "TEAM-B":
                    return [sample_receiving_lead]
                return []
            
            mock_find_team.side_effect = find_team_side_effect
            
            # Step 1: Manager initiates transfer
            transfer_data = TransferCreate(
                employee_id="EMP001",
                requested_team_id="TEAM-B",
                reason="career_growth",
                justification="Employee wants to work on different tech stack"
            )
            
            created_transfer = await transfer_service.create_transfer(
                transfer_data,
                sample_lead
            )
            
            assert created_transfer.workflow_type == WorkflowType.MANAGER_INITIATED
            assert created_transfer.status == TransferStatus.PENDING_RECEIVING_MANAGER_ACCEPTANCE
            
            # Step 2: Receiving manager accepts
            mock_transfer_repo['find_by_id'].return_value = {
                "id": created_transfer.id,
                "employee_id": "EMP001",
                "employee_name": "John Developer",
                "initiated_by": "Alice Lead",
                "initiated_by_id": "LEAD001",
                "current_team_id": "TEAM-A",
                "requested_team_id": "TEAM-B",
                "current_manager_id": "LEAD001",
                "receiving_manager_id": "LEAD002",
                "reason": "career_growth",
                "justification": "Employee wants to work on different tech stack",
                "status": TransferStatus.PENDING_RECEIVING_MANAGER_ACCEPTANCE.value,
                "workflow_type": WorkflowType.MANAGER_INITIATED.value,
                "approvals": [],
                "hr_flags": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            approved_by_receiving = await transfer_service.approve_transfer(
                created_transfer.id,
                sample_receiving_lead,
                "Happy to have John on the team"
            )
            
            # Should advance to management approval
            mock_transfer_repo['update_status'].assert_called_once()
            assert mock_transfer_repo['update_status'].call_args[0][1] == TransferStatus.PENDING_MANAGEMENT_APPROVAL.value
            
            # Step 3: PM approves
            mock_transfer_repo['find_by_id'].return_value['status'] = TransferStatus.PENDING_MANAGEMENT_APPROVAL.value
            mock_transfer_repo['update_status'].reset_mock()
            
            approved_by_pm = await transfer_service.approve_transfer(
                created_transfer.id,
                sample_pm,
                "Approved for organizational efficiency"
            )
            
            # Should advance to HR review
            assert mock_transfer_repo['update_status'].call_args[0][1] == TransferStatus.PENDING_HR_REVIEW.value
            
            # Step 4: HR reviews and approves
            mock_transfer_repo['find_by_id'].return_value['status'] = TransferStatus.PENDING_HR_REVIEW.value
            mock_transfer_repo['update_status'].reset_mock()
            
            approved_by_hr = await transfer_service.approve_transfer(
                created_transfer.id,
                sample_hr,
                "Employment records verified"
            )
            
            # Should advance to approved
            assert mock_transfer_repo['update_status'].call_args[0][1] == TransferStatus.APPROVED.value


class TestEmployeeInitiatedTransfer:
    """Test employee-initiated transfer workflow."""

    @pytest.mark.asyncio
    async def test_employee_initiated_flow(
        self,
        transfer_service,
        mock_user_repo,
        mock_transfer_repo,
        sample_employee,
        sample_lead,
        sample_receiving_lead,
        sample_hr
    ):
        """Test employee-initiated transfer starts with HR validation."""
        # Setup mocks
        mock_user_repo.return_value = sample_employee
        mock_transfer_repo['find_active'].return_value = []
        
        with patch.object(UserRepository, 'find_by_team') as mock_find_team:
            async def find_team_side_effect(team_id):
                if team_id == "TEAM-A":
                    return [sample_lead]
                elif team_id == "TEAM-B":
                    return [sample_receiving_lead]
                return []
            
            mock_find_team.side_effect = find_team_side_effect
            
            # Employee initiates transfer
            transfer_data = TransferCreate(
                employee_id="EMP001",
                requested_team_id="TEAM-B",
                reason="career_growth",
                justification="I want to learn new technologies"
            )
            
            created_transfer = await transfer_service.create_transfer(
                transfer_data,
                sample_employee
            )
            
            assert created_transfer.workflow_type == WorkflowType.EMPLOYEE_INITIATED
            assert created_transfer.status == TransferStatus.PENDING_HR_VALIDATION
            
            # HR must validate first
            mock_transfer_repo['find_by_id'].return_value = {
                "id": created_transfer.id,
                "employee_id": "EMP001",
                "employee_name": "John Developer",
                "initiated_by": "John Developer",
                "initiated_by_id": "EMP001",
                "current_team_id": "TEAM-A",
                "requested_team_id": "TEAM-B",
                "current_manager_id": "LEAD001",
                "receiving_manager_id": "LEAD002",
                "reason": "career_growth",
                "justification": "I want to learn new technologies",
                "status": TransferStatus.PENDING_HR_VALIDATION.value,
                "workflow_type": WorkflowType.EMPLOYEE_INITIATED.value,
                "approvals": [],
                "hr_flags": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            validated_by_hr = await transfer_service.approve_transfer(
                created_transfer.id,
                sample_hr,
                "Request is valid"
            )
            
            # Should advance to current manager release
            assert mock_transfer_repo['update_status'].call_args[0][1] == TransferStatus.PENDING_CURRENT_MANAGER_RELEASE.value


class TestGrievanceBypass:
    """Test grievance bypass workflow."""

    @pytest.mark.asyncio
    async def test_grievance_skips_current_manager(
        self,
        transfer_service,
        mock_user_repo,
        mock_transfer_repo,
        sample_employee,
        sample_lead,
        sample_receiving_lead,
        sample_hr
    ):
        """Test grievance transfer bypasses current manager."""
        # Setup mocks
        mock_user_repo.return_value = sample_employee
        mock_transfer_repo['find_active'].return_value = []
        
        with patch.object(UserRepository, 'find_by_team') as mock_find_team:
            async def find_team_side_effect(team_id):
                if team_id == "TEAM-A":
                    return [sample_lead]
                elif team_id == "TEAM-B":
                    return [sample_receiving_lead]
                return []
            
            mock_find_team.side_effect = find_team_side_effect
            
            # Employee initiates transfer with grievance reason
            transfer_data = TransferCreate(
                employee_id="EMP001",
                requested_team_id="TEAM-B",
                reason="grievance_current_manager",
                justification="Conflict with current manager"
            )
            
            created_transfer = await transfer_service.create_transfer(
                transfer_data,
                sample_employee
            )
            
            assert created_transfer.workflow_type == WorkflowType.GRIEVANCE_BYPASS
            assert created_transfer.status == TransferStatus.PENDING_HR_VALIDATION
            
            # After HR validation, should skip current manager
            mock_transfer_repo['find_by_id'].return_value = {
                "id": created_transfer.id,
                "employee_id": "EMP001",
                "employee_name": "John Developer",
                "initiated_by": "John Developer",
                "initiated_by_id": "EMP001",
                "current_team_id": "TEAM-A",
                "requested_team_id": "TEAM-B",
                "current_manager_id": "LEAD001",
                "receiving_manager_id": "LEAD002",
                "reason": "grievance_current_manager",
                "justification": "Conflict with current manager",
                "status": TransferStatus.PENDING_HR_VALIDATION.value,
                "workflow_type": WorkflowType.GRIEVANCE_BYPASS.value,
                "approvals": [],
                "hr_flags": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            validated_by_hr = await transfer_service.approve_transfer(
                created_transfer.id,
                sample_hr,
                "Grievance validated"
            )
            
            # Should go directly to receiving manager, skipping current manager
            assert mock_transfer_repo['update_status'].call_args[0][1] == TransferStatus.PENDING_RECEIVING_MANAGER_ACCEPTANCE.value


class TestHRReviewCapabilities:
    """Test HR review capabilities and limitations."""

    @pytest.mark.asyncio
    async def test_hr_can_flag_issues(
        self,
        transfer_service,
        mock_transfer_repo,
        sample_hr
    ):
        """Test HR can flag issues during review."""
        mock_transfer_repo['find_by_id'].return_value = {
            "id": "TRF-001",
            "employee_id": "EMP001",
            "employee_name": "John Developer",
            "initiated_by": "Alice Lead",
            "initiated_by_id": "LEAD001",
            "current_team_id": "TEAM-A",
            "requested_team_id": "TEAM-B",
            "current_manager_id": "LEAD001",
            "receiving_manager_id": "LEAD002",
            "reason": "career_growth",
            "justification": "Want to change teams",
            "status": TransferStatus.PENDING_HR_REVIEW.value,
            "workflow_type": WorkflowType.MANAGER_INITIATED.value,
            "approvals": [],
            "hr_flags": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        flagged_transfer = await transfer_service.flag_transfer(
            "TRF-001",
            sample_hr,
            "pending_background_check",
            "Waiting for verification"
        )
        
        mock_transfer_repo['add_hr_flag'].assert_called_once()


class TestTransferExecution:
    """Test transfer execution by PM/CEO."""

    @pytest.mark.asyncio
    async def test_pm_cannot_execute_approved_transfer(
        self,
        transfer_service,
        mock_transfer_repo,
        sample_pm,
        sample_employee
    ):
        """Test PM cannot execute organizational transfers (only manages projects)."""
        mock_transfer_repo['find_by_id'].return_value = {
            "id": "TRF-001",
            "employee_id": "EMP001",
            "employee_name": "John Developer",
            "initiated_by": "Alice Lead",
            "initiated_by_id": "LEAD001",
            "current_team_id": "TEAM-A",
            "requested_team_id": "TEAM-B",
            "current_manager_id": "LEAD001",
            "receiving_manager_id": "LEAD002",
            "reason": "career_growth",
            "justification": "Want to change teams",
            "status": TransferStatus.APPROVED.value,
            "workflow_type": WorkflowType.MANAGER_INITIATED.value,
            "approvals": [],
            "hr_flags": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        with patch.object(UserRepository, 'find_by_employee_id') as mock_find, \
             patch.object(UserRepository, 'update') as mock_update:
            mock_find.return_value = sample_employee
            
            # PM should NOT be able to execute organizational transfers
            with pytest.raises(ValueError, match="Insufficient permissions to execute transfer"):
                await transfer_service.execute_transfer(
                    "TRF-001",
                    sample_pm
                )
            
            # No updates should have occurred
            mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_ceo_can_execute_approved_transfer(
        self,
        transfer_service,
        mock_transfer_repo,
        sample_ceo,
        sample_employee
    ):
        """Test CEO can execute approved organizational transfer."""
        mock_transfer_repo['find_by_id'].return_value = {
            "id": "TRF-001",
            "employee_id": "EMP001",
            "employee_name": "John Developer",
            "initiated_by": "Alice Lead",
            "initiated_by_id": "LEAD001",
            "current_team_id": "TEAM-A",
            "requested_team_id": "TEAM-B",
            "current_manager_id": "LEAD001",
            "receiving_manager_id": "LEAD002",
            "reason": "career_growth",
            "justification": "Want to change teams",
            "status": TransferStatus.APPROVED.value,
            "workflow_type": WorkflowType.MANAGER_INITIATED.value,
            "approvals": [],
            "hr_flags": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        with patch.object(UserRepository, 'find_by_employee_id') as mock_find, \
             patch.object(UserRepository, 'update') as mock_update:
            mock_find.return_value = sample_employee
            
            executed_transfer = await transfer_service.execute_transfer(
                "TRF-001",
                sample_ceo
            )
            
            # Should update employee's team
            mock_update.assert_called_once_with(
                {"employee_id": "EMP001"},
                {"team_id": "TEAM-B"}
            )
            
            # Should update transfer status to effective
            assert mock_transfer_repo['update_status'].call_args[0][1] == TransferStatus.EFFECTIVE.value

    @pytest.mark.asyncio
    async def test_lead_cannot_execute_transfer(
        self,
        transfer_service,
        mock_transfer_repo,
        sample_hr
    ):
        """Roles without EXECUTE_TRANSFER cannot execute.

        CR-006 Decision 1 gave HR EXECUTE_TRANSFER (with the CEO); HR execution
        is covered in tests/test_hr_access.py.
        """
        lead = {**sample_hr, "employee_id": "LEAD-9", "role": "LEAD", "designation": None}
        mock_transfer_repo['find_by_id'].return_value = {
            "id": "TRF-001",
            "employee_id": "EMP001",
            "status": TransferStatus.APPROVED.value,
            "current_team_id": "TEAM-A",
            "requested_team_id": "TEAM-B"
        }
        
        with pytest.raises(ValueError, match="Insufficient permissions to execute transfer"):
            await transfer_service.execute_transfer("TRF-001", lead)


class TestConcurrentTransfers:
    """Test concurrent transfer handling."""

    @pytest.mark.asyncio
    async def test_prevent_concurrent_transfers(
        self,
        transfer_service,
        mock_user_repo,
        mock_transfer_repo,
        sample_employee,
        sample_lead
    ):
        """Test system prevents concurrent active transfers."""
        mock_user_repo.return_value = sample_employee
        mock_transfer_repo['find_active'].return_value = [
            {
                "id": "TRF-EXISTING",
                "employee_id": "EMP001",
                "status": TransferStatus.PENDING_HR_VALIDATION.value
            }
        ]
        
        transfer_data = TransferCreate(
            employee_id="EMP001",
            requested_team_id="TEAM-B",
            reason="career_growth",
            justification="Want to change teams"
        )
        
        with pytest.raises(ValueError, match="already has an active transfer request"):
            await transfer_service.create_transfer(transfer_data, sample_lead)


class TestRejectedTransfer:
    """Test rejection handling."""

    @pytest.mark.asyncio
    async def test_rejected_transfer_no_changes(
        self,
        transfer_service,
        mock_transfer_repo,
        sample_receiving_lead,
        sample_employee
    ):
        """Test rejected transfer doesn't change records."""
        mock_transfer_repo['find_by_id'].return_value = {
            "id": "TRF-001",
            "employee_id": "EMP001",
            "employee_name": "John Developer",
            "initiated_by": "Alice Lead",
            "initiated_by_id": "LEAD001",
            "current_team_id": "TEAM-A",
            "requested_team_id": "TEAM-B",
            "current_manager_id": "LEAD001",
            "receiving_manager_id": "LEAD002",
            "reason": "career_growth",
            "justification": "Want to change teams",
            "status": TransferStatus.PENDING_RECEIVING_MANAGER_ACCEPTANCE.value,
            "workflow_type": WorkflowType.MANAGER_INITIATED.value,
            "approvals": [],
            "hr_flags": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        with patch.object(UserRepository, 'update') as mock_update:
            rejected_transfer = await transfer_service.reject_transfer(
                "TRF-001",
                sample_receiving_lead,
                "Not enough capacity on the team"
            )
            
            # Should update status to rejected
            assert mock_transfer_repo['update_status'].call_args[0][1] == TransferStatus.REJECTED.value
            
            # Should NOT update employee records
            mock_update.assert_not_called()


class TestAuthorizationChecks:
    """Test authorization at each stage."""

    @pytest.mark.asyncio
    async def test_wrong_manager_cannot_approve(
        self,
        transfer_service,
        mock_transfer_repo,
        sample_lead
    ):
        """Test that wrong manager cannot approve."""
        mock_transfer_repo['find_by_id'].return_value = {
            "id": "TRF-001",
            "employee_id": "EMP001",
            "status": TransferStatus.PENDING_RECEIVING_MANAGER_ACCEPTANCE.value,
            "workflow_type": WorkflowType.MANAGER_INITIATED.value,
            "receiving_manager_id": "LEAD002",  # Different from sample_lead
            "approvals": []
        }
        
        with pytest.raises(ValueError, match="not authorized to approve"):
            await transfer_service.approve_transfer(
                "TRF-001",
                sample_lead,  # LEAD001 trying to approve when LEAD002 is expected
                "Trying to approve"
            )

    @pytest.mark.asyncio
    async def test_developer_cannot_approve_management_stage(
        self,
        transfer_service,
        mock_transfer_repo,
        sample_employee
    ):
        """Test that developer cannot approve at management stage."""
        mock_transfer_repo['find_by_id'].return_value = {
            "id": "TRF-001",
            "employee_id": "EMP002",
            "status": TransferStatus.PENDING_MANAGEMENT_APPROVAL.value,
            "workflow_type": WorkflowType.MANAGER_INITIATED.value,
            "approvals": []
        }
        
        with pytest.raises(ValueError, match="not authorized to approve"):
            await transfer_service.approve_transfer(
                "TRF-001",
                sample_employee,
                "Trying to approve"
            )
