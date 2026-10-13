"""
Audit Log Routes
Implements SRS FR-DAT-004 (audit trail access) and FR-DAT-005 (hash chain verification)

Origin: BioSync-Gateway middleware/api/routes/audit.py (adapted).
Removed: the Gateway POST /test-trigger endpoint interpolated a caller-supplied table name
into an UPDATE statement (SQL injection). Trigger rejection is verified by the OQ suite instead.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import logging

from api.auth import require_scope
from database import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/")
async def get_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    table_name: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("audit_read"))
):
    """
    Retrieve paginated audit logs with filtering.
    Requires audit_read scope.
    """
    try:
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = {}

        if table_name:
            query += " AND table_name = :table_name"
            params["table_name"] = table_name

        if action:
            query += " AND action = :action"
            params["action"] = action

        if start_date:
            query += " AND occurred_at >= :start_date"
            params["start_date"] = start_date

        if end_date:
            query += " AND occurred_at <= :end_date"
            params["end_date"] = end_date

        count_query = f"SELECT COUNT(*) FROM ({query}) AS count_query"
        total = db.execute(text(count_query), params).scalar()

        query += " ORDER BY id DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = (page - 1) * limit

        result = db.execute(text(query), params)
        logs = [dict(row._mapping) for row in result]

        return {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit,
            "logs": logs
        }

    except Exception as e:
        logger.error(f"Error retrieving audit logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve audit logs")


@router.get("/verify")
async def verify_hash_chain(
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("audit_read"))
):
    """
    Verify integrity of the audit_log hash chain (SRS FR-DAT-005).
    Returns the integrity status and the first broken row if one is detected.
    """
    try:
        result = db.execute(text("SELECT * FROM verify_hash_chain()"))
        row = result.first()

        if row:
            return {
                "integrity": row[0],
                "broken_at_row_id": row[1],
                "verification_timestamp": datetime.utcnow().isoformat()
            }

        return {
            "integrity": "unknown",
            "broken_at_row_id": None,
            "verification_timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error verifying hash chain: {e}")
        raise HTTPException(status_code=500, detail="Failed to verify hash chain")


@router.get("/statistics")
async def get_audit_statistics(
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("audit_read"))
):
    """
    Get audit log statistics: counts by table and action, and the time range.
    """
    try:
        stats_query = """
            SELECT
                table_name,
                action,
                COUNT(*) AS count,
                MIN(occurred_at) AS first_entry,
                MAX(occurred_at) AS last_entry
            FROM audit_log
            GROUP BY table_name, action
            ORDER BY table_name, action
        """

        result = db.execute(text(stats_query))
        stats = [dict(row._mapping) for row in result]

        total = db.execute(text("SELECT COUNT(*) FROM audit_log")).scalar()

        return {
            "total_entries": total,
            "statistics": stats
        }

    except Exception as e:
        logger.error(f"Error retrieving audit statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")
