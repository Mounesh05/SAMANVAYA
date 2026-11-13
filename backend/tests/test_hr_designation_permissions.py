"""
Tests for HR Designation-Based Permissions (GAP 3)

Verifies:
- HR_MANAGER has broad HR access
- RECRUITER has limited access (no compensation/grievances)
- EMPLOYEE_RELATIONS has grievance access
- COMPENSATION_BENEFITS restricted to designated users
- HR_OPERATIONS has employee management access
- HRBP has strategic HR access
"""

import pytest
from core.permissions import Permission, get_user_permissions, HR_DESIGNATION_PERMISSIONS


class TestHRDesignationPermissions:
    """Test HR designation-based permission differentiation."""
    
    def test_hr_manager_permissions(self):
        """HR_MANAGER should have broad HR access."""
        permissions = get_user_permissions("HR", is_admin=False, designation="HR_MANAGER")
        
        # Should have core HR permissions
        assert Permission.VIEW_EMPLOYEE_DIRECTORY in permissions
        assert Permission.VIEW_EMPLOYEE_PROFILE in permissions
        assert Permission.VIEW_ORG_CHART in permissions
        assert Permission.VIEW_PERFORMANCE_OUTCOMES in permissions
        
        # Should have employee management
        assert Permission.CREATE_EMPLOYEE in permissions
        assert Permission.UPDATE_EMPLOYEE_PROFILE in permissions
        assert Permission.DEACTIVATE_EMPLOYEE in permissions
        
        # Should have transfer management
        assert Permission.VIEW_TRANSFER_REQUESTS in permissions
        assert Permission.REVIEW_TRANSFER_REQUEST in permissions
        assert Permission.UPDATE_EMPLOYMENT_RECORDS in permissions
        
        # Should have sensitive access
        assert Permission.VIEW_COMPENSATION in permissions
        assert Permission.VIEW_GRIEVANCES in permissions
        assert Permission.MANAGE_CANDIDATES in permissions
    
    def test_recruiter_permissions(self):
        """RECRUITER should have limited access - no compensation/grievances."""
        permissions = get_user_permissions("HR", is_admin=False, designation="RECRUITER")
        
        # Should have basic employee view
        assert Permission.VIEW_EMPLOYEE_DIRECTORY in permissions
        assert Permission.VIEW_EMPLOYEE_PROFILE in permissions
        
        # Should have recruitment permissions
        assert Permission.CREATE_EMPLOYEE in permissions
        assert Permission.MANAGE_CANDIDATES in permissions
        
        # Should NOT have sensitive access
        assert Permission.VIEW_COMPENSATION not in permissions
        assert Permission.VIEW_GRIEVANCES not in permissions
        assert Permission.DEACTIVATE_EMPLOYEE not in permissions
        assert Permission.UPDATE_EMPLOYMENT_RECORDS not in permissions
        assert Permission.VIEW_PERFORMANCE_OUTCOMES not in permissions
    
    def test_hr_operations_permissions(self):
        """HR_OPERATIONS should have operational access."""
        permissions = get_user_permissions("HR", is_admin=False, designation="HR_OPERATIONS")
        
        # Should have employee management
        assert Permission.VIEW_EMPLOYEE_DIRECTORY in permissions
        assert Permission.VIEW_EMPLOYEE_PROFILE in permissions
        assert Permission.CREATE_EMPLOYEE in permissions
        assert Permission.UPDATE_EMPLOYEE_PROFILE in permissions
        assert Permission.DEACTIVATE_EMPLOYEE in permissions
        assert Permission.UPDATE_EMPLOYMENT_RECORDS in permissions
        
        # Should have transfer visibility
        assert Permission.VIEW_TRANSFER_REQUESTS in permissions
        
        # Should NOT have strategic or sensitive access
        assert Permission.VIEW_COMPENSATION not in permissions
        assert Permission.VIEW_GRIEVANCES not in permissions
        assert Permission.VIEW_PERFORMANCE_OUTCOMES not in permissions
        assert Permission.REVIEW_TRANSFER_REQUEST not in permissions
    
    def test_hrbp_permissions(self):
        """HRBP should have strategic HR access."""
        permissions = get_user_permissions("HR", is_admin=False, designation="HRBP")
        
        # Should have strategic view
        assert Permission.VIEW_EMPLOYEE_DIRECTORY in permissions
        assert Permission.VIEW_EMPLOYEE_PROFILE in permissions
        assert Permission.VIEW_ORG_CHART in permissions
        assert Permission.VIEW_PERFORMANCE_OUTCOMES in permissions
        
        # Should have transfer and grievance access
        assert Permission.VIEW_TRANSFER_REQUESTS in permissions
        assert Permission.REVIEW_TRANSFER_REQUEST in permissions
        assert Permission.VIEW_GRIEVANCES in permissions
        
        # Should have feedback permissions
        assert Permission.SUBMIT_HR_FEEDBACK in permissions
        assert Permission.VIEW_ROLE_FEEDBACK in permissions
        
        # Should NOT have operational permissions
        assert Permission.CREATE_EMPLOYEE not in permissions
        assert Permission.DEACTIVATE_EMPLOYEE not in permissions
        assert Permission.UPDATE_EMPLOYMENT_RECORDS not in permissions
        assert Permission.VIEW_COMPENSATION not in permissions
    
    def test_employee_relations_permissions(self):
        """EMPLOYEE_RELATIONS should have grievance access."""
        permissions = get_user_permissions("HR", is_admin=False, designation="EMPLOYEE_RELATIONS")
        
        # Should have basic employee view
        assert Permission.VIEW_EMPLOYEE_DIRECTORY in permissions
        assert Permission.VIEW_EMPLOYEE_PROFILE in permissions
        
        # Should have grievance access
        assert Permission.VIEW_GRIEVANCES in permissions
        
        # Should NOT have other sensitive permissions
        assert Permission.VIEW_COMPENSATION not in permissions
        assert Permission.DEACTIVATE_EMPLOYEE not in permissions
        assert Permission.UPDATE_EMPLOYMENT_RECORDS not in permissions
        assert Permission.VIEW_PERFORMANCE_OUTCOMES not in permissions
        assert Permission.MANAGE_CANDIDATES not in permissions
    
    def test_compensation_benefits_permissions(self):
        """COMPENSATION_BENEFITS should have compensation access."""
        permissions = get_user_permissions("HR", is_admin=False, designation="COMPENSATION_BENEFITS")
        
        # Should have basic employee view
        assert Permission.VIEW_EMPLOYEE_DIRECTORY in permissions
        assert Permission.VIEW_EMPLOYEE_PROFILE in permissions
        
        # Should have compensation access
        assert Permission.VIEW_COMPENSATION in permissions
        
        # Should NOT have other sensitive permissions
        assert Permission.VIEW_GRIEVANCES not in permissions
        assert Permission.DEACTIVATE_EMPLOYEE not in permissions
        assert Permission.UPDATE_EMPLOYMENT_RECORDS not in permissions
        assert Permission.VIEW_PERFORMANCE_OUTCOMES not in permissions
        assert Permission.MANAGE_CANDIDATES not in permissions
    
    def test_hr_without_designation_gets_base_permissions(self):
        """HR role without designation should get base HR permissions only."""
        permissions = get_user_permissions("HR", is_admin=False, designation=None)
        
        # Should have base HR role permissions
        assert Permission.VIEW_OWN_DATA in permissions
        assert Permission.VIEW_EMPLOYEE_DIRECTORY in permissions
        assert Permission.MANAGE_EMPLOYEES in permissions
        
        # Designation-specific permissions should be limited
        # Base HR role has some permissions, but not all designation-specific ones
    
    def test_hr_admin_gets_all_permissions(self):
        """HR with admin flag should get admin permissions on top of HR."""
        permissions = get_user_permissions("HR", is_admin=True, designation="HR_MANAGER")
        
        # Should have HR permissions
        assert Permission.VIEW_EMPLOYEE_DIRECTORY in permissions
        assert Permission.MANAGE_EMPLOYEES in permissions
        
        # Should also have admin permissions
        assert Permission.MANAGE_USERS in permissions
        assert Permission.MANAGE_TEAMS in permissions
        # CR-008: evaluations are people decisions, not admin rights.
        assert Permission.TRIGGER_AI_EVALUATION not in permissions
        assert Permission.TRIGGER_BULK_EVALUATION not in permissions


class TestDesignationBoundaries:
    """Test permission boundaries between designations."""
    
    def test_recruiter_cannot_view_compensation(self):
        """Recruiters should not access compensation data."""
        recruiter_perms = get_user_permissions("HR", is_admin=False, designation="RECRUITER")
        
        assert Permission.VIEW_COMPENSATION not in recruiter_perms
    
    def test_only_designated_roles_view_compensation(self):
        """Only HR_MANAGER and COMPENSATION_BENEFITS view compensation."""
        hr_manager_perms = get_user_permissions("HR", is_admin=False, designation="HR_MANAGER")
        comp_perms = get_user_permissions("HR", is_admin=False, designation="COMPENSATION_BENEFITS")
        hrbp_perms = get_user_permissions("HR", is_admin=False, designation="HRBP")
        recruiter_perms = get_user_permissions("HR", is_admin=False, designation="RECRUITER")
        
        assert Permission.VIEW_COMPENSATION in hr_manager_perms
        assert Permission.VIEW_COMPENSATION in comp_perms
        assert Permission.VIEW_COMPENSATION not in hrbp_perms
        assert Permission.VIEW_COMPENSATION not in recruiter_perms
    
    def test_only_designated_roles_view_grievances(self):
        """Only HR_MANAGER, HRBP, EMPLOYEE_RELATIONS view grievances."""
        hr_manager_perms = get_user_permissions("HR", is_admin=False, designation="HR_MANAGER")
        hrbp_perms = get_user_permissions("HR", is_admin=False, designation="HRBP")
        er_perms = get_user_permissions("HR", is_admin=False, designation="EMPLOYEE_RELATIONS")
        recruiter_perms = get_user_permissions("HR", is_admin=False, designation="RECRUITER")
        ops_perms = get_user_permissions("HR", is_admin=False, designation="HR_OPERATIONS")
        
        assert Permission.VIEW_GRIEVANCES in hr_manager_perms
        assert Permission.VIEW_GRIEVANCES in hrbp_perms
        assert Permission.VIEW_GRIEVANCES in er_perms
        assert Permission.VIEW_GRIEVANCES not in recruiter_perms
        assert Permission.VIEW_GRIEVANCES not in ops_perms
    
    def test_deactivate_employee_restricted(self):
        """Only HR_MANAGER and HR_OPERATIONS can deactivate employees."""
        hr_manager_perms = get_user_permissions("HR", is_admin=False, designation="HR_MANAGER")
        ops_perms = get_user_permissions("HR", is_admin=False, designation="HR_OPERATIONS")
        recruiter_perms = get_user_permissions("HR", is_admin=False, designation="RECRUITER")
        hrbp_perms = get_user_permissions("HR", is_admin=False, designation="HRBP")
        
        assert Permission.DEACTIVATE_EMPLOYEE in hr_manager_perms
        assert Permission.DEACTIVATE_EMPLOYEE in ops_perms
        assert Permission.DEACTIVATE_EMPLOYEE not in recruiter_perms
        assert Permission.DEACTIVATE_EMPLOYEE not in hrbp_perms


class TestHRDesignationDefinitions:
    """Test that all HR designations are properly defined."""
    
    def test_all_hr_designations_exist(self):
        """All expected HR designations should be defined."""
        expected_designations = [
            "HR_MANAGER",
            "RECRUITER",
            "HR_OPERATIONS",
            "HRBP",
            "EMPLOYEE_RELATIONS",
            "COMPENSATION_BENEFITS",
        ]
        
        for designation in expected_designations:
            assert designation in HR_DESIGNATION_PERMISSIONS, \
                f"Designation {designation} not found in HR_DESIGNATION_PERMISSIONS"
    
    def test_each_designation_has_unique_permissions(self):
        """Each designation should have a distinct permission set."""
        designations = list(HR_DESIGNATION_PERMISSIONS.keys())
        
        for i, des1 in enumerate(designations):
            for des2 in designations[i+1:]:
                perms1 = HR_DESIGNATION_PERMISSIONS[des1]
                perms2 = HR_DESIGNATION_PERMISSIONS[des2]
                
                # Not all sets should be identical
                if des1 != des2:
                    # They can overlap but shouldn't be identical
                    assert perms1 != perms2 or len(perms1) == 0, \
                        f"{des1} and {des2} have identical permissions"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
