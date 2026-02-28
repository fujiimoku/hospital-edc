import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.visit import Visit
from app.models.forms import PhysicalExam, LabResults, Comorbidity, CostIndicator
from app.models.medication import Medication
from app.models.questionnaire import Questionnaire
from app.models.lifestyle import LifestyleAssessment, MealRecord
from app.schemas.forms import (
    PhysicalExamIn, LabResultsIn, ComorbidityIn, CostIndicatorIn,
    MedicationBatchIn, QuestionnaireIn, LifestyleIn, MealRecordBatchIn,
)
from app.dependencies import get_current_user
from app.services.scoring import (
    calc_phq9_level, calc_gad7_level,
    calc_diet_level, calc_exercise_level,
)

router = APIRouter(prefix="/api/visits", tags=["表单录入"])


#  辅助函数 
def _get_unlocked_visit(visit_id: int, db: Session) -> Visit:
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise HTTPException(404, "访视记录不存在")
    if visit.status == "locked":
        raise HTTPException(400, "该访视已锁定，无法修改数据")
    return visit


def _upsert(db: Session, model_cls, filter_kwargs: dict, data: dict):
    obj = db.query(model_cls).filter_by(**filter_kwargs).first()
    if obj:
        for k, v in data.items():
            setattr(obj, k, v)
    else:
        obj = model_cls(**filter_kwargs, **data)
        db.add(obj)
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
    _get_unlocked_visit(visit_id, db)
    payload = data.model_dump(exclude_unset=True)
    existing = db.query(PhysicalExam).filter_by(visit_id=visit_id).first()
    h_cm = payload.get("height_cm") or (existing.height_cm if existing else None)
    w_kg = payload.get("weight_kg") or (existing.weight_kg if existing else None)
    if h_cm and w_kg:
        payload["bmi"] = round(w_kg / ((h_cm / 100) ** 2), 1)
    _upsert(db, PhysicalExam, {"visit_id": visit_id}, payload)
    return {"message": "体格检查保存成功", "bmi": payload.get("bmi")}


#  实验室检查 
@router.get("/{visit_id}/lab-results")
def get_lab_results(visit_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    obj = db.query(LabResults).filter(LabResults.visit_id == visit_id).first()
    if not obj:
        raise HTTPException(404, "暂无实验室检查数据")
    return _to_dict(obj)


@router.post("/{visit_id}/lab-results")
def save_lab_results(visit_id: int, data: LabResultsIn, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    _get_unlocked_visit(visit_id, db)
    _upsert(db, LabResults, {"visit_id": visit_id}, data.model_dump(exclude_unset=True))
    return {"message": "实验室检查保存成功"}


#  合并症 
@router.get("/{visit_id}/comorbidity")
def get_comorbidity(visit_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    obj = db.query(Comorbidity).filter(Comorbidity.visit_id == visit_id).first()
    if not obj:
        raise HTTPException(404, "暂无合并症数据")
    return _to_dict(obj)


@router.post("/{visit_id}/comorbidity")
def save_comorbidity(visit_id: int, data: ComorbidityIn, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    _get_unlocked_visit(visit_id, db)
    _upsert(db, Comorbidity, {"visit_id": visit_id}, data.model_dump(exclude_unset=True))
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
    _get_unlocked_visit(visit_id, db)
    _upsert(db, CostIndicator, {"visit_id": visit_id}, data.model_dump(exclude_unset=True))
    return {"message": "费用数据保存成功"}


#  药物治疗（批量）
@router.get("/{visit_id}/medications")
def get_medications(visit_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return [_to_dict(m) for m in db.query(Medication).filter(Medication.visit_id == visit_id).all()]


@router.post("/{visit_id}/medications")
def save_medications(visit_id: int, data: MedicationBatchIn, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    _get_unlocked_visit(visit_id, db)
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
    _get_unlocked_visit(visit_id, db)
    payload = data.model_dump(exclude_unset=True)
    q_type = data.questionnaire_type
    if q_type == "phq9":
        payload["total_score"] = sum(payload.get(f"q{i}", 0) or 0 for i in range(1, 10))
    elif q_type == "gad7":
        payload["total_score"] = sum(payload.get(f"q{i}", 0) or 0 for i in range(1, 8))
    obj = db.query(Questionnaire).filter_by(visit_id=visit_id, questionnaire_type=q_type).first()
    if obj:
        for k, v in payload.items():
            setattr(obj, k, v)
    else:
        obj = Questionnaire(visit_id=visit_id, **payload)
        db.add(obj)
    db.commit()
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
    _get_unlocked_visit(visit_id, db)
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
    _upsert(db, LifestyleAssessment, {"visit_id": visit_id}, payload)
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
    _get_unlocked_visit(visit_id, db)
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


#  一次性获取全部表单数据 
@router.get("/{visit_id}/all-forms")
def get_all_forms(visit_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise HTTPException(404, "访视不存在")
    return {
        "visit": _to_dict(visit),
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