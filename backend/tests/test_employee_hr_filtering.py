"""
Tests for Employee API HR Data Filtering (GAP 1)

Verifies:
- HR users receive filtered employee data without technical fields
- Engineering users receive complete employee data
- Field filtering is applied consistently across all endpoints
"""

import pytest
from unittest.mock import AsyncMock, patch
from domain.schemas.hr_views import EmployeeHRView


class TestEmployeeHRFiltering:
    """Test employee data filtering for HR users."""
    
    def test_employee_hr_view_excludes_technical_fields(self):
        """HR view should exclude github_username, is_admin, and other technical fields."""
        employee_data = {
            "employee_id": "EMP001",
            "name": "John Doe",
            "email": "john@example.com",
            "role": "DEVELOPER",
            "dept": "Engineering",
            "github_username": "johndoe123",  # Should be excluded
            "is_admin": False,  # Should be excluded
            "team_id": "TEAM001",
            "is_active": True,
            "created_at": "2024-01-01T00:00:00Z",
        }
        
        hr_view = EmployeeHRView.from_employee(employee_data)
        
        # Should have basic fields
        assert hr_view.employee_id == "EMP001"
        assert hr_view.name == "John Doe"
        assert hr_view.email == "john@example.com"
        assert hr_view.role == "DEVELOPER"
        assert hr_view.dept == "Engineering"
        assert hr_view.current_team_id == "TEAM001"
        assert hr_view.is_active == True
        
        # Should NOT have technical fields (verify by checking model schema)
        hr_dict = hr_view.model_dump()
        assert "github_username" not in hr_dict or hr_dict["github_username"] is None
        assert "is_admin" not in hr_dict
        assert "project_ids" not in hr_dict
    
    def test_employee_hr_view_includes_hr_relevant_fields(self):
        """HR view should include employment and organizational fields."""
        employee_data = {
            "employee_id": "EMP002",
            "name": "Jane Smith",
            "email": "jane@example.com",
            "role": "LEAD",
            "dept": "Engineering",
            "designation": "Senior Technical Lead",
            "reporting_manager_id": "EMP003",
            "team_id": "TEAM002",
            "employment_type": "Full-time",
            "joining_date": "2023-01-15",
            "location": "Bangalore",
            "is_active": True,
        }
        
        hr_view = EmployeeHRView.from_employee(employee_data)
        
        # Should have HR-relevant fields
        assert hr_view.designation == "Senior Technical Lead"
        assert hr_view.reporting_manager_id == "EMP003"
        assert hr_view.employment_type == "Full-time"
        assert hr_view.location == "Bangalore"
        assert hr_view.employment_status == "active"
    
    @pytest.mark.asyncio
    async def test_list_employees_filters_for_hr(self, monkeypatch):
        """List employees endpoint should return filtered data for HR users."""
        from api.routes import employees
        from repositories.user_repository import UserRepository
        
        hr_user = {
            "employee_id": "HR001",
            "role": "HR",
            "is_admin": False,
            "designation": "HR_MANAGER",
        }
        
        mock_employees = [
            {
                "employee_id": "EMP001",
                "name": "Dev One",
                "email": "dev1@example.com",
                "role": "DEVELOPER",
                "dept": "Engineering",
                "github_username": "dev1",  # Should be filtered
                "is_admin": False,  # Should be filtered
                "team_id": "TEAM001",
                "is_active": True,
            }
        ]
        
        mock_repo = AsyncMock(spec=UserRepository)
        mock_repo.find_all = AsyncMock(return_value=mock_employees)
        
        with patch.object(employees, 'UserRepository', return_value=mock_repo):
            result = await employees.list_employees(
                role=None, dept=None, team_id=None, is_active=None, limit=100, user=hr_user
            )
        
        # Should return EmployeeHRView instances
        assert len(result) == 1
        assert isinstance(result[0], EmployeeHRView)
        assert result[0].employee_id == "EMP001"
        
        # Technical fields should not be in the response
        result_dict = result[0].model_dump()
        assert "github_username" not in result_dict or result_dict["github_username"] is None
        assert "is_admin" not in result_dict
    
    @pytest.mark.asyncio
    async def test_list_employees_full_data_for_engineering(self, monkeypatch):
        """List employees endpoint should return complete data for engineering users."""
        from api.routes import employees
        from repositories.user_repository import UserRepository
        from api.routes.employees import EmployeeResponse
        
        ceo_user = {
            "employee_id": "CEO001",
            "role": "CEO",
            "is_admin": True,
        }
        
        mock_employees = [
            {
                "employee_id": "EMP001",
                "name": "Dev One",
                "email": "dev1@example.com",
                "role": "DEVELOPER",
                "dept": "Engineering",
                "github_username": "dev1",
                "is_admin": False,
                "team_id": "TEAM001",
                "is_active": True,
            }
        ]
        
        mock_repo = AsyncMock(spec=UserRepository)
        mock_repo.find_all = AsyncMock(return_value=mock_employees)
        
        with patch.object(employees, 'UserRepository', return_value=mock_repo):
            result = await employees.list_employees(
                role=None, dept=None, team_id=None, is_active=None, limit=100, user=ceo_user
            )
        
        # Should return EmployeeResponse instances with full data
        assert len(result) == 1
        assert isinstance(result[0], EmployeeResponse)
        assert result[0].github_username == "dev1"
        assert result[0].is_admin == False
    
    @pytest.mark.asyncio
    async def test_get_employee_filters_for_hr(self, monkeypatch):
        """Get employee endpoint should return filtered data for HR users."""
        from api.routes import employees
        from repositories.user_repository import UserRepository
        
        hr_user = {
            "employee_id": "HR001",
            "role": "HR",
            "is_admin": False,
            "designation": "HR_MANAGER",
        }
        
        mock_employee = {
            "employee_id": "EMP001",
            "name": "Dev One",
            "email": "dev1@example.com",
            "role": "DEVELOPER",
            "dept": "Engineering",
            "github_username": "dev1",
            "is_admin": False,
            "team_id": "TEAM001",
            "is_active": True,
        }
        
        mock_repo = AsyncMock(spec=UserRepository)
        mock_repo.find_by_employee_id = AsyncMock(return_value=mock_employee)
        
        with patch.object(employees, 'UserRepository', return_value=mock_repo):
            result = await employees.get_employee("EMP001", user=hr_user)
        
        # Should return EmployeeHRView
        assert isinstance(result, EmployeeHRView)
        result_dict = result.model_dump()
        assert "github_username" not in result_dict or result_dict["github_username"] is None
        assert "is_admin" not in result_dict
    
    @pytest.mark.asyncio
    async def test_create_employee_filters_response_for_hr(self, monkeypatch):
        """Create employee endpoint should return filtered data for HR users."""
        from api.routes import employees
        from repositories.user_repository import UserRepository
        from api.routes.employees import EmployeeCreate
        
        hr_user = {
            "employee_id": "HR001",
            "role": "HR",
            "is_admin": False,
            "designation": "HR_MANAGER",
        }
        
        new_employee = EmployeeCreate(
            employee_id="EMP002",
            name="New Employee",
            email="new@example.com",
            role="DEVELOPER",
            dept="Engineering",
            password="SecurePass123!Strong",
            organisation_password="OrgPass123456!Strong",
            employee_password="EmpPass123456!Strong",
            github_username="newdev",
            is_admin=False,
        )
        
        mock_repo = AsyncMock(spec=UserRepository)
        mock_repo.find_by_employee_id = AsyncMock(return_value=None)
        mock_repo.find_by_email = AsyncMock(return_value=None)
        mock_repo.insert = AsyncMock(return_value=None)
        
        # Mock log_audit
        async def mock_log_audit(*args, **kwargs):
            pass
        
        with patch.object(employees, 'UserRepository', return_value=mock_repo), \
             patch.object(employees, 'log_audit', new=mock_log_audit):
            result = await employees.create_employee(new_employee, user=hr_user)
        
        # HR should receive filtered view
        assert isinstance(result, EmployeeHRView)
        result_dict = result.model_dump()
        assert "github_username" not in result_dict or result_dict["github_username"] is None
        assert "is_admin" not in result_dict


class TestEmployeeFieldExclusions:
    """Test specific field exclusions from HR view."""
    
    def test_github_username_excluded(self):
        """github_username should not be in HR view."""
        employee = {
            "employee_id": "EMP001",
            "name": "Test User",
            "email": "test@example.com",
            "role": "DEVELOPER",
            "dept": "Engineering",
            "github_username": "testuser123",
            "is_active": True,
        }
        
        hr_view = EmployeeHRView.from_employee(employee)
        hr_dict = hr_view.model_dump()
        
        # github_username should be excluded
        assert "github_username" not in hr_dict or hr_dict["github_username"] is None
    
    def test_is_admin_excluded(self):
        """is_admin should not be in HR view."""
        employee = {
            "employee_id": "EMP001",
            "name": "Test User",
            "email": "test@example.com",
            "role": "DEVELOPER",
            "dept": "Engineering",
            "is_admin": True,
            "is_active": True,
        }
        
        hr_view = EmployeeHRView.from_employee(employee)
        hr_dict = hr_view.model_dump()
        
        # is_admin should not be exposed in HR view
        assert "is_admin" not in hr_dict
    
    def test_project_ids_excluded(self):
        """project_ids should not be in HR view."""
        employee = {
            "employee_id": "EMP001",
            "name": "Test User",
            "email": "test@example.com",
            "role": "DEVELOPER",
            "dept": "Engineering",
            "project_ids": ["PROJ001", "PROJ002"],
            "is_active": True,
        }
        
        hr_view = EmployeeHRView.from_employee(employee)
        hr_dict = hr_view.model_dump()
        
        # project_ids should be excluded
        assert "project_ids" not in hr_dict


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
