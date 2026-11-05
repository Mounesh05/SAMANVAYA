"""
Evaluation scoring constants and utilities for performance evaluations.

Provides dimension scoring logic, rubric enforcement, and score aggregation
for AI-powered performance evaluations.
"""

from typing import Dict, Any, List, Optional
from enum import Enum


# Dimension weights for performance evaluation
DIMENSION_WEIGHTS = {
    'code_quality': 0.25,
    'delivery': 0.20,
    'collaboration': 0.20,
    'technical_design': 0.15,
    'reliability': 0.10,
    'innovation': 0.10
}

# Rubric version for evaluation consistency
RUBRIC_VERSION = "1.0.0"


class PerformanceRating(str, Enum):
    """Standard performance rating levels."""
    EXCEPTIONAL = "EXCEPTIONAL"  # 4.5 - 5.0
    EXCEEDS_EXPECTATIONS = "EXCEEDS_EXPECTATIONS"  # 3.5 - 4.4
    MEETS_EXPECTATIONS = "MEETS_EXPECTATIONS"  # 2.5 - 3.4
    NEEDS_IMPROVEMENT = "NEEDS_IMPROVEMENT"  # 1.5 - 2.4
    UNSATISFACTORY = "UNSATISFACTORY"  # 0.0 - 1.4


# Score ranges for each rating level
RATING_THRESHOLDS = {
    PerformanceRating.EXCEPTIONAL: (4.5, 5.0),
    PerformanceRating.EXCEEDS_EXPECTATIONS: (3.5, 4.5),
    PerformanceRating.MEETS_EXPECTATIONS: (2.5, 3.5),
    PerformanceRating.NEEDS_IMPROVEMENT: (1.5, 2.5),
    PerformanceRating.UNSATISFACTORY: (0.0, 1.5),
}


def calculate_overall_score(dimension_scores: Dict[str, float]) -> float:
    """
    Calculate weighted overall performance score from dimension scores.
    
    Args:
        dimension_scores: Dictionary mapping dimension name to score (0-5)
        
    Returns:
        Weighted overall score (0-5)
    """
    if not dimension_scores:
        return 0.0
    
    weighted_sum = 0.0
    total_weight = 0.0
    
    for dimension, score in dimension_scores.items():
        weight = DIMENSION_WEIGHTS.get(dimension, 0.0)
        weighted_sum += score * weight
        total_weight += weight
    
    # Normalize if not all dimensions present
    if total_weight > 0:
        return round(weighted_sum / total_weight, 2)
    
    return 0.0


def get_rating_from_score(score: float) -> PerformanceRating:
    """
    Convert numeric score to performance rating level.
    
    Args:
        score: Overall score (0-5)
        
    Returns:
        Performance rating enum value
    """
    for rating, (min_score, max_score) in RATING_THRESHOLDS.items():
        if min_score <= score < max_score:
            return rating
    
    # Edge case: score exactly 5.0
    if score >= 5.0:
        return PerformanceRating.EXCEPTIONAL
    
    # Edge case: negative or invalid scores
    return PerformanceRating.UNSATISFACTORY


def validate_dimension_score(dimension: str, score: float) -> bool:
    """
    Validate that a dimension score is within acceptable range.
    
    Args:
        dimension: Dimension name
        score: Score value
        
    Returns:
        True if valid, False otherwise
    """
    # Check dimension exists
    if dimension not in DIMENSION_WEIGHTS:
        return False
    
    # Check score range
    if not (0.0 <= score <= 5.0):
        return False
    
    return True


def normalize_dimension_scores(dimension_scores: Dict[str, float]) -> Dict[str, float]:
    """
    Normalize dimension scores to ensure they're in valid range (0-5).
    
    Clamps out-of-range values and filters invalid dimensions.
    
    Args:
        dimension_scores: Raw dimension scores
        
    Returns:
        Normalized dimension scores
    """
    normalized = {}
    
    for dimension, score in dimension_scores.items():
        # Skip unknown dimensions
        if dimension not in DIMENSION_WEIGHTS:
            continue
        
        # Clamp to 0-5 range
        clamped_score = max(0.0, min(5.0, score))
        normalized[dimension] = round(clamped_score, 2)
    
    return normalized


def calculate_dimension_percentile(score: float, all_scores: List[float]) -> float:
    """
    Calculate percentile rank of a dimension score relative to all scores.
    
    Args:
        score: Individual score
        all_scores: List of all scores for comparison
        
    Returns:
        Percentile (0-100)
    """
    if not all_scores:
        return 50.0  # Default to median if no comparison data
    
    scores_below = sum(1 for s in all_scores if s < score)
    percentile = (scores_below / len(all_scores)) * 100
    
    return round(percentile, 1)


def get_improvement_recommendations(
    dimension_scores: Dict[str, float],
    threshold: float = 3.0
) -> List[str]:
    """
    Generate improvement recommendations for dimensions scoring below threshold.
    
    Args:
        dimension_scores: Evaluated dimension scores
        threshold: Minimum acceptable score (default: 3.0 = meets expectations)
        
    Returns:
        List of improvement recommendation messages
    """
    recommendations = []
    
    dimension_descriptions = {
        'code_quality': 'code quality practices, testing, and maintainability',
        'delivery': 'on-time delivery and task completion consistency',
        'collaboration': 'peer collaboration, code reviews, and knowledge sharing',
        'technical_design': 'system design decisions and architectural thinking',
        'reliability': 'bug resolution, system stability, and incident response',
        'innovation': 'creative problem-solving and adoption of new technologies',
    }
    
    for dimension, score in dimension_scores.items():
        if score < threshold:
            description = dimension_descriptions.get(dimension, dimension)
            recommendations.append(
                f"Focus on improving {description} (current score: {score:.1f}/5.0)"
            )
    
    return recommendations


def aggregate_multi_period_scores(
    period_scores: List[Dict[str, Any]],
    method: str = 'weighted_recent'
) -> Dict[str, float]:
    """
    Aggregate scores across multiple evaluation periods.
    
    Args:
        period_scores: List of period evaluation results, each containing dimension_scores
        method: Aggregation method ('weighted_recent', 'average', 'latest')
        
    Returns:
        Aggregated dimension scores
    """
    if not period_scores:
        return {}
    
    if method == 'latest':
        # Return most recent period scores
        return period_scores[-1].get('dimension_scores', {})
    
    if method == 'average':
        # Simple average across all periods
        dimension_sums = {}
        dimension_counts = {}
        
        for period in period_scores:
            for dimension, score in period.get('dimension_scores', {}).items():
                dimension_sums[dimension] = dimension_sums.get(dimension, 0) + score
                dimension_counts[dimension] = dimension_counts.get(dimension, 0) + 1
        
        return {
            dim: round(dimension_sums[dim] / dimension_counts[dim], 2)
            for dim in dimension_sums
        }
    
    if method == 'weighted_recent':
        # Weight recent periods more heavily
        dimension_weighted_sums = {}
        dimension_total_weights = {}
        
        num_periods = len(period_scores)
        for idx, period in enumerate(period_scores):
            # Linear weighting: most recent period has highest weight
            weight = (idx + 1) / num_periods
            
            for dimension, score in period.get('dimension_scores', {}).items():
                dimension_weighted_sums[dimension] = (
                    dimension_weighted_sums.get(dimension, 0) + score * weight
                )
                dimension_total_weights[dimension] = (
                    dimension_total_weights.get(dimension, 0) + weight
                )
        
        return {
            dim: round(dimension_weighted_sums[dim] / dimension_total_weights[dim], 2)
            for dim in dimension_weighted_sums
        }
    
    # Default to average
    return aggregate_multi_period_scores(period_scores, method='average')


def calculate_trend(
    historical_scores: List[float],
    periods: int = 3
) -> str:
    """
    Calculate performance trend from historical scores.
    
    Args:
        historical_scores: List of historical overall scores (chronological)
        periods: Number of recent periods to analyze
        
    Returns:
        Trend description ('IMPROVING', 'STABLE', 'DECLINING', 'INSUFFICIENT_DATA')
    """
    if len(historical_scores) < 2:
        return 'INSUFFICIENT_DATA'
    
    # Use only recent periods
    recent_scores = historical_scores[-periods:] if len(historical_scores) >= periods else historical_scores
    
    if len(recent_scores) < 2:
        return 'INSUFFICIENT_DATA'
    
    # Calculate average change
    changes = [recent_scores[i] - recent_scores[i-1] for i in range(1, len(recent_scores))]
    avg_change = sum(changes) / len(changes)
    
    # Determine trend based on average change
    if avg_change > 0.2:
        return 'IMPROVING'
    elif avg_change < -0.2:
        return 'DECLINING'
    else:
        return 'STABLE'
