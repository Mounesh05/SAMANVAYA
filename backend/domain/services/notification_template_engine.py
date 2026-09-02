"""
Notification Template System - Phase 1.4

Provides rich, role-aware notification templates with customization.
"""

from typing import Dict, Any, List, Optional
from enum import Enum


class NotificationTemplate(str, Enum):
    """Predefined notification templates."""
    PR_HIGH_RISK = "pr_high_risk"
    PR_OPENED = "pr_opened"
    PR_REVIEW_RECEIVED = "pr_review_received"
    PR_RISK_FEEDBACK = "pr_risk_feedback"
    RECOMMENDATION_NEW = "recommendation_new"
    RECOMMENDATION_URGENT = "recommendation_urgent"
    DIRECT_PUSH_MAIN = "direct_push_main"
    DEPLOYMENT_FAILED = "deployment_failed"
    CI_FAILURE = "ci_failure"
    TASK_ASSIGNED = "task_assigned"
    SPRINT_AT_RISK = "sprint_at_risk"


class NotificationChannel(str, Enum):
    """Notification delivery channels."""
    IN_APP = "in_app"


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    URGENT = "urgent"      # Immediate attention
    HIGH = "high"          # Important, address soon
    NORMAL = "normal"      # Standard notification
    LOW = "low"            # Informational


class NotificationTemplateEngine:
    """Renders notification templates with context data."""
    
    # Template definitions with role-specific variations
    TEMPLATES = {
        NotificationTemplate.PR_HIGH_RISK: {
            "developer": {
                "title": "⚠️ Your PR #{pr_number} has {risk_level} risk",
                "body": "Risk score: {risk_score}/100\n\n{top_issue}\n\nAction needed: {primary_recommendation}",
                "priority": NotificationPriority.HIGH,
                "channels": [NotificationChannel.IN_APP],
                "include_recommendations": True
            },
            "tech_lead": {
                "title": "🔴 High Risk PR #{pr_number} requires review",
                "body": "{author} opened a {risk_level} risk PR\n\nRisk factors:\n{risk_factors}\n\nRecommendation: Assign senior reviewer",
                "priority": NotificationPriority.URGENT,
                "channels": [NotificationChannel.IN_APP],
                "include_recommendations": True
            }
        },
        
        NotificationTemplate.PR_OPENED: {
            "tech_lead": {
                "title": "New PR #{pr_number}: {pr_title}",
                "body": "{risk_emoji} {risk_level} risk | {author} | {files_changed} files changed",
                "priority": NotificationPriority.NORMAL,
                "channels": [NotificationChannel.IN_APP],
                "include_recommendations": False
            }
        },
        
        NotificationTemplate.RECOMMENDATION_URGENT: {
            "developer": {
                "title": "🚨 Urgent: {recommendation_title}",
                "body": "{recommendation_description}\n\nAction: {recommendation_action}\n\nImpact: {estimated_impact}",
                "priority": NotificationPriority.URGENT,
                "channels": [NotificationChannel.IN_APP],
                "include_recommendations": False
            }
        },
        
        NotificationTemplate.DIRECT_PUSH_MAIN: {
            "tech_lead": {
                "title": "⚠️ Direct push to {branch}",
                "body": "{author} pushed {commit_count} commit(s) directly to {branch} without PR",
                "priority": NotificationPriority.HIGH,
                "channels": [NotificationChannel.IN_APP],
                "include_recommendations": False
            },
            "devops": {
                "title": "Direct push to {branch} detected",
                "body": "{author} bypassed PR workflow. {commit_count} commits to {branch}.",
                "priority": NotificationPriority.NORMAL,
                "channels": [NotificationChannel.IN_APP],
                "include_recommendations": False
            }
        },
        
        NotificationTemplate.DEPLOYMENT_FAILED: {
            "devops": {
                "title": "❌ Deployment failed: {environment}",
                "body": "Deployment to {environment} failed\n\nRepository: {repository}\n\nAction: Check logs and rollback if needed",
                "priority": NotificationPriority.URGENT,
                "channels": [NotificationChannel.IN_APP],
                "include_recommendations": False
            },
            "tech_lead": {
                "title": "Deployment failure: {environment}",
                "body": "Deployment to {environment} failed for {repository}",
                "priority": NotificationPriority.HIGH,
                "channels": [NotificationChannel.IN_APP],
                "include_recommendations": False
            }
        },
        
        NotificationTemplate.SPRINT_AT_RISK: {
            "pm": {
                "title": "🔴 Sprint at risk: {sprint_name}",
                "body": "Progress: {progress_pct}% | Time: {time_pct}%\n\nBlocked stories: {blocked_count}\n\nAction: Review sprint scope",
                "priority": NotificationPriority.HIGH,
                "channels": [NotificationChannel.IN_APP],
                "include_recommendations": True
            },
            "tech_lead": {
                "title": "Sprint {sprint_name} behind schedule",
                "body": "{blocked_count} blocked stories need attention",
                "priority": NotificationPriority.NORMAL,
                "channels": [NotificationChannel.IN_APP],
                "include_recommendations": False
            }
        }
    }
    
    RISK_EMOJIS = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🟢",
        "unknown": "⚪"
    }
    
    @classmethod
    def render(
        cls,
        template: NotificationTemplate,
        role: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Render a notification template for a specific role.
        
        Args:
            template: Template identifier
            role: User role (developer, tech_lead, pm, etc.)
            context: Data to fill template variables
        
        Returns:
            {
                "title": str,
                "body": str,
                "priority": NotificationPriority,
                "channels": List[NotificationChannel],
                "include_recommendations": bool
            }
        """
        template_def = cls.TEMPLATES.get(template, {})
        role_template = template_def.get(role)
        
        # Fall back to first available role if specific role not found
        if not role_template and template_def:
            role_template = next(iter(template_def.values()))
        
        if not role_template:
            # Default template
            return {
                "title": "Notification",
                "body": str(context),
                "priority": NotificationPriority.NORMAL,
                "channels": [NotificationChannel.IN_APP],
                "include_recommendations": False
            }
        
        # Add risk emoji to context if risk_level present
        if "risk_level" in context and "risk_emoji" not in context:
            context["risk_emoji"] = cls.RISK_EMOJIS.get(context["risk_level"], "⚪")
        
        # Format template strings
        try:
            title = role_template["title"].format(**context)
            body = role_template["body"].format(**context)
        except KeyError as e:
            # Missing context variable, use placeholder
            title = role_template["title"]
            body = role_template["body"]
        
        return {
            "title": title,
            "body": body,
            "priority": role_template["priority"],
            "channels": role_template["channels"],
            "include_recommendations": role_template.get("include_recommendations", False)
        }
    
    @classmethod
    def get_available_templates(cls) -> List[str]:
        """Get list of available template names."""
        return [t.value for t in NotificationTemplate]
    
    @classmethod
    def supports_role(cls, template: NotificationTemplate, role: str) -> bool:
        """Check if template has a variant for specific role."""
        template_def = cls.TEMPLATES.get(template, {})
        return role in template_def
