"""
Risk Configuration Model - Production-scale configurable risk/quality weights.

Supports:
- Global default configuration (project_id = None)
- Per-project overrides (project_id = specific project)
- Validation of weights (must sum correctly)
- Audit trail (created_by, updated_at)
"""

from datetime import datetime, timezone
from typing import Dict, Optional
from pydantic import BaseModel, Field, field_validator


class RiskDimensionWeights(BaseModel):
    """
    Risk dimension weights - must sum to 100.
    
    NOTE: alpha_size_zscore and zeta_complexity are LEGACY Z-score fields
    that remain in the schema for backward compatibility but are NEVER USED
    in current calculations (baseline=None always).
    
    RiskEngine falls back to simple threshold-based risk calculation.
    Full removal requires database migration.
    
    See: backend/intelligence/ARCHITECTURE.md for details.
    """
    alpha_size_zscore: float = Field(
        12.0,
        description="LEGACY: PR size Z-score (unused, baseline=None)"
    )
    beta_hotspot: float = Field(20.0, description="Historical incident-prone files")
    gamma_dependency: float = Field(15.0, description="New/updated dependencies")
    delta_missing_tests: float = Field(18.0, description="Changed lines without tests")
    epsilon_security: float = Field(25.0, description="CVSS-weighted vulnerabilities")
    zeta_complexity: float = Field(
        10.0,
        description="LEGACY: Complexity spike (unused, baseline=None)"
    )
    
    @field_validator('*')
    @classmethod
    def validate_positive(cls, v):
        if v < 0:
            raise ValueError("Weights must be non-negative")
        return v
    
    def sum(self) -> float:
        """Calculate sum of all weights."""
        return (
            self.alpha_size_zscore +
            self.beta_hotspot +
            self.gamma_dependency +
            self.delta_missing_tests +
            self.epsilon_security +
            self.zeta_complexity
        )


class QualityDimensionWeights(BaseModel):
    """Quality dimension weights - must sum to 1.0."""
    static_security: float = Field(0.25, description="Lint + security findings")
    testing: float = Field(0.25, description="Coverage + test failures")
    complexity: float = Field(0.20, description="Cyclomatic complexity")
    architecture: float = Field(0.20, description="Layer violations + circular deps")
    duplication: float = Field(0.10, description="Code duplication")
    
    @field_validator('*')
    @classmethod
    def validate_range(cls, v):
        if not 0 <= v <= 1:
            raise ValueError("Quality weights must be between 0 and 1")
        return v
    
    def sum(self) -> float:
        """Calculate sum of all weights."""
        return (
            self.static_security +
            self.testing +
            self.complexity +
            self.architecture +
            self.duplication
        )


class RiskThresholds(BaseModel):
    """Risk level classification thresholds."""
    critical: int = Field(70, ge=0, le=100, description="Score >= this is CRITICAL")
    high: int = Field(50, ge=0, le=100, description="Score >= this is HIGH")
    medium: int = Field(30, ge=0, le=100, description="Score >= this is MEDIUM")
    # LOW is implicit: score < medium
    
    @field_validator('*')
    @classmethod
    def validate_order(cls, v, info):
        """Ensure thresholds are in descending order."""
        values = info.data
        if 'critical' in values and 'high' in values:
            if values['critical'] <= values['high']:
                raise ValueError("critical threshold must be > high threshold")
        if 'high' in values and 'medium' in values:
            if values['high'] <= values['medium']:
                raise ValueError("high threshold must be > medium threshold")
        return v


class PRSizeThresholds(BaseModel):
    """PR size classification thresholds."""
    large_files: int = Field(20, ge=1, description="Files > this = large PR")
    medium_files: int = Field(10, ge=1, description="Files > this = medium PR")
    small_files: int = Field(5, ge=1, description="Files > this = small PR")
    
    large_risk: int = Field(30, ge=0, le=100, description="Risk points for large PR")
    medium_risk: int = Field(20, ge=0, le=100, description="Risk points for medium PR")
    small_risk: int = Field(10, ge=0, le=100, description="Risk points for small PR")


class RiskConfiguration(BaseModel):
    """
    Risk configuration document for MongoDB.
    
    - project_id = None: Global default configuration
    - project_id = "PRJ-123": Project-specific override
    """
    id: Optional[str] = Field(None, alias="_id", description="MongoDB _id")
    project_id: Optional[str] = Field(None, description="Project ID or None for global")
    
    # Weight configurations
    risk_weights: RiskDimensionWeights = Field(default_factory=RiskDimensionWeights)
    quality_weights: QualityDimensionWeights = Field(default_factory=QualityDimensionWeights)
    base_risk: float = Field(10.0, ge=0, le=100, description="Base risk for all PRs")
    
    # Threshold configurations
    risk_thresholds: RiskThresholds = Field(default_factory=RiskThresholds)
    pr_size_thresholds: PRSizeThresholds = Field(default_factory=PRSizeThresholds)
    
    # Metadata
    name: str = Field(..., description="Configuration name/description")
    created_by: str = Field(..., description="User who created this config")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = Field(True, description="Whether this config is active")
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "project_id": None,
                "name": "Global Default Configuration",
                "created_by": "admin",
                "risk_weights": {
                    "alpha_size_zscore": 12.0,
                    "beta_hotspot": 20.0,
                    "gamma_dependency": 15.0,
                    "delta_missing_tests": 18.0,
                    "epsilon_security": 25.0,
                    "zeta_complexity": 10.0,
                },
                "quality_weights": {
                    "static_security": 0.25,
                    "testing": 0.25,
                    "complexity": 0.20,
                    "architecture": 0.20,
                    "duplication": 0.10,
                },
                "base_risk": 10.0,
            }
        }
    
    def validate_weights(self) -> tuple[bool, list[str]]:
        """
        Validate that all weights sum correctly.
        
        Returns:
            (is_valid, error_messages)
        """
        errors = []
        
        # Validate risk weights sum to 100
        risk_sum = self.risk_weights.sum()
        if abs(risk_sum - 100.0) > 0.01:  # Allow small floating point error
            errors.append(f"Risk weights must sum to 100, got {risk_sum}")
        
        # Validate quality weights sum to 1.0
        quality_sum = self.quality_weights.sum()
        if abs(quality_sum - 1.0) > 0.01:
            errors.append(f"Quality weights must sum to 1.0, got {quality_sum}")
        
        return (len(errors) == 0, errors)
