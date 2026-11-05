"""
Period evidence manifest - helper for performance evaluation evidence tracking.
Temporary stub to allow server startup.
"""

from typing import Dict, Any, List


def period_manifest(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyzes developer data and returns a manifest of available evidence dimensions.
    
    Args:
        data: Developer performance data for a period
        
    Returns:
        Dictionary with eligible_dimensions and evidence_counts
    """
    # Extract available evidence types
    has_commits = bool(data.get('commits'))
    has_prs = bool(data.get('pull_requests'))
    has_reviews = bool(data.get('code_reviews'))
    has_tasks = bool(data.get('completed_tasks'))
    has_stories = bool(data.get('completed_stories'))
    
    # Determine eligible evaluation dimensions based on available evidence
    eligible_dimensions = []
    
    if has_commits or has_prs:
        eligible_dimensions.append('code_quality')
    
    if has_prs or has_reviews:
        eligible_dimensions.append('collaboration')
    
    if has_tasks or has_stories:
        eligible_dimensions.extend(['delivery', 'reliability'])
    
    if has_prs:
        eligible_dimensions.append('technical_design')
    
    # Build evidence counts
    evidence_counts = {
        'commits': len(data.get('commits', [])),
        'pull_requests': len(data.get('pull_requests', [])),
        'code_reviews': len(data.get('code_reviews', [])),
        'completed_tasks': len(data.get('completed_tasks', [])),
        'completed_stories': len(data.get('completed_stories', [])),
    }
    
    return {
        'eligible_dimensions': eligible_dimensions,
        'evidence_counts': evidence_counts,
        'has_sufficient_evidence': len(eligible_dimensions) > 0
    }
