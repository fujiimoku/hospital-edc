"""统计报表（需求优先级 7、8、2）。

- /enrollment        入组进度：按中心 + 按月累计
- /visit-completion  访视完成率：按中心 / 按访视类型
- /data-completeness 数据完整率：按中心 / 按表单
- /summary           汇总聚合数（分中心也可看全局聚合，但不含患者明细）
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query as FQuery
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_accessible_center_ids
from app.models.center import Center
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.forms import PhysicalExam, LabResults, Comorbidity, CostIndicator
from app.models.questionnaire import Questionnaire
from app.models.adverse_event import AdverseEvent
from app.models.query import Query
from app.models.user import User

router = APIRouter(prefix="/api/reports", tags=["统计报表"])

DONE_STATUSES = ("submitted", "qc_passed", "signed", "locked")


def _center_scope(q, current_user):
    """对带 Patient.center_id 的查询应用中心隔离。"""
    accessible = get_accessible_center_ids(current_user)
    if accessible is not None:
        q = q.filter(Patient.center_id.in_(accessible))
    return q


@router.get("/enrollment")
def enrollment_report(
    center_id: Optional[int] = FQuery(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """入组进度：按中心统计 + 按月累计入组。"""
    accessible = get_accessible_center_ids(current_user)
    if accessible is not None and center_id is not None and center_id not in accessible:
        raise HTTPException(403, "无权查看该中心报表")

    q = db.query(Patient.center_id, Center.center_code, Center.center_name,
                 func.count(Patient.id).label("total")) \
        .outerjoin(Center, Patient.center_id == Center.id)
    if accessible is not None:
        q = q.filter(Patient.center_id.in_(accessible))
    elif center_id is not None:
        q = q.filter(Patient.center_id == center_id)
    by_center = [
        {"center_id": r.center_id, "center_code": r.center_code or "-",
         "center_name": r.center_name or "未分配", "total": r.total}
        for r in q.group_by(Patient.center_id, Center.center_code, Center.center_name) \
                  .order_by(Center.center_code).all()
    ]

    # 按月累计（入组日期）
    qm = db.query(Patient.enrollment_date).filter(Patient.enrollment_date.isnot(None))
    if accessible is not None:
        qm = qm.filter(Patient.center_id.in_(accessible))
    elif center_id is not None:
        qm = qm.filter(Patient.center_id == center_id)
    month_count = {}
    for (d,) in qm.all():
        key = f"{d.year:04d}-{d.month:02d}"
        month_count[key] = month_count.get(key, 0) + 1
    by_month, cum = [], 0
    for key in sorted(month_count):
        cum += month_count[key]
        by_month.append({"month": key, "count": month_count[key], "cumulative": cum})

    # 状态分布
    qs = db.query(Patient.status, func.count(Patient.id))
    if accessible is not None:
        qs = qs.filter(Patient.center_id.in_(accessible))
    elif center_id is not None:
        qs = qs.filter(Patient.center_id == center_id)
    status_dist = {s or "enrolled": c for s, c in qs.group_by(Patient.status).all()}

    return {"by_center": by_center, "by_month": by_month, "status_dist": status_dist}


@router.get("/visit-completion")
def visit_completion_report(
    center_id: Optional[int] = FQuery(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """访视完成率：按访视类型 × 状态统计（完成=已提交及之后的状态）。"""
    accessible = get_accessible_center_ids(current_user)
    if accessible is not None and center_id is not None and center_id not in accessible:
        raise HTTPException(403, "无权查看该中心报表")

    q = db.query(Visit.visit_type, Visit.status, func.count(Visit.id)) \
        .join(Patient, Visit.patient_id == Patient.id)
    if accessible is not None:
        q = q.filter(Patient.center_id.in_(accessible))
    elif center_id is not None:
        q = q.filter(Patient.center_id == center_id)
    rows = q.group_by(Visit.visit_type, Visit.status).all()

    stats = {}
    for visit_type, status_, cnt in rows:
        s = stats.setdefault(visit_type, {"total": 0, "done": 0, "by_status": {}})
        s["total"] += cnt
        s["by_status"][status_] = cnt
        if status_ in DONE_STATUSES:
            s["done"] += cnt
    result = []
    for vt in ("baseline", "M6", "M12", "M18", "M24"):
        if vt not in stats:
            continue
        s = stats[vt]
        result.append({
            "visit_type": vt,
            "total": s["total"],
            "done": s["done"],
            "rate": round(s["done"] / s["total"] * 100, 1) if s["total"] else 0,
            "by_status": s["by_status"],
        })
    return {"items": result}


@router.get("/data-completeness")
def data_completeness_report(
    center_id: Optional[int] = FQuery(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """数据完整率：各表单（体格/化验/合并症/费用/量表）在访视中的填写比例。"""
    accessible = get_accessible_center_ids(current_user)
    if accessible is not None and center_id is not None and center_id not in accessible:
        raise HTTPException(403, "无权查看该中心报表")

    visit_q = db.query(Visit.id).join(Patient, Visit.patient_id == Patient.id)
    if accessible is not None:
        visit_q = visit_q.filter(Patient.center_id.in_(accessible))
    elif center_id is not None:
        visit_q = visit_q.filter(Patient.center_id == center_id)
    visit_ids = [v.id for v in visit_q.all()]
    total = len(visit_ids)
    if not total:
        return {"total_visits": 0, "forms": []}

    def _count(model, distinct_visit=False):
        q = db.query(model.visit_id).filter(model.visit_id.in_(visit_ids))
        if distinct_visit:
            return q.distinct().count()
        return q.count()

    forms = [
        {"form": "physical_exam", "label": "体格检查", "filled": _count(PhysicalExam)},
        {"form": "lab_results", "label": "实验室检查", "filled": _count(LabResults)},
        {"form": "comorbidity", "label": "合并症", "filled": _count(Comorbidity)},
        {"form": "cost_indicators", "label": "费用指标", "filled": _count(CostIndicator)},
        # 一次访视可有多份量表（PHQ-9/GAD-7/EQ-5D/DTSQ），按"至少填了一份"计
        {"form": "questionnaires", "label": "量表问卷", "filled": _count(Questionnaire, distinct_visit=True)},
    ]
    for f in forms:
        f["rate"] = round(f["filled"] / total * 100, 1)
    return {"total_visits": total, "forms": forms}


@router.get("/summary")
def summary_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """全局聚合汇总数（所有角色可见，只有中心级计数，不含患者明细）。

    需求 3.3：分中心可看全局聚合数。
    """
    patient_by_center = db.query(Patient.center_id, func.count(Patient.id)) \
        .group_by(Patient.center_id).all()
    visit_by_status = db.query(Visit.status, func.count(Visit.id)) \
        .group_by(Visit.status).all()
    total_ae = db.query(func.count(AdverseEvent.id)).scalar()
    open_queries = db.query(func.count(Query.id)).filter(Query.status == "open").all()[0][0]
    centers = db.query(Center).filter(Center.is_active == True).count()

    today = date.today()
    month_start = date(today.year, today.month, 1)
    enrolled_this_month = db.query(func.count(Patient.id)).filter(
        Patient.enrollment_date >= month_start
    ).scalar()

    return {
        "centers_active": centers,
        "patients_by_center": [
            {"center_id": cid, "total": cnt} for cid, cnt in patient_by_center
        ],
        "patients_total": sum(cnt for _, cnt in patient_by_center),
        "patients_enrolled_this_month": enrolled_this_month,
        "visits_by_status": {s: c for s, c in visit_by_status},
        "visits_total": sum(c for _, c in visit_by_status),
        "adverse_events_total": total_ae,
        "open_queries": open_queries,
    }
