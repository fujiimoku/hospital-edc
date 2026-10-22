import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.visit import Visit
from app.models.forms import PhysicalExam, LabResults, Comorbidity, CostIndicator, FollowupSafety
from app.models.medication import Medication
from app.models.questionnaire import Questionnaire
from app.models.lifestyle import LifestyleAssessment, MealRecord
from app.schemas.forms import (
    PhysicalExamIn, LabResultsIn, ComorbidityIn, CostIndicatorIn, FollowupSafetyIn,
    MedicationBatchIn, QuestionnaireIn, LifestyleIn, MealRecordBatchIn,
)
from app.dependencies import get_current_user, get_accessible_center_ids
from app.services.scoring import (
    calc_phq9_level, calc_gad7_level,
    calc_diet_level, calc_exercise_level,
)
from app.services.validation import check_physical_exam, check_lab_results
from app.services.audit import log_change, diff_model

def _get_visit_with_access(visit_id: int, db: Session, current_user, for_update=False) -> Visit:
    query = db.query(Visit).filter(Visit.id == visit_id)
    if for_update:
        query = query.populate_existing().with_for_update()
    visit = query.first()
    if not visit:
        raise HTTPException(404, "访视记录不存在")
    accessible = get_accessible_center_ids(current_user)
    if accessible is not None and visit.patient.center_id not in accessible:
        raise HTTPException(403, "无权访问该访视")
    return visit


def _require_visit_access(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """所有表单端点（包括读取）都必须验证访视所属中心。"""
    return _get_visit_with_access(visit_id, db, current_user)


router = APIRouter(
    prefix="/api/visits", tags=["表单录入"],
    dependencies=[Depends(_require_visit_access)],
)


#  辅助函数
def _get_unlocked_visit(visit_id: int, db: Session, current_user=None) -> Visit:
    if current_user.role not in ("researcher", "center_admin", "main_admin"):
        raise HTTPException(403, "需要研究者权限")
    visit = _get_visit_with_access(visit_id, db, current_user, for_update=True)
    if visit.status != "draft":
        raise HTTPException(400, "仅草稿访视可修改；待审核可选择原因后自行撤回，已审核须由总管理员退回更正")
    return visit


def _upsert(db: Session, model_cls, filter_kwargs: dict, data: dict, current_user=None, *, audit_center_id=None):
    obj = db.query(model_cls).filter_by(**filter_kwargs).first()
    if obj:
        diff = diff_model(obj, data)
        for k, v in data.items():
            setattr(obj, k, v)
        if diff and current_user is not None:
            log_change(db, current_user, model_cls.__tablename__, obj.id, diff, "update", center_id=audit_center_id)
    else:
        obj = model_cls(**filter_kwargs, **data)
        db.add(obj)
        db.flush()
        if current_user is not None:
            log_change(db, current_user, model_cls.__tablename__, obj.id,
                       {k: (None, v) for k, v in data.items()}, "create", center_id=audit_center_id)
    db.commit()
    db.refresh(obj)
    return obj


def _to_dict(obj):
    if obj is None:
        return None
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


#  体格检查 
@router.get("/{visit_id}/physical-exam")
def get_physical_exam(visit_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    obj = db.query(PhysicalExam).filter(PhysicalExam.visit_id == visit_id).first()
    if not obj:
        raise HTTPException(404, "暂无体格检查数据")
    return _to_dict(obj)


@router.post("/{visit_id}/physical-exam")
def save_physical_exam(visit_id: int, data: PhysicalExamIn, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    _get_unlocked_visit(visit_id, db, current_user)
    payload = data.model_dump(exclude_unset=True)
    existing = db.query(PhysicalExam).filter_by(visit_id=visit_id).first()
    h_cm = payload.get("height_cm") or (existing.height_cm if existing else None)
    w_kg = payload.get("weight_kg") or (existing.weight_kg if existing else None)
    if h_cm and w_kg:
        payload["bmi"] = round(w_kg / ((h_cm / 100) ** 2), 1)
    _upsert(db, PhysicalExam, {"visit_id": visit_id}, payload, current_user)
    return {
        "message": "体格检查保存成功",
        "bmi": payload.get("bmi"),
        "warnings": check_physical_exam(payload),
    }


#  实验室检查 
@router.get("/{visit_id}/lab-results")
def get_lab_results(visit_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    obj = db.query(LabResults).filter(LabResults.visit_id == visit_id).first()
    if not obj:
        raise HTTPException(404, "暂无实验室检查数据")
    return _to_dict(obj)


@router.post("/{visit_id}/lab-results")
def save_lab_results(visit_id: int, data: LabResultsIn, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    _get_unlocked_visit(visit_id, db, current_user)
    payload = data.model_dump(exclude_unset=True)
    _upsert(db, LabResults, {"visit_id": visit_id}, payload, current_user)
    return {"message": "实验室检查保存成功", "warnings": check_lab_results(payload)}


#  合并症 
@router.get("/{visit_id}/comorbidity")
def get_comorbidity(visit_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    obj = db.query(Comorbidity).filter(Comorbidity.visit_id == visit_id).first()
    if not obj:
        raise HTTPException(404, "暂无合并症数据")
    return _to_dict(obj)


@router.post("/{visit_id}/comorbidity")
def save_comorbidity(visit_id: int, data: ComorbidityIn, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    _get_unlocked_visit(visit_id, db, current_user)
    _upsert(db, Comorbidity, {"visit_id": visit_id}, data.model_dump(exclude_unset=True), current_user)
    return {"message": "合并症保存成功"}


#  核心指标（费用）
@router.get("/{visit_id}/cost-indicators")
def get_cost_indicators(visit_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    obj = db.query(CostIndicator).filter(CostIndicator.visit_id == visit_id).first()
    if not obj:
        raise HTTPException(404, "暂无费用数据")
    return _to_dict(obj)


@router.post("/{visit_id}/cost-indicators")
def save_cost_indicators(visit_id: int, data: CostIndicatorIn, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    _get_unlocked_visit(visit_id, db, current_user)
    _upsert(db, CostIndicator, {"visit_id": visit_id}, data.model_dump(exclude_unset=True), current_user)
    return {"message": "费用数据保存成功"}


#  药物治疗（批量）
@router.get("/{visit_id}/medications")
def get_medications(visit_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return [_to_dict(m) for m in db.query(Medication).filter(Medication.visit_id == visit_id).all()]


@router.post("/{visit_id}/medications")
def save_medications(visit_id: int, data: MedicationBatchIn, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    visit = _get_unlocked_visit(visit_id, db, current_user)
    old_rows = db.query(Medication).filter_by(visit_id=visit_id).order_by(Medication.id).all()
    fields = list(type(data.medications[0]).model_fields) if data.medications else [c.name for c in Medication.__table__.columns if c.name not in ("id", "visit_id", "created_at")]
    before = [{k: getattr(row, k) for k in fields} for row in old_rows]
    after = [row.model_dump() for row in data.medications]
    old_json = json.dumps(before, ensure_ascii=False, sort_keys=True, default=str)
    new_json = json.dumps(after, ensure_ascii=False, sort_keys=True, default=str)
    if old_json != new_json:
        log_change(db, current_user, "visits", visit_id,
                   {"medications": (old_json, new_json)}, center_id=visit.patient.center_id)
    db.query(Medication).filter(Medication.visit_id == visit_id).delete()
    for med in data.medications:
        db.add(Medication(visit_id=visit_id, **med.model_dump(exclude_unset=True)))
    db.commit()
    return {"message": f"药物记录保存成功，共 {len(data.medications)} 条"}


#  问卷（PHQ-9 / GAD-7 / EQ-5D / DTSQ）
@router.get("/{visit_id}/questionnaire/{q_type}")
def get_questionnaire(visit_id: int, q_type: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    obj = db.query(Questionnaire).filter_by(visit_id=visit_id, questionnaire_type=q_type).first()
    if not obj:
        raise HTTPException(404, f"暂无 {q_type} 数据")
    return _to_dict(obj)


@router.post("/{visit_id}/questionnaire")
def save_questionnaire(visit_id: int, data: QuestionnaireIn, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    visit = _get_unlocked_visit(visit_id, db, current_user)
    payload = data.model_dump(exclude_unset=True)
    q_type = data.questionnaire_type
    if q_type == "phq9":
        payload["total_score"] = sum(payload.get(f"q{i}", 0) or 0 for i in range(1, 10))
    elif q_type == "gad7":
        payload["total_score"] = sum(payload.get(f"q{i}", 0) or 0 for i in range(1, 8))
    _upsert(db, Questionnaire, {"visit_id": visit_id, "questionnaire_type": q_type},
            {k: v for k, v in payload.items() if k != "questionnaire_type"}, current_user,
            audit_center_id=visit.patient.center_id)
    result = {"message": f"{q_type} 保存成功"}
    if q_type == "phq9":
        result["total_score"] = payload["total_score"]
        result["level"] = calc_phq9_level(int(payload["total_score"]))
    elif q_type == "gad7":
        result["total_score"] = payload["total_score"]
        result["level"] = calc_gad7_level(int(payload["total_score"]))
    return result


#  生活方式评估 
@router.get("/{visit_id}/lifestyle")
def get_lifestyle(visit_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    obj = db.query(LifestyleAssessment).filter(LifestyleAssessment.visit_id == visit_id).first()
    if not obj:
        raise HTTPException(404, "暂无生活方式评估数据")
    return _to_dict(obj)


@router.post("/{visit_id}/lifestyle")
def save_lifestyle(visit_id: int, data: LifestyleIn, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    _get_unlocked_visit(visit_id, db, current_user)
    payload = data.model_dump(exclude_unset=True)
    if "diet_scores_json" in payload:
        scores = json.loads(payload["diet_scores_json"])
        total = sum(scores) if isinstance(scores, list) else sum(scores.values())
        payload["diet_total"] = total
        payload["diet_level"] = calc_diet_level(total)
    if "exercise_scores_json" in payload:
        scores = json.loads(payload["exercise_scores_json"])
        total = sum(scores) if isinstance(scores, list) else sum(scores.values())
        payload["exercise_total"] = total
        payload["exercise_level"] = calc_exercise_level(total)
    _upsert(db, LifestyleAssessment, {"visit_id": visit_id}, payload, current_user)
    return {
        "message": "生活方式评估保存成功",
        "diet_total": payload.get("diet_total"),
        "diet_level": payload.get("diet_level"),
        "exercise_total": payload.get("exercise_total"),
        "exercise_level": payload.get("exercise_level"),
    }


#  膳食记录（批量）
@router.get("/{visit_id}/meal-records")
def get_meal_records(visit_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return [_to_dict(r) for r in db.query(MealRecord).filter(MealRecord.visit_id == visit_id).all()]


@router.post("/{visit_id}/meal-records")
def save_meal_records(visit_id: int, data: MealRecordBatchIn, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    visit = _get_unlocked_visit(visit_id, db, current_user)
    old_rows = db.query(MealRecord).filter_by(visit_id=visit_id).order_by(MealRecord.id).all()
    fields = list(type(data.records[0]).model_fields) if data.records else [c.name for c in MealRecord.__table__.columns if c.name not in ("id", "visit_id", "created_at")]
    before = [{k: getattr(row, k) for k in fields} for row in old_rows]
    after = [row.model_dump() for row in data.records]
    old_json = json.dumps(before, ensure_ascii=False, sort_keys=True, default=str)
    new_json = json.dumps(after, ensure_ascii=False, sort_keys=True, default=str)
    if old_json != new_json:
        log_change(db, current_user, "visits", visit_id,
                   {"meal_records": (old_json, new_json)}, center_id=visit.patient.center_id)
    db.query(MealRecord).filter(MealRecord.visit_id == visit_id).delete()
    for rec in data.records:
        db.add(MealRecord(visit_id=visit_id, **rec.model_dump(exclude_unset=True)))
    db.commit()
    return {"message": f"膳食记录保存成功，共 {len(data.records)} 条"}


# /meals 是 /meal-records 的别名，与 API 表格对齐
@router.get("/{visit_id}/meals")
def get_meals(visit_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return get_meal_records(visit_id, db, current_user)


@router.post("/{visit_id}/meals")
def save_meals(visit_id: int, data: MealRecordBatchIn, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return save_meal_records(visit_id, data, db, current_user)


@router.post("/{visit_id}/followup-safety")
def save_followup_safety(visit_id: int, data: FollowupSafetyIn, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    visit = _get_unlocked_visit(visit_id, db, current_user)
    payload = data.model_dump(exclude_unset=True)
    existing = db.query(FollowupSafety).filter_by(visit_id=visit_id).first()
    merged = {**(_to_dict(existing) or {}), **payload}
    if merged.get("hypoglycemia") != 2 and any(merged.get(k) for k in ("symptomatic", "nocturnal", "severe")):
        raise HTTPException(422, "勾选低血糖类型时，请选择有低血糖")
    _upsert(db, FollowupSafety, {"visit_id": visit_id}, payload, current_user, audit_center_id=visit.patient.center_id)
    return {"message": "不良反应记录已保存"}


#  一次性获取全部表单数据 
@router.get("/{visit_id}/all-forms")
def get_all_forms(visit_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise HTTPException(404, "访视不存在")
    return {
        "visit": _to_dict(visit),
        "followup_safety": _to_dict(db.query(FollowupSafety).filter_by(visit_id=visit_id).first()),
        "physical_exam": _to_dict(db.query(PhysicalExam).filter_by(visit_id=visit_id).first()),
        "lab_results": _to_dict(db.query(LabResults).filter_by(visit_id=visit_id).first()),
        "comorbidity": _to_dict(db.query(Comorbidity).filter_by(visit_id=visit_id).first()),
        "cost_indicators": _to_dict(db.query(CostIndicator).filter_by(visit_id=visit_id).first()),
        "medications": [_to_dict(m) for m in db.query(Medication).filter_by(visit_id=visit_id).all()],
        "questionnaires": {
            q.questionnaire_type: _to_dict(q)
            for q in db.query(Questionnaire).filter_by(visit_id=visit_id).all()
        },
        "lifestyle": _to_dict(db.query(LifestyleAssessment).filter_by(visit_id=visit_id).first()),
        "meal_records": [_to_dict(r) for r in db.query(MealRecord).filter_by(visit_id=visit_id).all()],
    }


@router.get("/{visit_id}/previous-medications")
def previous_medications(visit_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    from sqlalchemy import or_, and_
    current = _get_visit_with_access(visit_id, db, current_user)
    previous = db.query(Visit).filter(Visit.patient_id == current.patient_id,
        or_(Visit.visit_date < current.visit_date, and_(Visit.visit_date == current.visit_date, Visit.id < current.id))
    ).order_by(Visit.visit_date.desc(), Visit.id.desc()).first()
    if previous is None:
        return {"source_visit": None, "medications": []}
    rows = db.query(Medication).filter_by(visit_id=previous.id).order_by(Medication.id).all()
    return {"source_visit": {"id": previous.id, "visit_date": previous.visit_date, "visit_type": previous.visit_type},
            "medications": [{k: v for k, v in _to_dict(row).items() if k not in ('id', 'visit_id', 'created_at')} for row in rows]}
