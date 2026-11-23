from typing import Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from .database import check_database

router = APIRouter(prefix="/api/health", tags=["Health"])


class HealthStatus(BaseModel):
    status: Literal["ok", "unavailable"]


@router.get("/live", response_model=HealthStatus)
def live(response: Response) -> HealthStatus:
    response.headers["Cache-Control"] = "no-store"
    return HealthStatus(status="ok")


@router.get("/ready", response_model=HealthStatus, responses={503: {"model": HealthStatus}})
def ready(request: Request, response: Response) -> HealthStatus:
    response.headers["Cache-Control"] = "no-store"
    try:
        check_database(request.app.state.database)
    except SQLAlchemyError:
        response.status_code = 503
        return HealthStatus(status="unavailable")
    return HealthStatus(status="ok")
