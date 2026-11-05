"""
Period evidence manifest - helper for performance evaluation evidence tracking.

Analyzes developer activity data and determines eligible evaluation dimensions
based on evidence quality, completeness, and volume.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date


# Minimum evidence thresholds for dimension eligibility
EVIDENCE_THRESHOLDS = {
    'code_quality': {'commits': 5, 'pull_requests': 2},
    'collaboration': {'pull_requests': 2, 'code_reviews': 3},
    'delivery': {'completed_tasks': 3, 'completed_stories': 1},
    'reliability': {'completed_tasks': 5},
    'technical_design': {'pull_requests': 3, 'commits': 10},
    'innovation': {'pull_requests': 1},  # Lower threshold for innovation
}


def period_manifest(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyzes developer data and returns a manifest of available evidence dimensions.
    
    Performs evidence quality assessment, completeness validation, and dimension
    eligibility determination based on configurable thresholds.
    
    Args:
        data: Developer performance data for a period containing:
            - commits: List of commit records
            - pull_requests: List of PR records
            - code_reviews: List of code review records
            - completed_tasks: List of completed task records
            - completed_stories: List of completed story records
            - period_start: Start date of evaluation period (optional)
            - period_end: End date of evaluation period (optional)
        
    Returns:
        Dictionary with:
            - eligible_dimensions: List of dimension names with sufficient evidence
            - evidence_counts: Raw counts per evidence type
            - evidence_quality: Quality assessment per evidence type
            - has_sufficient_evidence: Boolean indicating overall sufficiency
            - warnings: List of quality warnings
    """
    # Extract available evidence with counts
    commits = data.get('commits', [])
    pull_requests = data.get('pull_requests', [])
    code_reviews = data.get('code_reviews', [])
    completed_tasks = data.get('completed_tasks', [])
    completed_stories = data.get('completed_stories', [])
    
    evidence_counts = {
        'commits': len(commits),
        'pull_requests': len(pull_requests),
        'code_reviews': len(code_reviews),
        'completed_tasks': len(completed_tasks),
        'completed_stories': len(completed_stories),
    }
    
    # Assess evidence quality
    evidence_quality = _assess_evidence_quality(data)
    
    # Determine eligible dimensions based on thresholds
    eligible_dimensions = []
    dimension_evidence_map = {}
    
    for dimension, requirements in EVIDENCE_THRESHOLDS.items():
        meets_threshold = True
        evidence_sources = []
        
        for evidence_type, min_count in requirements.items():
            actual_count = evidence_counts.get(evidence_type, 0)
            if actual_count >= min_count:
                evidence_sources.append(evidence_type)
            else:
                meets_threshold = False
                break
        
        if meets_threshold:
            eligible_dimensions.append(dimension)
            dimension_evidence_map[dimension] = evidence_sources
    
    # Validate period boundaries
    warnings = []
    period_start = data.get('period_start')
    period_end = data.get('period_end')
    
    if period_start and period_end:
        boundary_warnings = _validate_period_boundaries(
            period_start, period_end, data
        )
        warnings.extend(boundary_warnings)
    
    # Check for data completeness issues
    completeness_warnings = _check_data_completeness(evidence_counts, evidence_quality)
    warnings.extend(completeness_warnings)
    
    return {
        'eligible_dimensions': eligible_dimensions,
        'dimension_evidence_map': dimension_evidence_map,
        'evidence_counts': evidence_counts,
        'evidence_quality': evidence_quality,
        'has_sufficient_evidence': len(eligible_dimensions) > 0,
        'warnings': warnings,
        'period_validated': period_start is not None and period_end is not None
    }


def _assess_evidence_quality(data: Dict[str, Any]) -> Dict[str, str]:
    """
    Assess quality of available evidence.
    
    Returns quality rating (EXCELLENT, GOOD, FAIR, POOR) for each evidence type.
    """
    quality = {}
    
    commits = data.get('commits', [])
    if len(commits) >= 20:
        quality['commits'] = 'EXCELLENT'
    elif len(commits) >= 10:
        quality['commits'] = 'GOOD'
    elif len(commits) >= 5:
        quality['commits'] = 'FAIR'
    else:
        quality['commits'] = 'POOR'
    
    pull_requests = data.get('pull_requests', [])
    if len(pull_requests) >= 10:
        quality['pull_requests'] = 'EXCELLENT'
    elif len(pull_requests) >= 5:
        quality['pull_requests'] = 'GOOD'
    elif len(pull_requests) >= 2:
        quality['pull_requests'] = 'FAIR'
    else:
        quality['pull_requests'] = 'POOR'
    
    code_reviews = data.get('code_reviews', [])
    if len(code_reviews) >= 15:
        quality['code_reviews'] = 'EXCELLENT'
    elif len(code_reviews) >= 8:
        quality['code_reviews'] = 'GOOD'
    elif len(code_reviews) >= 3:
        quality['code_reviews'] = 'FAIR'
    else:
        quality['code_reviews'] = 'POOR'
    
    completed_tasks = data.get('completed_tasks', [])
    if len(completed_tasks) >= 20:
        quality['completed_tasks'] = 'EXCELLENT'
    elif len(completed_tasks) >= 10:
        quality['completed_tasks'] = 'GOOD'
    elif len(completed_tasks) >= 5:
        quality['completed_tasks'] = 'FAIR'
    else:
        quality['completed_tasks'] = 'POOR'
    
    completed_stories = data.get('completed_stories', [])
    if len(completed_stories) >= 8:
        quality['completed_stories'] = 'EXCELLENT'
    elif len(completed_stories) >= 4:
        quality['completed_stories'] = 'GOOD'
    elif len(completed_stories) >= 1:
        quality['completed_stories'] = 'FAIR'
    else:
        quality['completed_stories'] = 'POOR'
    
    return quality


def _validate_period_boundaries(
    period_start: str,
    period_end: str,
    data: Dict[str, Any]
) -> List[str]:
    """
    Validate that evidence falls within period boundaries.
    
    Returns list of warnings if evidence is outside period or period is invalid.
    """
    warnings = []
    
    try:
        start_date = datetime.fromisoformat(period_start.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(period_end.replace('Z', '+00:00'))
        
        if start_date >= end_date:
            warnings.append("Invalid period: start_date is not before end_date")
            return warnings
        
        # Check if commits fall within period
        commits = data.get('commits', [])
        out_of_period_commits = 0
        for commit in commits:
            commit_date_str = commit.get('date') or commit.get('committed_date')
            if commit_date_str:
                try:
                    commit_date = datetime.fromisoformat(commit_date_str.replace('Z', '+00:00'))
                    if commit_date < start_date or commit_date > end_date:
                        out_of_period_commits += 1
                except (ValueError, AttributeError):
                    pass
        
        if out_of_period_commits > 0:
            warnings.append(
                f"{out_of_period_commits} commits fall outside evaluation period"
            )
        
        # Similar validation for PRs
        pull_requests = data.get('pull_requests', [])
        out_of_period_prs = 0
        for pr in pull_requests:
            pr_date_str = pr.get('merged_at') or pr.get('created_at')
            if pr_date_str:
                try:
                    pr_date = datetime.fromisoformat(pr_date_str.replace('Z', '+00:00'))
                    if pr_date < start_date or pr_date > end_date:
                        out_of_period_prs += 1
                except (ValueError, AttributeError):
                    pass
        
        if out_of_period_prs > 0:
            warnings.append(
                f"{out_of_period_prs} pull requests fall outside evaluation period"
            )
    
    except (ValueError, AttributeError) as e:
        warnings.append(f"Period date parsing error: {str(e)}")
    
    return warnings


def _check_data_completeness(
    evidence_counts: Dict[str, int],
    evidence_quality: Dict[str, str]
) -> List[str]:
    """
    Check for data completeness issues that might affect evaluation quality.
    
    Returns list of warnings about missing or insufficient evidence.
    """
    warnings = []
    
    # Check for completely missing evidence types
    if evidence_counts.get('commits', 0) == 0:
        warnings.append("No commit data available - code quality assessment limited")
    
    if evidence_counts.get('pull_requests', 0) == 0:
        warnings.append("No pull request data - collaboration and design assessment limited")
    
    if evidence_counts.get('code_reviews', 0) == 0:
        warnings.append("No code review data - collaboration assessment limited")
    
    if evidence_counts.get('completed_tasks', 0) == 0 and evidence_counts.get('completed_stories', 0) == 0:
        warnings.append("No task or story completion data - delivery assessment limited")
    
    # Check for low-quality evidence
    poor_quality_types = [
        evidence_type for evidence_type, quality in evidence_quality.items()
        if quality == 'POOR'
    ]
    
    if poor_quality_types:
        warnings.append(
            f"Low evidence volume for: {', '.join(poor_quality_types)}"
        )
    
    return warnings
