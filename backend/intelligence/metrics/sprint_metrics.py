"""
Sprint metrics calculator.
Analyzes sprint progress, velocity, and delivery predictability.
This is the core of "Plan vs Reality" intelligence.
NO LLM - pure data analysis.
"""

from typing import Optional


class SprintMetrics:
    """Calculate sprint and delivery-related metrics."""

    @staticmethod
    def calculate_velocity(
        completed_points: int,
        sprint_duration_days: int,
    ) -> float:
        """
        Calculate sprint velocity (points per day).
        
        Returns:
            Velocity as points/day
        """
        if sprint_duration_days == 0:
            return 0.0
        return completed_points / sprint_duration_days

    @staticmethod
    def calculate_sprint_progress(
        total_stories: int,
        completed_stories: int,
        in_progress_stories: int,
        blocked_stories: int,
        total_points: int,
        completed_points: int,
        days_elapsed: int,
        sprint_duration_days: int,
    ) -> dict:
        """
        Comprehensive sprint progress analysis.
        This is the "Plan vs Reality" core calculation.
        
        Returns:
            Detailed progress metrics and risk assessment
        """
        # Completion percentages
        story_completion_pct = (completed_stories / max(total_stories, 1)) * 100
        points_completion_pct = (completed_points / max(total_points, 1)) * 100
        time_elapsed_pct = (days_elapsed / max(sprint_duration_days, 1)) * 100
        
        # Expected progress (linear burndown assumption)
        expected_completion_pct = time_elapsed_pct
        
        # Progress variance
        progress_variance = points_completion_pct - expected_completion_pct
        
        risk_score = 0
        risk_factors = []
        
        # Behind schedule
        if progress_variance < -30:
            risk_score += 50
            risk_factors.append(f"Significantly behind schedule: {abs(progress_variance):.1f}% behind")
        elif progress_variance < -15:
            risk_score += 30
            risk_factors.append(f"Behind schedule: {abs(progress_variance):.1f}% behind")
        elif progress_variance < -5:
            risk_score += 15
            risk_factors.append(f"Slightly behind schedule: {abs(progress_variance):.1f}% behind")
        
        # Blocked stories
        if blocked_stories > 0:
            blocked_pct = (blocked_stories / max(total_stories, 1)) * 100
            risk_score += blocked_stories * 15
            risk_factors.append(f"{blocked_stories} stories blocked ({blocked_pct:.1f}%)")
        
        # Too much WIP
        if in_progress_stories > 5:
            risk_score += 15
            risk_factors.append(f"High WIP: {in_progress_stories} stories in progress")
        elif in_progress_stories > 3:
            risk_score += 5
            risk_factors.append(f"Moderate WIP: {in_progress_stories} stories in progress")
        
        # Calculate projected completion
        if days_elapsed > 0:
            current_velocity = completed_points / days_elapsed
            days_remaining = sprint_duration_days - days_elapsed
            projected_total_points = completed_points + (current_velocity * days_remaining)
            projected_completion_pct = (projected_total_points / max(total_points, 1)) * 100
        else:
            projected_completion_pct = 0.0
        
        # Unlikely to complete
        if projected_completion_pct < 70:
            risk_score += 35
            risk_factors.append(f"Unlikely to complete sprint goal: {projected_completion_pct:.1f}% projected")
        elif projected_completion_pct < 85:
            risk_score += 20
            risk_factors.append(f"At risk of incomplete sprint: {projected_completion_pct:.1f}% projected")
        
        risk_level = "CRITICAL" if risk_score >= 70 else \
                     "HIGH" if risk_score >= 50 else \
                     "MEDIUM" if risk_score >= 30 else "LOW"
        
        return {
            "total_stories": total_stories,
            "completed_stories": completed_stories,
            "in_progress_stories": in_progress_stories,
            "blocked_stories": blocked_stories,
            "total_points": total_points,
            "completed_points": completed_points,
            "story_completion_pct": round(story_completion_pct, 2),
            "points_completion_pct": round(points_completion_pct, 2),
            "time_elapsed_pct": round(time_elapsed_pct, 2),
            "expected_completion_pct": round(expected_completion_pct, 2),
            "progress_variance": round(progress_variance, 2),
            "projected_completion_pct": round(projected_completion_pct, 2),
            "risk_score": min(risk_score, 100),
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "data_quality": "complete",
        }

    @staticmethod
    def calculate_scope_creep(
        original_points: int,
        current_points: int,
        added_stories: int = 0,
    ) -> dict:
        """
        Detect sprint scope creep.
        
        Adding work mid-sprint increases delivery risk.
        """
        scope_change = current_points - original_points
        scope_change_pct = (scope_change / max(original_points, 1)) * 100
        
        risk_score = 0
        risk_factors = []
        
        if scope_change_pct > 20:
            risk_score += 40
            risk_factors.append(f"Significant scope creep: +{scope_change_pct:.1f}%")
        elif scope_change_pct > 10:
            risk_score += 25
            risk_factors.append(f"Moderate scope creep: +{scope_change_pct:.1f}%")
        elif scope_change_pct > 5:
            risk_score += 10
            risk_factors.append(f"Minor scope creep: +{scope_change_pct:.1f}%")
        
        if added_stories > 0:
            risk_factors.append(f"{added_stories} stories added mid-sprint")
        
        return {
            "original_points": original_points,
            "current_points": current_points,
            "scope_change": scope_change,
            "scope_change_pct": round(scope_change_pct, 2),
            "added_stories": added_stories,
            "risk_score": min(risk_score, 100),
            "risk_factors": risk_factors,
            "data_quality": "complete",
        }

    @staticmethod
    def calculate_velocity_trend(
        current_velocity: float,
        previous_sprint_velocity: Optional[float],
        team_avg_velocity: Optional[float] = None,
    ) -> dict:
        """
        Analyze velocity trends and consistency.
        
        Declining velocity may indicate technical debt or team issues.
        """
        risk_score = 0
        risk_factors = []
        
        if previous_sprint_velocity:
            velocity_change = current_velocity - previous_sprint_velocity
            velocity_change_pct = (velocity_change / max(previous_sprint_velocity, 0.1)) * 100
            
            if velocity_change_pct < -20:
                risk_score += 30
                risk_factors.append(f"Velocity declined significantly: {velocity_change_pct:.1f}%")
            elif velocity_change_pct < -10:
                risk_score += 15
                risk_factors.append(f"Velocity declined: {velocity_change_pct:.1f}%")
        else:
            velocity_change_pct = None
        
        if team_avg_velocity and current_velocity < (team_avg_velocity * 0.7):
            risk_score += 20
            risk_factors.append(f"Below team average velocity: {current_velocity:.1f} vs {team_avg_velocity:.1f}")
        
        return {
            "current_velocity": round(current_velocity, 2),
            "previous_velocity": previous_sprint_velocity,
            "velocity_change_pct": round(velocity_change_pct, 2) if velocity_change_pct else None,
            "team_avg_velocity": team_avg_velocity,
            "risk_score": min(risk_score, 100),
            "risk_factors": risk_factors,
            "data_quality": "complete" if previous_sprint_velocity else "partial",
        }
