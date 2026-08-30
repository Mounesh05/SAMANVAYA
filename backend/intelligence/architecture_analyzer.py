"""
Architecture Analyzer
Detects violations of layered architecture and design patterns.
"""

from typing import Dict, Any, List
from pathlib import Path
import re


class ArchitectureAnalyzer:
    """
    Analyzes architectural patterns and violations.
    """
    
    # Expected architecture layers
    LAYERS = {
        "api": ["routes", "controllers"],
        "domain": ["models", "services"],
        "repository": ["repositories", "data"],
        "infrastructure": ["integrations", "external"],
    }
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
    
    async def analyze_architecture(
        self,
        changed_files: List[str]
    ) -> Dict[str, Any]:
        """
        Analyze architectural compliance.
        """
        result = {
            "violations": [],
            "layer_mixing": 0,
            "circular_dependencies": 0,
            "affected_layers": set(),
        }
        
        for file_path in changed_files:
            layer = self._identify_layer(file_path)
            if layer:
                result["affected_layers"].add(layer)
            
            # Check for violations (simplified)
            if "api" in file_path and "database" in file_path.lower():
                result["violations"].append({
                    "file": file_path,
                    "issue": "API layer directly accessing database",
                })
                result["layer_mixing"] += 1
        
        result["affected_layers"] = list(result["affected_layers"])
        
        return result
    
    def _identify_layer(self, file_path: str) -> str:
        """Identify which architectural layer a file belongs to."""
        for layer, patterns in self.LAYERS.items():
            if any(pattern in file_path for pattern in patterns):
                return layer
        return "unknown"
    
    def get_architecture_summary(self, result: Dict[str, Any]) -> str:
        """Generate summary."""
        if not result["violations"]:
            return "No architectural violations detected"
        
        parts = [f"⚠️ {len(result['violations'])} architectural violations"]
        
        for violation in result["violations"][:3]:
            parts.append(f"  - {violation['file']}: {violation['issue']}")
        
        return "\n".join(parts)
