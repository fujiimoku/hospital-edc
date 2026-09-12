"""质控审计页聚合接口：把分散在各患者访视里的待办质控集中到一处。

只返回"待办"：
- queries：状态 ∈ {open, answered} 的质疑（附患者/中心上下文）
- visits：状态 ∈ {submitted, qc_passed, signed} 的访视（附 open 质疑数）

所有写操作（答疑/关闭/通过/签名/锁定）复用 queries / visits 现有端点，
本模块只做只读聚合，中心隔离与其它列表接口一致。
"""
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_accessible_center_ids
from app.models.center import Center
from app.models.patient import Patient
from app.models.query import Query
from app.models.visit import Visit
from app.models.user import User

router = APIRouter(prefix="/api/review", tags=["质控审计"])

PENDING_QUERY_STATUSES = ("open", "answered")
PENDING_VISIT_STATUSES = ("submitted", "qc_passed", "signed")


@router.get("/queue")
def review_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """待办质控一览（质疑 + 访视状态流转），按登录用户中心隔离。"""
    accessible = get_accessible_center_ids(current_user)

    # ── 待办质疑（open=待研究者答复，answered=待质控关闭）──
    q_query = (
        db.query(Query, Visit, Patient, Center.center_code)
        .join(Visit, Query.visit_id == Visit.id)
        .join(Patient, Visit.patient_id == Patient.id)
        .outerjoin(Center, Patient.center_id == Center.id)
        .filter(Query.status.in_(PENDING_QUERY_STATUSES))
    )
    if accessible is not None:
        q_query = q_query.filter(Patient.center_id.in_(accessible))
    queries = [
        {
            "id": q.id,
            "visit_id": q.visit_id,
            "field_name": q.field_name,
            "content": q.content,
            "status": q.status,
            "answer": q.answer,
            "created_at": q.created_at,
            "patient_id": p.id,
            "patient_code": p.patient_code,
            "name_initials": p.name_initials,
            "visit_type": v.visit_type,
            "visit_date": v.visit_date,
            "visit_status": v.status,
            "center_code": center_code or p.center_code or "-",
        }
        for q, v, p, center_code in q_query.order_by(Query.created_at.desc()).all()
    ]

    # ── 待办访视（submitted=待质控审核，qc_passed=待签名，signed=待锁定）──
    open_by_visit = dict(
        db.query(Query.visit_id, func.count(Query.id))
        .filter(Query.status == "open")
        .group_by(Query.visit_id)
        .all()
    )
    v_query = (
        db.query(Visit, Patient, Center.center_code)
        .join(Patient, Visit.patient_id == Patient.id)
        .outerjoin(Center, Patient.center_id == Center.id)
        .filter(Visit.status.in_(PENDING_VISIT_STATUSES))
    )
    if accessible is not None:
        v_query = v_query.filter(Patient.center_id.in_(accessible))
    visits = [
        {
            "id": v.id,
            "patient_id": p.id,
            "patient_code": p.patient_code,
            "name_initials": p.name_initials,
            "visit_type": v.visit_type,
            "visit_date": v.visit_date,
            "status": v.status,
            "center_code": center_code or p.center_code or "-",
            "open_queries": open_by_visit.get(v.id, 0),
        }
        for v, p, center_code in v_query.order_by(Visit.updated_at.desc()).all()
    ]

    counts = {
        "to_answer": sum(1 for q in queries if q["status"] == "open"),
        "to_close": sum(1 for q in queries if q["status"] == "answered"),
        "to_review": sum(1 for v in visits if v["status"] == "submitted"),
        "to_sign": sum(1 for v in visits if v["status"] == "qc_passed"),
        "to_lock": sum(1 for v in visits if v["status"] == "signed"),
    }
    return {"queries": queries, "visits": visits, "counts": counts}
