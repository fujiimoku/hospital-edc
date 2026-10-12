from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Literal
from datetime import date


# ---- 体格检查 ----
class PhysicalExamIn(BaseModel):
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    waist_cm: Optional[float] = None
    hip_cm: Optional[float] = None
    heart_rate: Optional[int] = None
    sbp_mmhg: Optional[int] = None
    dbp_mmhg: Optional[int] = None


# ---- 实验室检查 ----
class LabResultsIn(BaseModel):
    fasting_glucose: Optional[float] = None
    hba1c: Optional[float] = None
    tc: Optional[float] = None
    tg: Optional[float] = None
    hdl_c: Optional[float] = None
    ldl_c: Optional[float] = None
    alt: Optional[float] = None
    ast: Optional[float] = None
    scr: Optional[float] = None
    egfr: Optional[float] = None
    ua: Optional[float] = None
    bun: Optional[float] = None
    test_date: Optional[date] = None


# ---- 合并症 ----
class ComorbidityIn(BaseModel):
    hypertension: Optional[Literal[0, 1]] = None
    hypertension_date: Optional[str] = None
    hypertension_cause: Optional[str] = None
    ckd: Optional[Literal[0, 1]] = None
    ckd_date: Optional[str] = None
    ckd_cause: Optional[str] = None
    chd: Optional[Literal[0, 1]] = None
    chd_date: Optional[str] = None
    angina: Optional[Literal[0, 1]] = None
    angina_date: Optional[str] = None
    mi: Optional[Literal[0, 1]] = None
    mi_date: Optional[str] = None
    stroke: Optional[Literal[0, 1]] = None
    stroke_date: Optional[str] = None
    # 糖尿病并发症
    dr: Optional[Literal[0, 1]] = None
    dr_date: Optional[str] = None
    dr_macular: Optional[bool] = False
    dr_non_proliferative: Optional[bool] = False
    dr_proliferative: Optional[bool] = False
    dn: Optional[Literal[0, 1]] = None
    dn_date: Optional[str] = None
    dn_peripheral: Optional[bool] = False
    dn_autonomic: Optional[bool] = False
    df: Optional[Literal[0, 1]] = None
    df_date: Optional[str] = None
    df_healed_ulcer: Optional[bool] = False
    df_active_ulcer: Optional[bool] = False


# ---- 核心指标（费用）----
class CostIndicatorIn(BaseModel):
    crf_version: Optional[Literal[1]] = None
    drug_cost: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    lab_cost: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    service_cost: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    supply_cost: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    other_cost: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)


# ---- 药物 ----
class MedicationIn(BaseModel):
    treatment_type: Optional[str] = None
    drug_name: Optional[str] = None
    route: Optional[str] = None
    dose: Optional[str] = None
    frequency: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_ongoing: Optional[bool] = True


class MedicationBatchIn(BaseModel):
    medications: List[MedicationIn]


# ---- 问卷（PHQ-9 / GAD-7 / EQ-5D / DTSQ）----
class QuestionnaireIn(BaseModel):
    crf_version: Optional[Literal[1]] = None
    questionnaire_type: str   # phq9 | gad7 | eq5d | dtsq

    # PHQ-9 / GAD-7
    q1: Optional[int] = None
    q2: Optional[int] = None
    q3: Optional[int] = None
    q4: Optional[int] = None
    q5: Optional[int] = None
    q6: Optional[int] = None
    q7: Optional[int] = None
    q8: Optional[int] = None
    q9: Optional[int] = None

    # EQ-5D
    eq_mobility: Optional[int] = None
    eq_self_care: Optional[int] = None
    eq_usual_activity: Optional[int] = None
    eq_pain: Optional[int] = None
    eq_anxiety: Optional[int] = None
    eq_vas_score: Optional[int] = None

    # DTSQ 开放性文本
    dtsq_open_text: Optional[str] = None

    @model_validator(mode="after")
    def validate_crf_answers(self):
        if self.questionnaire_type == "dtsq":
            for i in range(1, 10):
                value = getattr(self, f"q{i}")
                if value is not None and not 1 <= value <= 5:
                    raise ValueError("DTSQ 选项必须在 1 至 5 之间")
        if self.questionnaire_type == "eq5d":
            for key in ("eq_mobility", "eq_self_care", "eq_usual_activity", "eq_pain", "eq_anxiety"):
                value = getattr(self, key)
                if value is not None and not 1 <= value <= 5:
                    raise ValueError("EQ-5D 选项必须在 1 至 5 之间")
            if self.eq_vas_score is not None and not 0 <= self.eq_vas_score <= 100:
                raise ValueError("健康状况评分必须在 0 至 100 之间")
        return self

    # PHQ-9 就诊症状（逗号分隔字符串）
    phq9_symptoms: Optional[str] = None


# ---- 生活方式 ----
class LifestyleIn(BaseModel):
    diet_scores_json: Optional[str] = None    # JSON 字符串
    exercise_scores_json: Optional[str] = None
    bad_habits: Optional[str] = None          # 逗号分隔
    meal_basic_info_json: Optional[str] = None


# ---- 膳食记录（单条）----
class MealRecordIn(BaseModel):
    meal_time: Optional[str] = None
    dish_name: Optional[str] = None
    ingredients: Optional[str] = None
    raw_cooked: Optional[str] = None
    estimated_amount: Optional[str] = None


class MealRecordBatchIn(BaseModel):
    records: List[MealRecordIn]


class FollowupSafetyIn(BaseModel):
    hypoglycemia: Optional[Literal[1, 2]] = None
    symptomatic: Optional[bool] = None
    nocturnal: Optional[bool] = None
    severe: Optional[bool] = None
    gastrointestinal: Optional[bool] = None
    allergy: Optional[bool] = None
    other: Optional[str] = None
