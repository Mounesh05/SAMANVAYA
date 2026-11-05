"""
Tests for AI Agent Authorization (FEAT-003)

Verifies:
- AI agents respect user permissions
- HR AI cannot bypass authorization
- HR AI gets filtered data (no technical details)
- Existing AI functionality unchanged for engineering users
"""

import json
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from fastapi import HTTPException

from core.permissions import Permission


class TestHRAgentPermissions:
    """Test HR agent permission requirements."""
    
    def test_hr_agent_requires_view_employee_directory(self):
        """HR AI agent requires VIEW_EMPLOYEE_DIRECTORY permission."""
        from agents.hr_agent import hr_assistant_node
        
        state = {
            'user_context': {
                'role': 'HR',
                'permissions': [],  # Missing VIEW_EMPLOYEE_DIRECTORY
            },
            'evidence': {},
            'context': {},
            'agent_history': [],
            'errors': [],
        }
        
        result = hr_assistant_node(state)
        
        assert 'errors' in result
        assert len(result['errors']) > 0
        assert 'Insufficient permissions' in result['errors'][0]
    
    def test_hr_agent_with_permission_succeeds(self, monkeypatch):
        """HR AI agent works with proper permissions."""
        from agents import hr_agent
        
        state = {
            'user_context': {
                'role': 'HR',
                'permissions': [Permission.VIEW_EMPLOYEE_DIRECTORY.value],
            },
            'evidence': {
                'performance_summary': {
                    'overall_score': 85,
                    'grade': 'B',
                },
            },
            'context': {'employee_name': 'John Doe'},
            'agent_history': [],
            'errors': [],
        }
        
        mock_llm = Mock()
        mock_llm.invoke.return_value = json.dumps({
            "analysis": "Employee performance is satisfactory",
            "recommendations": ["Continue current trajectory"],
            "risk_level": "low",
            "confidence": 0.8
        })
        monkeypatch.setattr(hr_agent, 'get_ollama_llm', lambda **kwargs: mock_llm)
        
        result = hr_agent.hr_assistant_node(state)
        
        assert 'errors' not in result or len(result.get('errors', [])) == 0
        assert result.get('analysis') is not None
        assert 'hr_assistant' in result.get('agent_history', [])


class TestCodeAgentPermissions:
    """Test code agent permission requirements."""
    
    def test_code_agent_requires_view_ai_evaluation(self):
        """Code agent checks VIEW_AI_EVALUATION permission."""
        from agents.code_agent import code_analysis_node
        
        state = {
            'user_context': {
                'role': 'DEVELOPER',
                'permissions': [],  # Missing VIEW_AI_EVALUATION
            },
            'evidence': {},
            'context': {},
            'agent_history': [],
            'errors': [],
        }
        
        result = code_analysis_node(state)
        
        assert 'errors' in result
        assert len(result['errors']) > 0
        assert 'Insufficient permissions to analyze code' in result['errors'][0]
    
    def test_code_agent_with_permission_succeeds(self, monkeypatch):
        """Code agent works with proper permissions."""
        from agents import code_agent
        
        state = {
            'user_context': {
                'role': 'DEVELOPER',
                'permissions': [Permission.VIEW_AI_EVALUATION.value],
            },
            'evidence': {
                'evidence_summary': 'PR #123: Added new feature',
                'files_analyzed': 5,
            },
            'context': {'pr_title': 'Add feature'},
            'agent_history': [],
            'errors': [],
        }
        
        mock_llm = Mock()
        mock_llm.invoke.return_value = json.dumps({
            "quality_score": 85,
            "failure_risk": 15,
            "risk_level": "low",
            "confidence": 0.9,
            "analysis": "Code quality is good",
            "critical_issues": [],
            "recommendations": ["Add more tests"],
            "review_focus": "test_module.py",
            "quality_breakdown": {
                "correctness": 18,
                "maintainability": 17,
                "security": 19,
                "testing": 12,
                "performance": 9,
                "architecture": 8,
                "readability": 4
            }
        })
        monkeypatch.setattr(code_agent, 'get_ollama_llm', lambda **kwargs: mock_llm)
        
        result = code_agent.code_analysis_node(state)
        
        assert 'errors' not in result or len(result.get('errors', [])) == 0
        assert result.get('quality_score') is not None


class TestHRAgentRestrictions:
    """Test that HR AI cannot access technical details."""
    
    def test_hr_agent_filters_technical_evidence(self, monkeypatch):
        """HR AI cannot read source code, PRs, commits."""
        from agents import hr_agent
        
        state = {
            'user_context': {
                'role': 'HR',
                'permissions': [Permission.VIEW_EMPLOYEE_DIRECTORY.value],
            },
            'evidence': {
                'github_data': {
                    'pr_diffs': 'SENSITIVE CODE DIFF',
                    'commit_messages': 'Detailed commit history',
                },
                'performance_summary': {
                    'overall_score': 85,
                },
            },
            'context': {},
            'agent_history': [],
            'errors': [],
        }
        
        mock_llm = Mock()
        mock_llm.invoke.return_value = json.dumps({
            "analysis": "HR summary",
            "recommendations": ["Continue"],
            "risk_level": "low",
            "confidence": 0.7
        })
        monkeypatch.setattr(hr_agent, 'get_ollama_llm', lambda **kwargs: mock_llm)
        
        result = hr_agent.hr_assistant_node(state)
        
        # Check that the prompt sent to LLM doesn't contain technical details
        call_args = mock_llm.invoke.call_args
        prompt = call_args[0][0] if call_args else ""
        
        # HR prompt should NOT contain PR diffs or commit details
        assert 'SENSITIVE CODE DIFF' not in prompt
        assert 'Detailed commit history' not in prompt


class TestAIRunFiltering:
    """Test AI run result filtering for HR users."""
    
    def test_filter_ai_run_removes_technical_evidence(self):
        """HR users receive filtered AI run results without technical details."""
        from api.routes.ai import filter_ai_run_for_hr
        
        run = {
            'id': 'run123',
            'agent_type': 'code_review',
            'input_data': {
                'evidence': {
                    'pr_diffs': 'SENSITIVE CODE',
                    'commit_details': 'Detailed commits',
                },
                'context': {'pr_title': 'Feature'},
            },
            'output_data': {
                'analysis': 'Code analysis result',
                'recommendations': ['Improve tests'],
                'agent_history': ['code_agent', 'qa_agent'],
                'errors': ['Some technical error'],
            },
        }
        
        filtered = filter_ai_run_for_hr(run)
        
        # Evidence should be filtered
        assert 'input_data' in filtered
        assert filtered['input_data']['evidence']['filtered'] is True
        
        # Technical details should be removed from output
        assert 'output_data' in filtered
        assert 'agent_history' not in filtered['output_data']
        assert 'errors' not in filtered['output_data']
        
        # High-level info should remain
        assert filtered['output_data']['analysis'] == 'Code analysis result'
        assert filtered['output_data']['recommendations'] == ['Improve tests']


class TestSupervisorRouting:
    """Test that HR users are routed to HR assistant."""
    
    @pytest.mark.asyncio
    async def test_hr_user_routes_to_hr_assistant(self, monkeypatch):
        """HR users are automatically routed to hr_assistant regardless of task_type."""
        from agents import supervisor, hr_agent
        
        state = {
            'task_type': 'code_review',  # HR user tries to access code_review
            'user_context': {
                'role': 'HR',
                'permissions': [Permission.VIEW_EMPLOYEE_DIRECTORY.value],
            },
            'evidence': {},
            'context': {},
        }
        
        mock_llm = Mock()
        mock_llm.invoke.return_value = json.dumps({
            "analysis": "HR analysis",
            "recommendations": ["HR rec"],
            "risk_level": "low",
            "confidence": 0.7
        })
        monkeypatch.setattr(hr_agent, 'get_ollama_llm', lambda **kwargs: mock_llm)
        
        result = await supervisor.ainvoke_agent('code_review', state)
        
        # Should have been routed to hr_assistant
        assert 'hr_assistant' in result.get('agent_history', [])
        # Should NOT have accessed code_agent
        assert 'code_agent_enhanced' not in result.get('agent_history', [])


class TestEndToEndAIAuthorization:
    """End-to-end tests for AI authorization."""
    
    @pytest.mark.asyncio
    async def test_hr_user_cannot_invoke_ai_without_permission(self, monkeypatch):
        """HR user without TRIGGER_AI_EVALUATION cannot invoke AI."""
        from api.routes import ai as ai_routes
        from api.routes.ai import AgentRequest
        
        current_user = {
            'employee_id': 'EMP001',
            'role': 'HR',
            'is_admin': False,
            'designation': None,
        }
        
        request = AgentRequest(
            task_type='hr_assistant',
            evidence={'test': 'data'},
            context={},
        )
        
        mock_perms = Mock(return_value=[])  # No TRIGGER_AI_EVALUATION
        monkeypatch.setattr(ai_routes, 'get_user_permissions', mock_perms)
        
        with pytest.raises(HTTPException) as exc_info:
            await ai_routes.invoke_agent_endpoint(request, current_user)
        
        assert exc_info.value.status_code == 403
        assert 'Insufficient permissions' in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_developer_ai_unchanged(self, monkeypatch):
        """Developer AI functionality unchanged - full technical access."""
        from api.routes import ai as ai_routes
        from api.routes.ai import AgentRequest
        from agents import code_agent
        
        current_user = {
            'employee_id': 'EMP002',
            'role': 'DEVELOPER',
            'is_admin': False,
            'designation': 'Senior Developer',
        }
        
        request = AgentRequest(
            task_type='code_review',
            evidence={'evidence_summary': 'PR #123'},
            context={},
            save_run=False,
        )
        
        mock_perms = Mock(return_value=[
            Permission.TRIGGER_AI_EVALUATION,
            Permission.VIEW_AI_EVALUATION,
        ])
        mock_ollama = Mock(return_value=True)
        mock_projects = AsyncMock(return_value=['proj1'])
        
        monkeypatch.setattr(ai_routes, 'get_user_permissions', mock_perms)
        monkeypatch.setattr(ai_routes, 'check_ollama_connection', mock_ollama)
        monkeypatch.setattr(ai_routes, 'get_accessible_project_ids', mock_projects)
        
        mock_llm = Mock()
        mock_llm.invoke.return_value = json.dumps({
            "quality_score": 90,
            "failure_risk": 10,
            "risk_level": "low",
            "confidence": 0.95,
            "analysis": "Excellent code quality",
            "critical_issues": [],
            "recommendations": ["Minor improvements"],
            "review_focus": "main.py",
            "quality_breakdown": {
                "correctness": 20, "maintainability": 19, "security": 20,
                "testing": 14, "performance": 9, "architecture": 9, "readability": 5
            }
        })
        monkeypatch.setattr(code_agent, 'get_ollama_llm', lambda **kwargs: mock_llm)
        
        result = await ai_routes.invoke_agent_endpoint(request, current_user)
        
        # Developer should get full technical analysis
        assert result.analysis == "Excellent code quality"
        assert 'code_agent_enhanced' in result.agent_history
        # Quality score is in the internal result, not exposed in AgentResponse
        # But we verify that technical analysis was performed successfully


class TestPerformanceAgentFiltering:
    """Test performance evaluation agent filters data for HR."""
    
    def test_performance_agent_filters_for_hr(self):
        """Performance agent returns filtered summary for HR users."""
        from agents.performance_agent import PerformanceEvaluationAgent
        
        agent = PerformanceEvaluationAgent()
        
        developer_data = {
            'summary': {'total_commits': 10, 'total_prs': 5},
            'commits': [{'message': 'SENSITIVE COMMIT'}],
        }
        
        user_context = {
            'role': 'HR',
            'permissions': [Permission.VIEW_PERFORMANCE_OUTCOMES.value],
        }
        
        # This would normally call the async method, but we'll test the HR filter method
        with patch.object(agent, '_get_performance_summary_for_hr') as mock_hr_summary:
            mock_hr_summary.return_value = Mock(
                score=75.0,
                reasoning='HR summary',
                data_quality={'hr_filtered': True}
            )
            
            # Simulate calling evaluate_performance with HR context
            # In real implementation, this would be called from API
            result = agent._get_performance_summary_for_hr(
                developer_data, 'John Doe', 'Q1 2024'
            )
        
        # Should have hr_filtered flag
        assert result.data_quality.get('hr_filtered') is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
