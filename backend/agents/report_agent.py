"""
Report Agent — LangGraph node and employee evaluation report synthesis.

Architecture role:
    SPECIALIST AGENTS -> PERFORMANCE AGGREGATOR -> REPORT AGENT

The Report Agent does NOT independently invent scores.
It presents and explains scores produced by specialist agents, including:
- Employee overview
- Individual agent scores & subscores
- Traceable evidence
- Strengths & weaknesses
- Actionable recommendations
- Insufficient-evidence warnings
- Evaluation period & data sources
- Optional PDF report export
"""

import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import io

from .state import AgentState
from intelligence.scoring.models import AggregatedEmployeeEvaluation, EmployeeScore

logger = logging.getLogger("samanvaya.report_agent")


class EmployeeReportGenerator:
    """
    Generates structured presentations and PDF documents of employee evaluations
    without altering any numeric scores.
    """

    @staticmethod
    def generate_presentation_report(
        evaluation: AggregatedEmployeeEvaluation,
    ) -> Dict[str, Any]:
        """
        Builds a comprehensive structured report dict suitable for API and UI rendering.
        """
        agent_sections = {}
        insufficient_evidence_warnings = []

        for agent_key, score_obj in evaluation.agent_scores.items():
            if score_obj.status == "insufficient_evidence" or score_obj.score is None:
                insufficient_evidence_warnings.append({
                    "dimension": agent_key,
                    "agent": score_obj.agent,
                    "warning": score_obj.status_reason or f"Insufficient data observed for {agent_key} in the evaluated period.",
                })

            subscores_list = []
            for sub_name, sub in score_obj.subscore_details.items():
                subscores_list.append({
                    "name": sub.name,
                    "score": sub.score,
                    "max_score": sub.max_score,
                    "explanation": sub.explanation,
                })

            evidence_list = []
            for ev in score_obj.evidence[:10]:
                evidence_list.append({
                    "source": ev.source,
                    "id": ev.id,
                    "metric": ev.metric,
                    "value": str(ev.value)[:100],
                })

            agent_sections[agent_key] = {
                "agent_id": score_obj.agent,
                "score_type": score_obj.score_type,
                "score": score_obj.score,
                "confidence": score_obj.confidence,
                "status": score_obj.status,
                "analysis": score_obj.analysis,
                "subscores": subscores_list,
                "evidence_items": evidence_list,
                "metrics": score_obj.metrics,
                "strengths": score_obj.strengths,
                "weaknesses": score_obj.weaknesses,
                "recommendations": score_obj.recommendations,
            }

        return {
            "evaluation_id": evaluation.evaluation_id,
            "employee_id": evaluation.employee_id,
            "employee_name": evaluation.employee_name,
            "company_id": evaluation.company_id,
            "evaluation_period": {
                "start": evaluation.evaluation_period.start_date,
                "end": evaluation.evaluation_period.end_date,
                "label": evaluation.evaluation_period.label,
            },
            "overall_score": evaluation.overall_score,
            "agent_score_marks": evaluation.agent_score_marks,
            "superior_score_marks": evaluation.superior_score_marks,
            "final_score": evaluation.final_score,
            "score_split": {
                "agent_score_marks": evaluation.agent_score_marks,
                "agent_score_max": 80.0,
                "superior_score_marks": evaluation.superior_score_marks,
                "superior_score_max": 20.0,
                "final_score": evaluation.final_score,
                "final_score_max": 100.0,
            },
            "grade": evaluation.grade,
            "confidence": evaluation.overall_confidence,
            "summary": evaluation.summary,
            "executive_summary": evaluation.summary,
            "strengths": evaluation.strengths,
            "key_strengths": evaluation.strengths,
            "weaknesses": evaluation.weaknesses,
            "areas_for_growth": evaluation.weaknesses,
            "recommendations": evaluation.recommendations,
            "weights_used": evaluation.weights_used,
            "scoring_version": evaluation.scoring_version,
            "agent_scores": agent_sections,
            "dimension_scorecard": [
                {
                    "dimension": k,
                    "agent": v["agent_id"],
                    "score": v["score"],
                    "confidence": v["confidence"],
                    "status": v["status"],
                }
                for k, v in agent_sections.items()
            ],
            "insufficient_evidence_warnings": insufficient_evidence_warnings,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def generate_evaluation_pdf(evaluation: AggregatedEmployeeEvaluation) -> bytes:
        """
        Builds an executive PDF scorecard using ReportLab.
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors

            buf = io.BytesIO()
            doc = SimpleDocTemplate(buf, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
            styles = getSampleStyleSheet()

            title_style = ParagraphStyle(
                'EvalTitle',
                parent=styles['Heading1'],
                fontSize=20,
                textColor=colors.HexColor("#1e293b"),
                spaceAfter=10,
            )
            body_style = ParagraphStyle(
                'EvalBody',
                parent=styles['Normal'],
                fontSize=10,
                leading=14,
                textColor=colors.HexColor("#334155"),
            )
            h2_style = ParagraphStyle(
                'EvalH2',
                parent=styles['Heading2'],
                fontSize=14,
                textColor=colors.HexColor("#3b82f6"),
                spaceBefore=12,
                spaceAfter=6,
            )

            story = []

            # Header
            story.append(Paragraph("Engineering Intelligence — Employee Performance Evaluation", title_style))
            story.append(Paragraph(
                f"<b>Employee:</b> {evaluation.employee_name} ({evaluation.employee_id}) &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"<b>Period:</b> {evaluation.evaluation_period.start_date} to {evaluation.evaluation_period.end_date} &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"<b>Grade:</b> {evaluation.grade or 'N/A'}",
                body_style,
            ))
            story.append(Spacer(1, 12))

            # Score Box: Agent Score = 80 marks, Superior Score = 20 marks, Final Score = 100 marks
            overall_val = f"{evaluation.overall_score:.1f}/100" if evaluation.overall_score is not None else "N/A"
            agent_score_str = f"{evaluation.agent_score_marks:.1f} / 80" if evaluation.agent_score_marks is not None else (f"{evaluation.overall_score * 0.8:.1f} / 80" if evaluation.overall_score is not None else "N/A")
            superior_score_str = f"{evaluation.superior_score_marks:.1f} / 20" if evaluation.superior_score_marks is not None else "Pending / 20"
            final_score_str = f"{evaluation.final_score:.1f} / 100" if evaluation.final_score is not None else overall_val

            score_table_data = [
                ["Agent Score (Max 80)", "Superior Score (Max 20)", "Final Score (Max 100)", "Confidence"],
                [agent_score_str, superior_score_str, final_score_str, f"{int(evaluation.overall_confidence * 100)}%"],
            ]
            t = Table(score_table_data, colWidths=[130, 130, 130, 110])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#475569")),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
            story.append(t)
            story.append(Spacer(1, 14))

            # Executive Summary
            story.append(Paragraph("Executive Summary", h2_style))
            story.append(Paragraph(evaluation.summary, body_style))
            story.append(Spacer(1, 10))

            # Specialist Scores Table
            story.append(Paragraph("Specialist Dimension Scores", h2_style))
            dim_data = [["Dimension", "Agent", "Score", "Status", "Weight"]]
            for key, agent_sc in evaluation.agent_scores.items():
                s_val = f"{agent_sc.score:.1f}/100" if agent_sc.score is not None else "N/A"
                w_val = f"{evaluation.weights_used.get(key, 0.0) * 100:.0f}%"
                dim_data.append([
                    key.replace("_", " ").title(),
                    agent_sc.agent,
                    s_val,
                    agent_sc.status.replace("_", " ").title(),
                    w_val,
                ])

            dt = Table(dim_data, colWidths=[150, 110, 80, 100, 60])
            dt.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(dt)
            story.append(Spacer(1, 12))

            # Strengths & Recommendations
            story.append(Paragraph("Key Strengths", h2_style))
            for st in evaluation.strengths:
                story.append(Paragraph(f"• {st}", body_style))
            story.append(Spacer(1, 8))

            story.append(Paragraph("Actionable Recommendations", h2_style))
            for rec in evaluation.recommendations:
                story.append(Paragraph(f"• {rec}", body_style))

            doc.build(story)
            return buf.getvalue()
        except Exception as e:
            logger.error("[REPORT-AGENT] PDF generation error: %s", e)
            return b"%PDF-1.4 Mock PDF Fallback due to: " + str(e).encode()

    generate_pdf_report = generate_evaluation_pdf

    @classmethod
    def generate_pdf_report_from_doc(cls, doc: Dict[str, Any]) -> bytes:
        """Helper to generate PDF directly from a persisted MongoDB evaluation document."""
        from intelligence.scoring.models import AggregatedEmployeeEvaluation, EvaluationPeriod, EmployeeScore
        try:
            period_data = doc.get("period", {})
            period = EvaluationPeriod(
                start_date=period_data.get("start", "2026-09-01"),
                end_date=period_data.get("end", "2026-09-30"),
                label=period_data.get("label", "2026-09"),
            )
            raw_agent_scores = doc.get("agent_scores", {})
            agent_scores = {}
            for k, v in raw_agent_scores.items():
                if isinstance(v, dict):
                    agent_scores[k] = EmployeeScore.model_validate(v)
                elif hasattr(v, "score"):
                    agent_scores[k] = v

            eval_obj = AggregatedEmployeeEvaluation(
                evaluation_id=doc.get("evaluation_id") or str(doc.get("_id", "eval")),
                employee_id=doc.get("employee_id", "EMP-UNKNOWN"),
                employee_name=doc.get("employee_name", "Unknown Engineer"),
                company_id=doc.get("company_id", "ORG-001"),
                evaluation_period=period,
                overall_score=doc.get("overall_score"),
                agent_score_marks=doc.get("agent_score_marks") or (round(doc.get("overall_score") * 0.8, 2) if doc.get("overall_score") is not None else None),
                superior_score_marks=doc.get("superior_score_marks"),
                final_score=doc.get("final_score") or doc.get("overall_score"),
                grade=doc.get("grade", "N/A"),
                overall_confidence=doc.get("confidence", 0.0),
                agent_scores=agent_scores,
                weights_used=doc.get("weights_used", {}),
                summary=doc.get("report", {}).get("executive_summary") or doc.get("summary") or "Performance Evaluation",
                strengths=doc.get("report", {}).get("key_strengths") or doc.get("strengths") or [],
                weaknesses=doc.get("report", {}).get("areas_for_growth") or doc.get("weaknesses") or [],
                recommendations=[f"Focus on improving {w.lower()}" for w in (doc.get("report", {}).get("areas_for_growth") or [])],
                scoring_version=doc.get("scoring_version", "2.0.0"),
            )
            return cls.generate_pdf_report(eval_obj)
        except Exception as exc:
            logger.error("[REPORT-AGENT] Error generating PDF from doc: %s", exc)
            return b"%PDF-1.4 Fallback Error: " + str(exc).encode()


# ─────────────────────────────────────────────────────────────────────────────
# LangGraph node wrapper
# ─────────────────────────────────────────────────────────────────────────────

async def report_synthesis_node(state: AgentState) -> AgentState:
    """
    LangGraph node: synthesize a report from already calculated specialist scores or ReAct.
    """
    t0 = time.time()
    context = state.get("context", {})
    evidence = state.get("evidence", {})
    company_id = state.get("company_id", "ORG-001")
    user_role = state.get("user_role", "CEO")
    user_id = state.get("user_id", "system")

    # If evaluation object passed in context or evidence, build evaluation presentation report
    eval_obj = context.get("evaluation") or evidence.get("evaluation")
    if eval_obj:
        if isinstance(eval_obj, dict):
            # Parse into model
            try:
                from intelligence.scoring.models import AggregatedEmployeeEvaluation
                eval_obj = AggregatedEmployeeEvaluation.model_validate(eval_obj)
            except Exception:
                pass

        if isinstance(eval_obj, AggregatedEmployeeEvaluation):
            presentation = EmployeeReportGenerator.generate_presentation_report(eval_obj)
            pdf_bytes = EmployeeReportGenerator.generate_evaluation_pdf(eval_obj)
            latency_ms = round((time.time() - t0) * 1000, 1)

            return {
                **state,
                "analysis": presentation["summary"],
                "recommendations": presentation["recommendations"],
                "risk_level": "low" if (presentation["overall_score"] or 0) >= 80 else "medium",
                "confidence": presentation["confidence"],
                "structured_output": {
                    "report": presentation,
                    "pdf_bytes": pdf_bytes,
                    "pdf_size": len(pdf_bytes),
                },
                "agent_history": state.get("agent_history", []) + ["report_agent"],
                "latency_ms": {**state.get("latency_ms", {}), "report_agent": latency_ms},
            }

    # Fallback to existing ReAct agent for executive/HR reports
    title = context.get("title", "Strategic Intelligence Report")
    verbose = context.get("verbose", False)
    report_id = context.get("report_id", "REP-01")
    user_name = context.get("user_name") or evidence.get("user_name") or user_id

    try:
        from .report_react_agent import ReportReActAgent
        agent = ReportReActAgent(verbose=verbose)
        pdf_bytes = await agent.analyze_and_generate_pdf(
            report_id=report_id,
            title=title,
            role=user_role,
            company_id=company_id,
            user_name=user_name,
        )
        latency_ms = round((time.time() - t0) * 1000, 1)

        return {
            **state,
            "analysis": f"AI report synthesized: '{title}' for {user_role} at {company_id}.",
            "recommendations": ["Review exported report for executive details."],
            "risk_level": "low",
            "confidence": 0.92,
            "structured_output": {
                "pdf_bytes": pdf_bytes,
                "pdf_size": len(pdf_bytes),
                "report_id": report_id,
                "title": title,
                "role": user_role,
            },
            "agent_history": state.get("agent_history", []) + ["report_agent"],
            "latency_ms": {**state.get("latency_ms", {}), "report_agent": latency_ms},
        }
    except Exception as exc:
        latency_ms = round((time.time() - t0) * 1000, 1)
        return {
            **state,
            "analysis": f"Report synthesis failed: {exc}",
            "recommendations": [],
            "risk_level": "high",
            "confidence": 0.0,
            "agent_history": state.get("agent_history", []) + ["report_agent"],
            "errors": state.get("errors", []) + [f"report_agent: {exc}"],
            "latency_ms": {**state.get("latency_ms", {}), "report_agent": latency_ms},
        }
