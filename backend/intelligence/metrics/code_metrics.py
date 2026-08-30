"""
Code metrics calculator.
Analyzes code changes for complexity, size, and impact.
NO LLM - pure rule-based analysis.
"""

from typing import Optional


class CodeMetrics:
    """Calculate code-related metrics for PRs and commits."""

    @staticmethod
    def calculate_change_size(files_changed: int, lines_added: int, lines_deleted: int) -> dict:
        """
        Calculate change size metrics.
        
        Returns risk score based on size of changes.
        Large changes are inherently riskier.
        """
        total_lines_changed = lines_added + lines_deleted
        
        # Risk scoring based on size
        risk_score = 0
        risk_factors = []
        
        # Files changed risk
        if files_changed > 20:
            risk_score += 30
            risk_factors.append(f"Very large change: {files_changed} files")
        elif files_changed > 10:
            risk_score += 20
            risk_factors.append(f"Large change: {files_changed} files")
        elif files_changed > 5:
            risk_score += 10
            risk_factors.append(f"Moderate change: {files_changed} files")
        
        # Lines changed risk
        if total_lines_changed > 1000:
            risk_score += 25
            risk_factors.append(f"Very large diff: {total_lines_changed} lines")
        elif total_lines_changed > 500:
            risk_score += 15
            risk_factors.append(f"Large diff: {total_lines_changed} lines")
        elif total_lines_changed > 200:
            risk_score += 5
            risk_factors.append(f"Moderate diff: {total_lines_changed} lines")
        
        return {
            "files_changed": files_changed,
            "lines_added": lines_added,
            "lines_deleted": lines_deleted,
            "total_lines_changed": total_lines_changed,
            "risk_score": min(risk_score, 100),
            "risk_factors": risk_factors,
        }

    @staticmethod
    def analyze_file_types(changed_files: list[str]) -> dict:
        """
        Analyze types of files changed and their risk implications.
        
        Args:
            changed_files: List of file paths
        
        Returns:
            Analysis of file types and associated risk
        """
        high_risk_patterns = {
            "auth": ["auth", "login", "password", "token", "session"],
            "database": ["migration", "schema", "model", "database"],
            "config": ["config", "settings", ".env", "secrets"],
            "security": ["security", "permission", "access", "role"],
            "payment": ["payment", "billing", "transaction", "checkout"],
        }
        
        risk_score = 0
        risk_factors = []
        file_types = {"code": 0, "test": 0, "config": 0, "docs": 0}
        high_risk_areas = []
        
        for file_path in changed_files:
            lower_path = file_path.lower()
            
            # Categorize file type
            if any(ext in lower_path for ext in [".test.", "_test.", ".spec."]):
                file_types["test"] += 1
            elif any(ext in lower_path for ext in [".md", ".txt", ".rst"]):
                file_types["docs"] += 1
            elif any(ext in lower_path for ext in [".yml", ".yaml", ".json", ".toml", ".ini"]):
                file_types["config"] += 1
            else:
                file_types["code"] += 1
            
            # Check for high-risk areas
            for area, patterns in high_risk_patterns.items():
                if any(pattern in lower_path for pattern in patterns):
                    if area not in high_risk_areas:
                        high_risk_areas.append(area)
                        risk_score += 20
                        risk_factors.append(f"High-risk area modified: {area}")
        
        # Test coverage concern
        if file_types["code"] > 0 and file_types["test"] == 0:
            risk_score += 15
            risk_factors.append("Code changed without test modifications")
        
        return {
            "file_types": file_types,
            "high_risk_areas": high_risk_areas,
            "risk_score": min(risk_score, 100),
            "risk_factors": risk_factors,
        }

    @staticmethod
    def calculate_commit_frequency(commit_count: int, pr_age_hours: Optional[float] = None) -> dict:
        """
        Analyze commit patterns.
        
        Too many commits might indicate thrashing/uncertainty.
        Too few commits in old PR might indicate stale code.
        """
        risk_score = 0
        risk_factors = []
        
        if commit_count > 20:
            risk_score += 15
            risk_factors.append(f"Excessive commits: {commit_count}")
        elif commit_count == 1:
            risk_factors.append("Single commit (good practice)")
        
        if pr_age_hours and pr_age_hours > 168:  # 7 days
            risk_score += 20
            risk_factors.append(f"Stale PR: {int(pr_age_hours / 24)} days old")
        
        return {
            "commit_count": commit_count,
            "pr_age_hours": pr_age_hours,
            "risk_score": min(risk_score, 100),
            "risk_factors": risk_factors,
        }

    @staticmethod
    def calculate_pr_risk(
        files_changed: int,
        lines_added: int,
        lines_deleted: int,
        changed_files: list[str],
        commit_count: int,
        pr_age_hours: Optional[float] = None,
    ) -> dict:
        """
        Comprehensive PR risk calculation combining all code metrics.
        
        This is the main entry point for PR analysis.
        """
        change_size = CodeMetrics.calculate_change_size(files_changed, lines_added, lines_deleted)
        file_analysis = CodeMetrics.analyze_file_types(changed_files)
        commit_analysis = CodeMetrics.calculate_commit_frequency(commit_count, pr_age_hours)
        
        # Combine risk scores
        total_risk = (
            change_size["risk_score"] +
            file_analysis["risk_score"] +
            commit_analysis["risk_score"]
        )
        
        # Combine risk factors
        all_factors = (
            change_size["risk_factors"] +
            file_analysis["risk_factors"] +
            commit_analysis["risk_factors"]
        )
        
        # Classify risk level
        if total_risk >= 70:
            risk_level = "CRITICAL"
        elif total_risk >= 50:
            risk_level = "HIGH"
        elif total_risk >= 30:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return {
            "total_risk_score": min(total_risk, 100),
            "risk_level": risk_level,
            "risk_factors": all_factors,
            "metrics": {
                "change_size": change_size,
                "file_analysis": file_analysis,
                "commit_analysis": commit_analysis,
            },
        }
