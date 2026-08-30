"""
Performance Evaluation Agent
Pure AI-driven evaluation of developer performance.

AI reads all the data and evaluates across 6 dimensions.
NO formulas, NO tools - just AI reasoning.
"""

from typing import Dict, Any
import json
from agents.llm_provider import get_ollama_llm
from domain.models.developer_performance import (
    AIEvaluation,
    PerformanceBreakdown
)


class PerformanceEvaluationAgent:
    """
    AI agent that evaluates developer performance.
    
    This is the CORE of the system:
    - Receives raw developer data (commits, PRs, tasks, etc.)
    - AI reads and evaluates everything
    - Returns structured scores across 6 dimensions
    """
    
    def __init__(self):
        self.llm = get_ollama_llm(temperature=0.3)  # Lower temp for consistency
    
    async def evaluate_performance(
        self,
        developer_data: Dict[str, Any],
        developer_name: str,
        period_label: str
    ) -> AIEvaluation:
        """
        AI evaluates developer performance from raw data.
        
        Args:
            developer_data: Complete evidence package from aggregator
            developer_name: Developer's name
            period_label: Period being evaluated (e.g., "Sprint-23")
        
        Returns:
            AIEvaluation with scores, reasoning, recommendations
        """
        
        # Build comprehensive prompt for AI
        prompt = self._build_evaluation_prompt(
            developer_data,
            developer_name,
            period_label
        )
        
        # AI evaluates (this is where the magic happens!)
        try:
            response = await self.llm.ainvoke(prompt)
            
            # Parse AI response into structured format
            evaluation = self._parse_ai_response(response, developer_data)
            
            return evaluation
            
        except Exception as e:
            print(f"Error in AI evaluation: {e}")
            # Return default evaluation on error
            return self._get_default_evaluation(developer_data)
    
    def _build_evaluation_prompt(
        self,
        data: Dict[str, Any],
        dev_name: str,
        period: str
    ) -> str:
        """
        Build comprehensive evaluation prompt for AI.
        
        This is THE MOST IMPORTANT FUNCTION - it tells AI what to do.
        """
        
        summary = data.get('summary', {})
        commits = data.get('commits', [])
        prs = data.get('pull_requests', [])
        tasks = data.get('tasks', [])
        
        prompt = f"""You are an expert engineering performance evaluator analyzing a developer's work.

DEVELOPER: {dev_name}
PERIOD: {period}

=== ACTIVITY SUMMARY ===
• Commits: {summary.get('total_commits', 0)}
• Pull Requests: {summary.get('total_prs', 0)}
• Tasks Completed: {summary.get('total_tasks', 0)}
• Code Reviews Given: {summary.get('total_reviews_given', 0)}
• Lines Added: {summary.get('lines_added', 0)}
• Lines Deleted: {summary.get('lines_deleted', 0)}

=== COMMITS & CODE CHANGES ===
"""
        
        # Add commit details with diffs (AI reads actual code!)
        for i, commit in enumerate(commits[:10], 1):
            prompt += f"""
Commit {i}: {commit.get('message', '')}
Date: {commit.get('date', '')}
Files: {len(commit.get('files_changed', []))}
"""
            for file in commit.get('files_changed', [])[:2]:
                prompt += f"""
  • {file.get('filename', '')} (+{file.get('additions', 0)} -{file.get('deletions', 0)})
"""
                if file.get('patch'):
                    # AI reads the actual code diff!
                    prompt += f"""    Code changes:
{file['patch'][:800]}
"""
        
        # Add PR details with conversations
        prompt += f"""
=== PULL REQUESTS ===
"""
        for i, pr in enumerate(prs[:5], 1):
            prompt += f"""
PR #{pr.get('number', i)}: {pr.get('title', '')}
State: {pr.get('state', '')}
Files changed: {pr.get('files_changed', 0)}
Description: {pr.get('description', 'No description')[:300]}
"""
            # Add review conversations if available
            if pr.get('comments'):
                prompt += f"Comments: {len(pr['comments'])} review comments\n"
            if pr.get('reviews'):
                prompt += f"Reviews: {len(pr['reviews'])} reviews received\n"
        
        # Add task details
        prompt += f"""
=== TASKS & DELIVERABLES ===
"""
        for i, task in enumerate(tasks[:10], 1):
            prompt += f"""
Task {i}: {task.get('title', '')}
Status: {task.get('status', '')}
Story Points: {task.get('story_points', 0)}
Priority: {task.get('priority', 'medium')}
Description: {task.get('description', '')[:200]}
"""
        
        # Now ask AI to evaluate
        prompt += f"""

=== YOUR EVALUATION TASK ===

Based on ALL the data above (commits, code diffs, PRs, tasks), evaluate this developer's performance across 6 dimensions.

READ THE ACTUAL CODE CHANGES to judge quality. Don't just count metrics.

Evaluate:

1. CODE QUALITY (0-25 points)
   • Read the code diffs - is the code clean, maintainable?
   • Check for complexity, readability, security practices
   • Look for code smells, poor patterns
   • Consider naming, structure, documentation

2. DELIVERY & EXECUTION (0-20 points)
   • Did they complete valuable work?
   • Are tasks aligned with requirements?
   • Check for incomplete or rushed work
   • Consider story points and task complexity

3. PR & COLLABORATION (0-15 points)
   • Read PR descriptions and conversations
   • Are PRs well-structured and documented?
   • Do they participate in code review?
   • Do they communicate effectively?

4. TESTING & RELIABILITY (0-15 points)
   • Look for test files in commits
   • Check if code changes include tests
   • Look for potential bugs in the code
   • Consider build stability patterns

5. ENGINEERING IMPACT (0-10 points)
   • What business value did they deliver?
   • Did they solve important problems?
   • High-value features vs. trivial changes?
   • Technical debt addressed?

6. ENGINEERING JUDGMENT (0-5 points)
   • Do they make good technical decisions?
   • Do they handle complexity well?
   • Do they show learning/improvement?
   • Do they consider trade-offs?

OUTPUT FORMAT (JSON only):
{{
  "code_quality": {{
    "score": <0-25>,
    "reasoning": "<specific observations from code>"
  }},
  "delivery": {{
    "score": <0-20>,
    "reasoning": "<specific observations from tasks>"
  }},
  "collaboration": {{
    "score": <0-15>,
    "reasoning": "<specific observations from PRs>"
  }},
  "reliability": {{
    "score": <0-15>,
    "reasoning": "<specific observations from tests/bugs>"
  }},
  "engineering_impact": {{
    "score": <0-10>,
    "reasoning": "<business value assessment>"
  }},
  "engineering_judgment": {{
    "score": <0-5>,
    "reasoning": "<pattern analysis>"
  }},
  "strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
  "weaknesses": ["<weakness 1>", "<weakness 2>"],
  "recommendations": ["<specific action 1>", "<specific action 2>", "<specific action 3>"],
  "overall_reasoning": "<2-3 sentence summary>",
  "confidence": "<low|medium|high>"
}}

Be specific in your reasoning. Quote actual code examples when possible.
Be fair but honest. Don't inflate scores.
"""
        
        return prompt
    
    def _parse_ai_response(
        self,
        response: str,
        developer_data: Dict[str, Any]
    ) -> AIEvaluation:
        """
        Parse AI's JSON response into structured AIEvaluation model.
        """
        try:
            # Extract JSON from response
            response_text = response if isinstance(response, str) else str(response)
            
            # Find JSON block
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            
            if start == -1 or end == 0:
                raise ValueError("No JSON found in response")
            
            json_str = response_text[start:end]
            data = json.loads(json_str)
            
            # Extract scores (default to 0 if AI response is missing a dimension)
            code_quality_score = float(data.get('code_quality', {}).get('score', 0))
            delivery_score = float(data.get('delivery', {}).get('score', 0))
            collaboration_score = float(data.get('collaboration', {}).get('score', 0))
            reliability_score = float(data.get('reliability', {}).get('score', 0))
            impact_score = float(data.get('engineering_impact', {}).get('score', 0))
            judgment_score = float(data.get('engineering_judgment', {}).get('score', 0))
            
            # Validate scores are in range
            code_quality_score = max(0, min(25, code_quality_score))
            delivery_score = max(0, min(20, delivery_score))
            collaboration_score = max(0, min(15, collaboration_score))
            reliability_score = max(0, min(15, reliability_score))
            impact_score = max(0, min(10, impact_score))
            judgment_score = max(0, min(5, judgment_score))
            
            total_score = (
                code_quality_score +
                delivery_score +
                collaboration_score +
                reliability_score +
                impact_score +
                judgment_score
            )
            
            # Build breakdown
            breakdown = PerformanceBreakdown(
                code_quality=code_quality_score,
                delivery=delivery_score,
                collaboration=collaboration_score,
                reliability=reliability_score,
                engineering_impact=impact_score,
                engineering_judgment=judgment_score
            )
            
            # Extract other fields
            strengths = data.get('strengths', [])
            weaknesses = data.get('weaknesses', [])
            recommendations = data.get('recommendations', [])
            reasoning = data.get('overall_reasoning', 'Performance evaluation complete.')
            confidence = data.get('confidence', 'medium')
            
            # Build reasoning from individual dimension reasoning
            detailed_reasoning = f"{reasoning}\n\n"
            detailed_reasoning += f"Code Quality: {data.get('code_quality', {}).get('reasoning', 'N/A')}\n"
            detailed_reasoning += f"Delivery: {data.get('delivery', {}).get('reasoning', 'N/A')}\n"
            detailed_reasoning += f"Collaboration: {data.get('collaboration', {}).get('reasoning', 'N/A')}\n"
            detailed_reasoning += f"Reliability: {data.get('reliability', {}).get('reasoning', 'N/A')}\n"
            detailed_reasoning += f"Impact: {data.get('engineering_impact', {}).get('reasoning', 'N/A')}\n"
            detailed_reasoning += f"Judgment: {data.get('engineering_judgment', {}).get('reasoning', 'N/A')}"
            
            # Assess data quality
            summary = developer_data.get('summary', {})
            data_quality = {
                "commits_analyzed": summary.get('total_commits', 0),
                "prs_analyzed": summary.get('total_prs', 0),
                "tasks_analyzed": summary.get('total_tasks', 0),
                "has_code_diffs": len(developer_data.get('commits', [])) > 0,
                "has_pr_conversations": len(developer_data.get('pull_requests', [])) > 0,
            }
            
            return AIEvaluation(
                score=total_score,
                breakdown=breakdown,
                strengths=strengths,
                weaknesses=weaknesses,
                recommendations=recommendations,
                reasoning=detailed_reasoning,
                confidence=confidence,
                data_quality=data_quality
            )
            
        except Exception as e:
            print(f"Error parsing AI response: {e}")
            print(f"Response was: {response[:500]}")
            return self._get_default_evaluation(developer_data)
    
    def _get_default_evaluation(
        self,
        developer_data: Dict[str, Any]
    ) -> AIEvaluation:
        """
        Return default evaluation when AI fails.
        Scores are zeroed out to clearly indicate no real evaluation occurred.
        """
        summary = developer_data.get('summary', {})
        
        total_commits = summary.get('total_commits', 0)
        total_prs = summary.get('total_prs', 0)
        total_tasks = summary.get('total_tasks', 0)
        
        breakdown = PerformanceBreakdown(
            code_quality=0,
            delivery=0,
            collaboration=0,
            reliability=0,
            engineering_impact=0,
            engineering_judgment=0
        )
        
        return AIEvaluation(
            score=0,
            breakdown=breakdown,
            strengths=[],
            weaknesses=["AI evaluation failed — no scores available"],
            recommendations=["Retry evaluation when Ollama is available"],
            reasoning="Default evaluation returned due to AI unavailability. Scores are zeroed out.",
            confidence="low",
            data_quality={
                "commits_analyzed": total_commits,
                "prs_analyzed": total_prs,
                "tasks_analyzed": total_tasks,
                "ai_evaluation_failed": True
            }
        )
    
    def calculate_confidence_level(
        self,
        developer_data: Dict[str, Any],
        days_of_data: int
    ) -> tuple[str, str]:
        """
        Calculate confidence level based on data availability.
        
        Returns:
            (level, reason) tuple
        """
        summary = developer_data.get('summary', {})
        
        commits = summary.get('total_commits', 0)
        prs = summary.get('total_prs', 0)
        tasks = summary.get('total_tasks', 0)
        
        total_data_points = commits + prs + tasks
        
        if days_of_data < 7:
            return ("low", f"Only {days_of_data} days of data available")
        
        if total_data_points < 5:
            return ("low", f"Limited activity: {total_data_points} data points")
        
        if days_of_data < 30 or total_data_points < 20:
            return ("medium", f"{days_of_data} days of data with {total_data_points} data points")
        
        return ("high", f"Sufficient data: {days_of_data} days, {total_data_points} data points")
    
    def determine_grade(self, score: float) -> str:
        """
        Convert numeric score to letter grade.
        """
        if score >= 95:
            return "A+"
        elif score >= 90:
            return "A"
        elif score >= 85:
            return "B+"
        elif score >= 80:
            return "B"
        elif score >= 75:
            return "C+"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"
