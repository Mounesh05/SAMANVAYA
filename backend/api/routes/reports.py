"""
CR-011: report downloads (CEO, PM, HR).

GET  /api/reports          reports the caller may download
POST /api/reports/{type}   generate one (CSV or JSON), audited
"""

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field

from core.dependencies import get_current_user
from domain.services import report_service

router = APIRouter()


class ReportRequest(BaseModel):
    purpose: str = Field(..., min_length=3, max_length=500)
    project_id: Optional[str] = Field(None, max_length=100)
    start: Optional[date] = Field(None, alias="from")
    end: Optional[date] = Field(None, alias="to")
    format: Literal["csv", "json"] = "csv"

    model_config = {"populate_by_name": True}


@router.get("")
async def list_reports(user: dict = Depends(get_current_user)):
    return {"reports": report_service.available_reports(user)}


@router.post("/{report_type}")
async def generate_report(report_type: str, request: ReportRequest, user: dict = Depends(get_current_user)):
    result = await report_service.generate(
        user, report_type, purpose=request.purpose, project_id=request.project_id,
        start=request.start, end=request.end,
    )
    if request.format == "json":
        return result
    return Response(
        content=report_service.to_csv(result["columns"], result["rows"]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{report_type}_{result["generated_at"][:10]}.csv"',
            "X-Report-Digest": result["digest"],
            "Cache-Control": "no-store",
        },
    )
