"""
Risk Configuration Service - Production-scale configurable risk/quality weights.

Hybrid approach:
1. Try to load from database (project-specific or global)
2. Fall back to hardcoded defaults from risk_rules.py
3. Cache in memory for performance

This ensures:
- Fast lookups (cached)
- Flexibility (database overrides)
- Safety (always has fallback)
- No breaking changes (defaults in code)
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timezone

from core.database import col
from domain.models.risk_configuration import (
    RiskConfiguration,
    RiskDimensionWeights,
    QualityDimensionWeights,
    RiskThresholds,
    PRSizeThresholds,
)

# Import hardcoded defaults as fallback
from intelligence.rules.risk_rules import (
    RISK_DIMENSION_WEIGHTS,
    QUALITY_DIMENSION_WEIGHTS,
    BASE_RISK,
    RiskRules,
    PR_SIZE_LARGE_THRESHOLD,
    PR_SIZE_MEDIUM_THRESHOLD,
    PR_SIZE_SMALL_THRESHOLD,
    PR_SIZE_LARGE_RISK,
    PR_SIZE_MEDIUM_RISK,
    PR_SIZE_SMALL_RISK,
)

logger = logging.getLogger(__name__)


class RiskConfigService:
    """
    Service for loading and managing risk configurations.
    
    Provides production-scale configurable risk/quality weights with:
    - Per-project overrides
    - Global defaults
    - In-memory caching
    - Fallback to hardcoded values
    """
    
    def __init__(self):
        self._cache: Dict[Optional[str], RiskConfiguration] = {}
        self._cache_timestamp: Dict[Optional[str], datetime] = {}
        self._cache_ttl_seconds = 300  # 5 minutes
    
    async def get_configuration(
        self,
        project_id: Optional[str] = None,
        use_cache: bool = True
    ) -> RiskConfiguration:
        """
        Get risk configuration for a project or global default.
        
        Lookup order:
        1. Check in-memory cache (if use_cache=True and not expired)
        2. Try project-specific configuration (if project_id provided)
        3. Try global default configuration (project_id=None)
        4. Fall back to hardcoded defaults from risk_rules.py
        
        Args:
            project_id: Project ID for project-specific config, None for global
            use_cache: Whether to use cached configuration
        
        Returns:
            RiskConfiguration (either from DB or hardcoded defaults)
        """
        # Check cache
        if use_cache and project_id in self._cache:
            cached_time = self._cache_timestamp.get(project_id)
            if cached_time:
                age_seconds = (datetime.now(timezone.utc) - cached_time).total_seconds()
                if age_seconds < self._cache_ttl_seconds:
                    logger.debug(f"Using cached config for project_id={project_id}")
                    return self._cache[project_id]
        
        # Try to load from database
        config = await self._load_from_database(project_id)
        
        if config:
            # Validate before returning
            is_valid, errors = config.validate_weights()
            if not is_valid:
                logger.error(
                    f"Invalid configuration in database for project_id={project_id}: {errors}"
                )
                # Fall through to defaults
            else:
                # Cache and return
                self._cache[project_id] = config
                self._cache_timestamp[project_id] = datetime.now(timezone.utc)
                logger.info(f"Loaded config from database for project_id={project_id}")
                return config
        
        # Fall back to hardcoded defaults
        logger.info(
            f"Using hardcoded defaults for project_id={project_id} "
            "(no database configuration found)"
        )
        default_config = self._create_default_configuration(project_id)
        
        # Cache the default
        self._cache[project_id] = default_config
        self._cache_timestamp[project_id] = datetime.now(timezone.utc)
        
        return default_config
    
    async def _load_from_database(
        self,
        project_id: Optional[str]
    ) -> Optional[RiskConfiguration]:
        """
        Load configuration from database.
        
        Lookup order:
        1. Try project-specific (if project_id provided)
        2. Try global default (project_id=None)
        
        Returns:
            RiskConfiguration if found, None otherwise
        """
        configs_col = col("risk_configurations")
        
        try:
            # Try project-specific first
            if project_id:
                doc = await configs_col.find_one({
                    "project_id": project_id,
                    "is_active": True
                })
                if doc:
                    return RiskConfiguration(**doc)
            
            # Fall back to global default
            doc = await configs_col.find_one({
                "project_id": None,
                "is_active": True
            })
            if doc:
                return RiskConfiguration(**doc)
            
            return None
        
        except Exception as e:
            logger.error(f"Error loading risk configuration from database: {e}")
            return None
    
    def _create_default_configuration(
        self,
        project_id: Optional[str]
    ) -> RiskConfiguration:
        """
        Create default configuration from hardcoded values in risk_rules.py.
        
        This ensures the system always works even if database is unavailable.
        """
        return RiskConfiguration(
            project_id=project_id,
            name=f"Hardcoded Default ({'Global' if project_id is None else project_id})",
            created_by="system",
            risk_weights=RiskDimensionWeights(
                alpha_size_zscore=RISK_DIMENSION_WEIGHTS["alpha_size_zscore"],
                beta_hotspot=RISK_DIMENSION_WEIGHTS["beta_hotspot"],
                gamma_dependency=RISK_DIMENSION_WEIGHTS["gamma_dependency"],
                delta_missing_tests=RISK_DIMENSION_WEIGHTS["delta_missing_tests"],
                epsilon_security=RISK_DIMENSION_WEIGHTS["epsilon_security"],
                zeta_complexity=RISK_DIMENSION_WEIGHTS["zeta_complexity"],
            ),
            quality_weights=QualityDimensionWeights(
                static_security=QUALITY_DIMENSION_WEIGHTS["static_security"],
                testing=QUALITY_DIMENSION_WEIGHTS["testing"],
                complexity=QUALITY_DIMENSION_WEIGHTS["complexity"],
                architecture=QUALITY_DIMENSION_WEIGHTS["architecture"],
                duplication=QUALITY_DIMENSION_WEIGHTS["duplication"],
            ),
            base_risk=BASE_RISK,
            risk_thresholds=RiskThresholds(
                critical=RiskRules.RISK_THRESHOLDS["CRITICAL"],
                high=RiskRules.RISK_THRESHOLDS["HIGH"],
                medium=RiskRules.RISK_THRESHOLDS["MEDIUM"],
            ),
            pr_size_thresholds=PRSizeThresholds(
                large_files=PR_SIZE_LARGE_THRESHOLD,
                medium_files=PR_SIZE_MEDIUM_THRESHOLD,
                small_files=PR_SIZE_SMALL_THRESHOLD,
                large_risk=PR_SIZE_LARGE_RISK,
                medium_risk=PR_SIZE_MEDIUM_RISK,
                small_risk=PR_SIZE_SMALL_RISK,
            ),
        )
    
    async def save_configuration(
        self,
        config: RiskConfiguration,
        created_by: str
    ) -> str:
        """
        Save or update risk configuration in database.
        
        Args:
            config: RiskConfiguration to save
            created_by: User who is saving this configuration
        
        Returns:
            Configuration ID (MongoDB _id)
        
        Raises:
            ValueError: If configuration validation fails
        """
        # Validate before saving
        is_valid, errors = config.validate_weights()
        if not is_valid:
            raise ValueError(f"Invalid configuration: {', '.join(errors)}")
        
        configs_col = col("risk_configurations")
        
        # Update metadata
        config.created_by = created_by
        config.updated_at = datetime.now(timezone.utc)
        
        # Check if configuration already exists
        existing = await configs_col.find_one({
            "project_id": config.project_id,
            "is_active": True
        })
        
        if existing:
            # Update existing
            await configs_col.update_one(
                {"_id": existing["_id"]},
                {"$set": config.model_dump(exclude={"id"})}
            )
            config_id = str(existing["_id"])
            logger.info(
                f"Updated risk configuration for project_id={config.project_id} by {created_by}"
            )
        else:
            # Insert new
            result = await configs_col.insert_one(
                config.model_dump(exclude={"id"})
            )
            config_id = str(result.inserted_id)
            logger.info(
                f"Created risk configuration for project_id={config.project_id} by {created_by}"
            )
        
        # Invalidate cache
        if config.project_id in self._cache:
            del self._cache[config.project_id]
        if config.project_id in self._cache_timestamp:
            del self._cache_timestamp[config.project_id]
        
        return config_id
    
    async def list_configurations(
        self,
        project_id: Optional[str] = None,
        include_inactive: bool = False
    ) -> list[RiskConfiguration]:
        """
        List all risk configurations.
        
        Args:
            project_id: Filter by project ID (None = only global)
            include_inactive: Whether to include inactive configs
        
        Returns:
            List of RiskConfiguration objects
        """
        configs_col = col("risk_configurations")
        
        query = {}
        if project_id is not None:
            query["project_id"] = project_id
        if not include_inactive:
            query["is_active"] = True
        
        cursor = configs_col.find(query).sort("updated_at", -1)
        docs = await cursor.to_list(length=100)
        
        return [RiskConfiguration(**doc) for doc in docs]
    
    async def delete_configuration(
        self,
        project_id: Optional[str]
    ) -> bool:
        """
        Soft-delete a risk configuration (set is_active=False).
        
        Args:
            project_id: Project ID of configuration to delete
        
        Returns:
            True if deleted, False if not found
        """
        configs_col = col("risk_configurations")
        
        result = await configs_col.update_one(
            {"project_id": project_id, "is_active": True},
            {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}}
        )
        
        if result.modified_count > 0:
            # Invalidate cache
            if project_id in self._cache:
                del self._cache[project_id]
            if project_id in self._cache_timestamp:
                del self._cache_timestamp[project_id]
            
            logger.info(f"Deleted risk configuration for project_id={project_id}")
            return True
        
        return False
    
    def clear_cache(self, project_id: Optional[str] = None):
        """
        Clear configuration cache.
        
        Args:
            project_id: Specific project to clear, or None to clear all
        """
        if project_id is None:
            self._cache.clear()
            self._cache_timestamp.clear()
            logger.info("Cleared all risk configuration cache")
        else:
            if project_id in self._cache:
                del self._cache[project_id]
            if project_id in self._cache_timestamp:
                del self._cache_timestamp[project_id]
            logger.info(f"Cleared risk configuration cache for project_id={project_id}")


# Singleton instance
_service_instance: Optional[RiskConfigService] = None


def get_risk_config_service() -> RiskConfigService:
    """Get singleton instance of RiskConfigService."""
    global _service_instance
    if _service_instance is None:
        _service_instance = RiskConfigService()
    return _service_instance
