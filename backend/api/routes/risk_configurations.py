"""
Risk Configuration Management API Routes.

Provides CRUD operations for managing risk/quality weights and thresholds.
Supports:
- Global default configuration (project_id=None)
- Per-project overrides (project_id=specific project)
- Validation of weight configurations
- Cache invalidation
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from pydantic import BaseModel, Field

from core.dependencies import get_current_user
from domain.models.risk_configuration import (
    RiskConfiguration,
    RiskDimensionWeights,
    QualityDimensionWeights,
    RiskThresholds,
    PRSizeThresholds,
)
from domain.services.risk_config_service import get_risk_config_service

router = APIRouter()


# ── Request/Response Models ───────────────────────────────────────────────────

class CreateRiskConfigRequest(BaseModel):
    """Request body for creating/updating risk configuration."""
    project_id: Optional[str] = Field(None, description="Project ID or None for global")
    name: str = Field(..., description="Configuration name")
    risk_weights: RiskDimensionWeights
    quality_weights: QualityDimensionWeights
    base_risk: float = Field(10.0, ge=0, le=100)
    risk_thresholds: RiskThresholds = Field(default_factory=RiskThresholds)
    pr_size_thresholds: PRSizeThresholds = Field(default_factory=PRSizeThresholds)


class RiskConfigResponse(BaseModel):
    """Response model for risk configuration."""
    id: Optional[str] = None
    project_id: Optional[str]
    name: str
    risk_weights: dict
    quality_weights: dict
    base_risk: float
    risk_thresholds: dict
    pr_size_thresholds: dict
    created_by: str
    created_at: str
    updated_at: str
    is_active: bool
    validation_status: dict


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[RiskConfigResponse])
async def list_risk_configurations(
    project_id: Optional[str] = None,
    include_inactive: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """
    List all risk configurations.
    
    Query parameters:
    - project_id: Filter by project (None = only global configs)
    - include_inactive: Include inactive configurations
    
    Requires: Any authenticated user
    """
    service = get_risk_config_service()
    configs = await service.list_configurations(project_id, include_inactive)
    
    return [
        RiskConfigResponse(
            id=config.id,
            project_id=config.project_id,
            name=config.name,
            risk_weights=config.risk_weights.model_dump(),
            quality_weights=config.quality_weights.model_dump(),
            base_risk=config.base_risk,
            risk_thresholds=config.risk_thresholds.model_dump(),
            pr_size_thresholds=config.pr_size_thresholds.model_dump(),
            created_by=config.created_by,
            created_at=config.created_at.isoformat(),
            updated_at=config.updated_at.isoformat(),
            is_active=config.is_active,
            validation_status={
                "is_valid": config.validate_weights()[0],
                "errors": config.validate_weights()[1],
            },
        )
        for config in configs
    ]


@router.get("/{project_id_or_global}", response_model=RiskConfigResponse)
async def get_risk_configuration(
    project_id_or_global: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get risk configuration for a specific project or global default.
    
    Path parameter:
    - project_id_or_global: Project ID or "global" for global default
    
    Returns the active configuration (from DB or hardcoded fallback).
    
    Requires: Any authenticated user
    """
    project_id = None if project_id_or_global == "global" else project_id_or_global
    
    service = get_risk_config_service()
    config = await service.get_configuration(project_id, use_cache=False)
    
    return RiskConfigResponse(
        id=config.id,
        project_id=config.project_id,
        name=config.name,
        risk_weights=config.risk_weights.model_dump(),
        quality_weights=config.quality_weights.model_dump(),
        base_risk=config.base_risk,
        risk_thresholds=config.risk_thresholds.model_dump(),
        pr_size_thresholds=config.pr_size_thresholds.model_dump(),
        created_by=config.created_by,
        created_at=config.created_at.isoformat(),
        updated_at=config.updated_at.isoformat(),
        is_active=config.is_active,
        validation_status={
            "is_valid": config.validate_weights()[0],
            "errors": config.validate_weights()[1],
        },
    )


@router.post("/", response_model=dict)
async def create_risk_configuration(
    request: CreateRiskConfigRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Create or update risk configuration.
    
    Body: CreateRiskConfigRequest with all weight configurations
    
    Validates:
    - Risk weights sum to 100
    - Quality weights sum to 1.0
    - Thresholds in valid ranges
    
    Requires: LEAD, PM, CEO, or DEVOPS role
    """
    # Check permissions (only certain roles can modify configurations)
    allowed_roles = ["LEAD", "PM", "CEO", "DEVOPS"]
    if current_user.get("role") not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail=f"Only {', '.join(allowed_roles)} can modify risk configurations"
        )
    
    # Create configuration object
    config = RiskConfiguration(
        project_id=request.project_id,
        name=request.name,
        risk_weights=request.risk_weights,
        quality_weights=request.quality_weights,
        base_risk=request.base_risk,
        risk_thresholds=request.risk_thresholds,
        pr_size_thresholds=request.pr_size_thresholds,
        created_by=current_user.get("name", current_user.get("employee_id")),
    )
    
    # Validate before saving
    is_valid, errors = config.validate_weights()
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Configuration validation failed",
                "errors": errors,
            }
        )
    
    # Save configuration
    service = get_risk_config_service()
    try:
        config_id = await service.save_configuration(config, current_user.get("name", current_user.get("employee_id")))
        return {
            "message": "Risk configuration saved successfully",
            "config_id": config_id,
            "project_id": request.project_id or "global",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save configuration: {str(e)}")


@router.delete("/{project_id_or_global}", response_model=dict)
async def delete_risk_configuration(
    project_id_or_global: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Soft-delete risk configuration (set is_active=False).
    
    Path parameter:
    - project_id_or_global: Project ID or "global" for global default
    
    Note: This doesn't delete the configuration from database,
    just marks it as inactive. System will fall back to hardcoded defaults.
    
    Requires: LEAD, PM, CEO, or DEVOPS role
    """
    # Check permissions
    allowed_roles = ["LEAD", "PM", "CEO", "DEVOPS"]
    if current_user.get("role") not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail=f"Only {', '.join(allowed_roles)} can delete risk configurations"
        )
    
    project_id = None if project_id_or_global == "global" else project_id_or_global
    
    service = get_risk_config_service()
    deleted = await service.delete_configuration(project_id)
    
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"No active configuration found for project_id={project_id}"
        )
    
    return {
        "message": "Risk configuration deleted successfully",
        "project_id": project_id or "global",
        "note": "System will fall back to hardcoded defaults",
    }


@router.post("/cache/clear", response_model=dict)
async def clear_cache(
    project_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Clear configuration cache.
    
    Query parameter:
    - project_id: Specific project to clear, or None to clear all
    
    Useful after bulk updates or database migrations.
    
    Requires: DEVOPS or CEO role
    """
    # Only DEVOPS or CEO can clear cache
    if current_user.get("role") not in ["DEVOPS", "CEO"]:
        raise HTTPException(
            status_code=403,
            detail="Only DEVOPS or CEO can clear configuration cache"
        )
    
    service = get_risk_config_service()
    service.clear_cache(project_id)
    
    return {
        "message": "Cache cleared successfully",
        "scope": project_id or "all",
    }


@router.get("/validate/{project_id_or_global}", response_model=dict)
async def validate_configuration(
    project_id_or_global: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Validate a risk configuration without saving.
    
    Path parameter:
    - project_id_or_global: Project ID or "global" for global default
    
    Returns validation results with detailed error messages.
    
    Requires: Any authenticated user
    """
    project_id = None if project_id_or_global == "global" else project_id_or_global
    
    service = get_risk_config_service()
    config = await service.get_configuration(project_id, use_cache=False)
    
    is_valid, errors = config.validate_weights()
    
    # Additional validation checks
    validation_details = {
        "risk_weights": {
            "sum": config.risk_weights.sum(),
            "expected_sum": 100.0,
            "is_valid": abs(config.risk_weights.sum() - 100.0) < 0.01,
        },
        "quality_weights": {
            "sum": config.quality_weights.sum(),
            "expected_sum": 1.0,
            "is_valid": abs(config.quality_weights.sum() - 1.0) < 0.01,
        },
        "thresholds": {
            "critical": config.risk_thresholds.critical,
            "high": config.risk_thresholds.high,
            "medium": config.risk_thresholds.medium,
            "is_valid_order": (
                config.risk_thresholds.critical > config.risk_thresholds.high and
                config.risk_thresholds.high > config.risk_thresholds.medium
            ),
        },
    }
    
    return {
        "is_valid": is_valid,
        "errors": errors,
        "validation_details": validation_details,
        "project_id": project_id or "global",
    }
