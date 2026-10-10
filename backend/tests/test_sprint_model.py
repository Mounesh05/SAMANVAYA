import pytest
from pydantic import ValidationError

from domain.models.sprint import SprintCreate


def test_sprint_dates_accept_same_day_and_iso_datetimes():
    sprint = SprintCreate(
        name="Sprint",
        project_id="project-1",
        start_date="2026-10-05",
        end_date="2026-10-05T23:59:59Z",
    )

    assert sprint.start_date == "2026-10-05"


def test_sprint_rejects_end_date_before_start_date():
    with pytest.raises(ValidationError, match="on or after"):
        SprintCreate(
            name="Invalid sprint",
            project_id="project-1",
            start_date="2026-10-12",
            end_date="2026-10-05",
        )


def test_sprint_rejects_invalid_dates():
    with pytest.raises(ValidationError, match="valid ISO dates"):
        SprintCreate(
            name="Invalid sprint",
            project_id="project-1",
            start_date="not-a-date",
            end_date="2026-10-05",
        )
