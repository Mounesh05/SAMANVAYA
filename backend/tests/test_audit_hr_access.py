"""
Test audit log access with HR role-based filtering.

Verifies that HR users see only HR-relevant audit events,
not engineering/security/system events.
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException

from api.routes.audit import HR_AUDIT_ACTIONS, RESTRICTED_AUDIT_ACTIONS
from core.audit import AuditAction


class TestAuditHRFiltering:
    """Test audit log filtering for HR users."""
    
    @pytest.mark.asyncio
    async def test_hr_sees_only_hr_relevant_actions(self):
        """HR users should see only employee/team lifecycle events."""
        from api.routes.audit import get_audit_logs
        
        # Mock current user as HR
        hr_user = {
            'employee_id': 'HR001',
            'role': 'HR',
            'is_admin': False,
            'designation': 'HR_MANAGER'
        }
        
        # Mock audit logs with mixed events
        mock_logs = [
            {'action': AuditAction.USER_CREATED.value, 'actor_id': 'ADMIN01', 'timestamp': '2024-01-01'},
            {'action': AuditAction.SETTINGS_CHANGED.value, 'actor_id': 'ADMIN01', 'timestamp': '2024-01-02'},
            {'action': AuditAction.TEAM_MEMBER_ADDED.value, 'actor_id': 'LEAD01', 'timestamp': '2024-01-03'},
            {'action': AuditAction.ADMIN_GRANTED.value, 'actor_id': 'CEO01', 'timestamp': '2024-01-04'},
            {'action': AuditAction.USER_UPDATED.value, 'actor_id': 'HR001', 'timestamp': '2024-01-05'},
        ]
        
        with patch('api.routes.audit.audit_logger') as mock_logger:
            mock_logger.get_logs = AsyncMock(return_value=mock_logs)
            
            result = await get_audit_logs(
                actor_id=None,
                resource_type=None,
                resource_id=None,
                action=None,
                start_date=None,
                end_date=None,
                limit=100,
                current_user=hr_user
            )
        
        # HR should see only 3 HR-relevant events
        assert result['total'] == 3
        assert result['filtered_for_role'] == 'HR'
        
        # Verify only HR-allowed actions present
        returned_actions = [log['action'] for log in result['logs']]
        assert AuditAction.USER_CREATED.value in returned_actions
        assert AuditAction.TEAM_MEMBER_ADDED.value in returned_actions
        assert AuditAction.USER_UPDATED.value in returned_actions
        
        # Verify restricted actions are NOT present
        assert AuditAction.SETTINGS_CHANGED.value not in returned_actions
        assert AuditAction.ADMIN_GRANTED.value not in returned_actions
    
    @pytest.mark.asyncio
    async def test_hr_cannot_see_engineering_events(self):
        """HR should not see AI evaluation or technical audit events."""
        from api.routes.audit import get_audit_logs
        
        hr_user = {
            'employee_id': 'HR002',
            'role': 'HR',
            'is_admin': False,
            'designation': 'HR_MANAGER'
        }
        
        # Mock logs with restricted events
        mock_logs = [
            {'action': AuditAction.EVALUATION_TRIGGERED.value, 'actor_id': 'LEAD01'},
            {'action': AuditAction.BULK_EVALUATION_TRIGGERED.value, 'actor_id': 'CEO01'},
            {'action': AuditAction.INTEGRATION_ADDED.value, 'actor_id': 'ADMIN01'},
            {'action': AuditAction.SENSITIVE_DATA_ACCESSED.value, 'actor_id': 'CEO01'},
        ]
        
        with patch('api.routes.audit.audit_logger') as mock_logger:
            mock_logger.get_logs = AsyncMock(return_value=mock_logs)
            
            result = await get_audit_logs(
                actor_id=None,
                resource_type=None,
                resource_id=None,
                action=None,
                start_date=None,
                end_date=None,
                limit=100,
                current_user=hr_user
            )
        
        # HR should see ZERO events (all are restricted)
        assert result['total'] == 0
        assert len(result['logs']) == 0
    
    @pytest.mark.asyncio
    async def test_ceo_sees_all_audit_events(self):
        """Non-HR users with VIEW_AUDIT_LOGS see all events."""
        from api.routes.audit import get_audit_logs
        
        ceo_user = {
            'employee_id': 'CEO01',
            'role': 'CEO',
            'is_admin': True,
            'designation': None
        }
        
        mock_logs = [
            {'action': AuditAction.USER_CREATED.value},
            {'action': AuditAction.SETTINGS_CHANGED.value},
            {'action': AuditAction.ADMIN_GRANTED.value},
            {'action': AuditAction.EVALUATION_TRIGGERED.value},
        ]
        
        with patch('api.routes.audit.audit_logger') as mock_logger:
            mock_logger.get_logs = AsyncMock(return_value=mock_logs)
            
            result = await get_audit_logs(
                actor_id=None,
                resource_type=None,
                resource_id=None,
                action=None,
                start_date=None,
                end_date=None,
                limit=100,
                current_user=ceo_user
            )
        
        # CEO sees all 4 events (no filtering)
        assert result['total'] == 4
        assert len(result['logs']) == 4
        assert result['filtered_for_role'] == 'CEO'
    
    @pytest.mark.asyncio
    async def test_hr_user_activity_filtered(self):
        """HR user activity summary should be filtered."""
        from api.routes.audit import get_user_activity_summary
        
        hr_user = {
            'employee_id': 'HR003',
            'role': 'HR',
            'is_admin': False,
            'designation': 'HR_OPERATIONS'
        }
        
        mock_activity = {
            'actor_id': 'DEV01',
            'period_days': 30,
            'total_actions': 10,
            'action_counts': {
                AuditAction.USER_CREATED.value: 2,
                AuditAction.SETTINGS_CHANGED.value: 3,
                AuditAction.TEAM_MEMBER_ADDED.value: 5,
            },
            'recent_actions': [
                {'action': AuditAction.USER_CREATED.value},
                {'action': AuditAction.SETTINGS_CHANGED.value},
            ]
        }
        
        with patch('api.routes.audit.audit_logger') as mock_logger:
            mock_logger.get_user_activity = AsyncMock(return_value=mock_activity)
            
            result = await get_user_activity_summary(
                user_id='DEV01',
                days=30,
                current_user=hr_user
            )
        
        # HR should see only HR-relevant action counts
        assert AuditAction.USER_CREATED.value in result['action_counts']
        assert AuditAction.TEAM_MEMBER_ADDED.value in result['action_counts']
        assert AuditAction.SETTINGS_CHANGED.value not in result['action_counts']
        
        # Total should be recalculated for filtered actions only
        assert result['total_actions'] == 7  # 2 + 5, not 10
        assert result['filtered_for_role'] == 'HR'
    
    @pytest.mark.asyncio
    async def test_hr_without_permission_denied(self):
        """HR users without VIEW_AUDIT_LOGS permission should be denied."""
        from api.routes.audit import get_audit_logs
        
        # HR user without proper designation (no VIEW_AUDIT_LOGS)
        hr_user = {
            'employee_id': 'HR004',
            'role': 'HR',
            'is_admin': False,
            'designation': 'RECRUITER'  # Recruiter does not have VIEW_AUDIT_LOGS
        }
        
        with pytest.raises(HTTPException) as exc_info:
            await get_audit_logs(
                actor_id=None,
                resource_type=None,
                resource_id=None,
                action=None,
                start_date=None,
                end_date=None,
                limit=100,
                current_user=hr_user
            )
        
        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in exc_info.value.detail
    
    def test_hr_audit_actions_whitelist_correctness(self):
        """Verify HR_AUDIT_ACTIONS contains only appropriate events."""
        # HR should see employee and team lifecycle events
        assert AuditAction.USER_CREATED in HR_AUDIT_ACTIONS
        assert AuditAction.USER_UPDATED in HR_AUDIT_ACTIONS
        assert AuditAction.TEAM_MEMBER_ADDED in HR_AUDIT_ACTIONS
        
        # HR should NOT see system/security events
        assert AuditAction.ADMIN_GRANTED not in HR_AUDIT_ACTIONS
        assert AuditAction.SETTINGS_CHANGED not in HR_AUDIT_ACTIONS
        assert AuditAction.INTEGRATION_ADDED not in HR_AUDIT_ACTIONS
    
    def test_restricted_audit_actions_completeness(self):
        """Verify RESTRICTED_AUDIT_ACTIONS covers sensitive events."""
        # Restricted actions should include security-sensitive events
        assert AuditAction.ADMIN_GRANTED in RESTRICTED_AUDIT_ACTIONS
        assert AuditAction.ADMIN_REVOKED in RESTRICTED_AUDIT_ACTIONS
        assert AuditAction.SETTINGS_CHANGED in RESTRICTED_AUDIT_ACTIONS
        assert AuditAction.EVALUATION_TRIGGERED in RESTRICTED_AUDIT_ACTIONS
        assert AuditAction.SENSITIVE_DATA_ACCESSED in RESTRICTED_AUDIT_ACTIONS
    
    @pytest.mark.asyncio
    async def test_resource_history_filtering_for_hr(self):
        """HR should see filtered resource history."""
        from api.routes.audit import get_resource_history
        
        hr_user = {
            'employee_id': 'HR005',
            'role': 'HR',
            'is_admin': False,
            'designation': 'HR_MANAGER'
        }
        
        mock_history = [
            {'action': AuditAction.USER_UPDATED.value, 'resource_id': 'EMP001'},
            {'action': AuditAction.ADMIN_GRANTED.value, 'resource_id': 'EMP001'},
            {'action': AuditAction.TEAM_MEMBER_ADDED.value, 'resource_id': 'EMP001'},
        ]
        
        with patch('api.routes.audit.audit_logger') as mock_logger:
            mock_logger.get_resource_history = AsyncMock(return_value=mock_history)
            
            result = await get_resource_history(
                resource_type='user',
                resource_id='EMP001',
                limit=50,
                current_user=hr_user
            )
        
        # HR should see only 2 events (USER_UPDATED and TEAM_MEMBER_ADDED)
        assert result['total_events'] == 2
        assert result['filtered_for_role'] == 'HR'
        
        returned_actions = [log['action'] for log in result['history']]
        assert AuditAction.ADMIN_GRANTED.value not in returned_actions
