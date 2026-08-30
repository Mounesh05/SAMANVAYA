"""
Historical Analyzer
Tracks previous failures, bug patterns, and risk areas based on git/database history.
"""

from typing import Dict, Any, List
from pathlib import Path
from core.database import db


class HistoricalAnalyzer:
    """
    Analyzes historical data to identify risk patterns.
    """
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
    
    async def analyze_history(
        self,
        changed_files: List[str],
        project_id: str
    ) -> Dict[str, Any]:
        """
        Analyze historical incidents for changed files.
        """
        result = {
            "high_risk_files": [],
            "previous_incidents": 0,
            "bug_prone_modules": [],
            "frequently_changed_files": [],
        }
        
        # Query database for historical issues
        for file_path in changed_files[:10]:  # Limit to avoid performance issues
            incidents = await self._get_file_incidents(file_path, project_id)
            
            if incidents > 0:
                result["high_risk_files"].append({
                    "file": file_path,
                    "incidents": incidents,
                })
                result["previous_incidents"] += incidents
        
        return result
    
    async def _get_file_incidents(self, file_path: str, project_id: str) -> int:
        """Query database for previous incidents involving this file."""
        # Placeholder - would query MongoDB for bug reports, failed builds, etc.
        return 0
    
    def get_history_summary(self, result: Dict[str, Any]) -> str:
        """Generate summary."""
        if result["previous_incidents"] == 0:
            return "No historical incidents in modified files"
        
        parts = [f"⚠️ {result['previous_incidents']} previous incidents in modified files"]
        
        for file_info in result["high_risk_files"][:3]:
            parts.append(f"  - {file_info['file']}: {file_info['incidents']} incidents")
        
        return "\n".join(parts)
