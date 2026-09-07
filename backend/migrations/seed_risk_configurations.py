#!/usr/bin/env python3
"""
Migration script to seed default risk configurations into MongoDB.

This seeds the global default configuration using the current hardcoded values
from intelligence/rules/risk_rules.py.

Run this after deploying the configurable risk system to production.

Usage:
    python -m migrations.seed_risk_configurations
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import col, get_db_client, close_db
from domain.models.risk_configuration import (
    RiskConfiguration,
    RiskDimensionWeights,
    QualityDimensionWeights,
    RiskThresholds,
    PRSizeThresholds,
)
from intelligence.rules.risk_rules import (
    QUALITY_DIMENSION_WEIGHTS,
    RiskRules,
    PR_SIZE_LARGE_THRESHOLD,
    PR_SIZE_MEDIUM_THRESHOLD,
    PR_SIZE_SMALL_THRESHOLD,
    PR_SIZE_LARGE_RISK,
    PR_SIZE_MEDIUM_RISK,
    PR_SIZE_SMALL_RISK,
)


async def seed_global_default():
    """Seed the global default risk configuration."""
    configs_col = col("risk_configurations")
    
    # Check if global default already exists
    existing = await configs_col.find_one({"project_id": None, "is_active": True})
    if existing:
        print("✓ Global default configuration already exists")
        print(f"  ID: {existing['_id']}")
        print(f"  Name: {existing.get('name')}")
        print(f"  Created by: {existing.get('created_by')}")
        print("\nSkipping seed (delete existing config first if you want to re-seed)")
        return False
    
    # Create global default configuration
    config = RiskConfiguration(
        project_id=None,  # Global default
        name="Global Default Configuration",
        created_by="system_migration",
        risk_weights=RiskDimensionWeights(
            # Omitting legacy Z-score fields for schema compatibility
            # alpha_size_zscore defaults to 12.0, zeta_complexity to 10.0
            beta_hotspot=20.0,
            gamma_dependency=15.0,
            delta_missing_tests=18.0,
            epsilon_security=25.0,
        ),
        quality_weights=QualityDimensionWeights(
            static_security=QUALITY_DIMENSION_WEIGHTS["static_security"],
            testing=QUALITY_DIMENSION_WEIGHTS["testing"],
            complexity=QUALITY_DIMENSION_WEIGHTS["complexity"],
            architecture=QUALITY_DIMENSION_WEIGHTS["architecture"],
            duplication=QUALITY_DIMENSION_WEIGHTS["duplication"],
        ),
        base_risk=10.0,  # Default base risk
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
    
    # Validate before inserting
    is_valid, errors = config.validate_weights()
    if not is_valid:
        print(f"✗ Configuration validation failed: {errors}")
        return False
    
    # Insert into database
    result = await configs_col.insert_one(config.model_dump(exclude={"id"}))
    config_id = str(result.inserted_id)
    
    print("✓ Successfully seeded global default configuration")
    print(f"  ID: {config_id}")
    print(f"  Risk weights sum: {config.risk_weights.sum()}")
    print(f"  Quality weights sum: {config.quality_weights.sum()}")
    
    return True


async def seed_example_project_configs():
    """Seed example project-specific configurations (optional)."""
    configs_col = col("risk_configurations")
    
    examples = [
        {
            "project_id": "EXAMPLE-HIGH-SECURITY",
            "name": "High Security Project",
            "risk_weights": RiskDimensionWeights(
                alpha_size_zscore=10.0,
                beta_hotspot=18.0,
                gamma_dependency=12.0,
                delta_missing_tests=15.0,
                epsilon_security=35.0,  # Higher security weight
                zeta_complexity=10.0,
            ),
            "quality_weights": QualityDimensionWeights(
                static_security=0.35,  # Higher security weight
                testing=0.25,
                complexity=0.15,
                architecture=0.15,
                duplication=0.10,
            ),
        },
        {
            "project_id": "EXAMPLE-LEGACY",
            "name": "Legacy Code Project",
            "risk_weights": RiskDimensionWeights(
                alpha_size_zscore=15.0,  # Size matters more
                beta_hotspot=25.0,       # Hotspots critical
                gamma_dependency=10.0,
                delta_missing_tests=20.0,
                epsilon_security=20.0,
                zeta_complexity=10.0,
            ),
            "quality_weights": QualityDimensionWeights(
                static_security=0.20,
                testing=0.30,  # Testing critical for legacy
                complexity=0.25,  # Complexity matters
                architecture=0.15,
                duplication=0.10,
            ),
        },
    ]
    
    print("\n━━━ Seeding example project configurations ━━━")
    seeded_count = 0
    
    for example in examples:
        # Check if already exists
        existing = await configs_col.find_one({
            "project_id": example["project_id"],
            "is_active": True
        })
        if existing:
            print(f"✓ {example['name']} already exists, skipping")
            continue
        
        config = RiskConfiguration(
            project_id=example["project_id"],
            name=example["name"],
            created_by="system_migration",
            risk_weights=example["risk_weights"],
            quality_weights=example["quality_weights"],
            base_risk=BASE_RISK,
            risk_thresholds=RiskThresholds(),
            pr_size_thresholds=PRSizeThresholds(),
        )
        
        # Validate
        is_valid, errors = config.validate_weights()
        if not is_valid:
            print(f"✗ {example['name']} validation failed: {errors}")
            continue
        
        # Insert
        result = await configs_col.insert_one(config.model_dump(exclude={"id"}))
        print(f"✓ Seeded: {example['name']} (ID: {result.inserted_id})")
        seeded_count += 1
    
    print(f"\nSeeded {seeded_count} example project configurations")
    return seeded_count > 0


async def main():
    """Main migration function."""
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Seeding Risk Configurations")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
    
    try:
        # Connect to database
        await get_db_client()
        print("✓ Connected to MongoDB\n")
        
        # Seed global default
        print("━━━ Seeding global default configuration ━━━")
        await seed_global_default()
        
        # Seed example project configs
        await seed_example_project_configs()
        
        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("  Migration Complete!")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("\nYou can now:")
        print("  • View configs: GET /api/risk-configurations/")
        print("  • Get global: GET /api/risk-configurations/global")
        print("  • Update via API or directly in MongoDB")
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        await close_db()
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
