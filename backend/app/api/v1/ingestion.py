from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import IngestionJob

from .schemas import IngestionJobRead

router = APIRouter()


@router.get("/ingestion/jobs/{job_id}", response_model=IngestionJobRead)
def get_ingestion_job(job_id: int, db: Session = Depends(get_db)) -> IngestionJobRead:
    job = db.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"ingestion job {job_id} not found")
    return job
