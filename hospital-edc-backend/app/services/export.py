"""数据导出服务：一键导出可分析数据表 + 数据字典（M3 北极星）。

- build_patient_table    患者主表（一行一患者）
- build_visit_wide_table 访视宽表（一行=一患者一次访视，体格+化验+合并症+费用+量表总分横向平铺）
- build_medication_table 用药长表
- build_ae_table         不良事件长表
- build_data_dictionary  数据字典
- to_excel / to_csv_zip  多 sheet Excel / CSV 打包
"""
import io
import zipfile
from datetime import date, datetime

import pandas as pd
from sqlalchemy.orm import Session, joinedload

from app.models.center import Center
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.forms import PhysicalExam, LabResults, Comorbidity, CostIndicator
from app.models.medication import Medication
from app.models.questionnaire import Questionnaire
from app.models.adverse_event import AdverseEvent
from app.services.scoring import calc_phq9_level, calc_gad7_level
from app.utils.crypto import decrypt, mask

GENDER_LABEL = {"male": "男", "female": "女"}
EDUCATION_LABEL = {1: "文盲", 2: "小学", 3: "中学", 4: "大学"}
EMPLOYMENT_LABEL = {1: "在职", 2: "无工作", 3: "退休"}
INSURANCE_LABEL = {1: "无", 2: "商保", 3: "社保", 4: "均有"}
MARITAL_LABEL = {1: "未婚", 2: "已婚", 3: "离异", 4: "丧偶"}
SMOKING_LABEL = {1: "不吸烟", 2: "曾经吸烟", 3: "目前吸烟"}
DRINKING_LABEL = {1: "不饮酒", 2: "既往饮酒", 3: "社交饮酒", 4: "大量饮酒"}
PATIENT_STATUS_LABEL = {"enrolled": "在研", "completed": "已完成", "dropout": "脱落", "withdrawn": "退出"}
VISIT_STATUS_LABEL = {"draft": "草稿", "submitted": "待审核", "qc_passed": "质控通过", "signed": "已签名", "locked": "已锁定"}
SEVERITY_LABEL = {"mild": "轻度", "moderate": "中度", "severe": "重度"}
RELATION_LABEL = {"definite": "肯定有关", "probable": "很可能有关", "possible": "可能有关",
                  "unlikely": "可能无关", "unrelated": "肯定无关"}
OUTCOME_LABEL = {"recovered": "已恢复", "recovering": "恢复中", "not_recovered": "未恢复",
                 "death": "死亡", "unknown": "不详"}


def _label(mapping, value):
    if value is None:
        return None
    return mapping.get(value, str(value))


def _query_patients(db: Session, center_ids, status_filter=None):
    q = db.query(Patient).options(joinedload(Patient.center))
    if center_ids is not None:
        q = q.filter(Patient.center_id.in_(center_ids))
    if status_filter:
        q = q.filter(Patient.status.in_(status_filter))
    return q.order_by(Patient.patient_code).all()


def build_patient_table(db: Session, center_ids, deidentify: bool = True,
                        status_filter=None) -> pd.DataFrame:
    """患者主表：一行一患者。deidentify=True 时姓名/身份证脱敏。"""
    rows = []
    for p in _query_patients(db, center_ids, status_filter):
        full_name = decrypt(p.full_name_encrypted)
        id_card = decrypt(p.id_card_encrypted)
        rows.append({
            "patient_code": p.patient_code,
            "center_code": p.center_code,
            "center_name": p.center.center_name if p.center else None,
            "full_name": mask(full_name, 1) if deidentify else full_name,
            "id_card": mask(id_card, 3) if deidentify else id_card,
            "phone": mask(p.phone, 3) if deidentify else p.phone,
            "name_initials": p.name_initials,
            "gender": _label(GENDER_LABEL, p.gender),
            "age": p.age,
            "marital_status": _label(MARITAL_LABEL, p.marital_status),
            "employment_status": _label(EMPLOYMENT_LABEL, p.employment_status),
            "education_level": _label(EDUCATION_LABEL, p.education_level),
            "insurance_coverage": _label(INSURANCE_LABEL, p.insurance_coverage),
            "smoking_status": _label(SMOKING_LABEL, p.smoking_status),
            "smoking_per_day": p.smoking_per_day,
            "drinking_status": _label(DRINKING_LABEL, p.drinking_status),
            "drinking_per_day": p.drinking_per_day,
            "enrollment_date": p.enrollment_date,
            "consent_date": p.consent_date,
            "status": _label(PATIENT_STATUS_LABEL, p.status),
            "withdraw_reason": p.withdraw_reason,
            "withdraw_date": p.withdraw_date,
        })
    return pd.DataFrame(rows)


def build_visit_wide_table(db: Session, center_ids, status_filter=None,
                           visit_status=None) -> pd.DataFrame:
    """访视宽表：一行 = 一患者一次访视。量表只取总分/分级。"""
    vq = (
        db.query(Visit)
        .join(Patient)
        .options(
            joinedload(Visit.physical_exam),
            joinedload(Visit.lab_results),
            joinedload(Visit.comorbidities),
            joinedload(Visit.cost_indicators),
            joinedload(Visit.questionnaires),
        )
    )
    if center_ids is not None:
        vq = vq.filter(Patient.center_id.in_(center_ids))
    if visit_status:
        vq = vq.filter(Visit.status.in_(visit_status))

    rows = []
    for v in vq.order_by(Patient.patient_code, Visit.visit_date).all():
        pe = v.physical_exam or PhysicalExam(visit_id=v.id)
        lab = v.lab_results or LabResults(visit_id=v.id)
        cm = v.comorbidities or Comorbidity(visit_id=v.id)
        cost = v.cost_indicators or CostIndicator(visit_id=v.id)
        qmap = {q.questionnaire_type: q for q in (v.questionnaires or [])}
        phq9 = qmap.get("phq9")
        gad7 = qmap.get("gad7")
        eq5d = qmap.get("eq5d")
        dtsq = qmap.get("dtsq")

        phq9_total = phq9.total_score if phq9 else None
        gad7_total = gad7.total_score if gad7 else None

        rows.append({
            "patient_code": v.patient.patient_code,
            "center_code": v.patient.center_code,
            "visit_type": v.visit_type,
            "visit_date": v.visit_date,
            "visit_status": _label(VISIT_STATUS_LABEL, v.status),
            # 体格检查
            "height_cm": pe.height_cm, "weight_kg": pe.weight_kg, "bmi": pe.bmi,
            "waist_cm": pe.waist_cm, "hip_cm": pe.hip_cm,
            "sbp_mmhg": pe.sbp_mmhg, "dbp_mmhg": pe.dbp_mmhg, "heart_rate": pe.heart_rate,
            # 化验
            "fasting_glucose": lab.fasting_glucose, "hba1c": lab.hba1c,
            "tc": lab.tc, "tg": lab.tg, "hdl_c": lab.hdl_c, "ldl_c": lab.ldl_c,
            "alt": lab.alt, "ast": lab.ast, "scr": lab.scr, "egfr": lab.egfr,
            "ua": lab.ua, "bun": lab.bun, "lab_test_date": lab.test_date,
            # 合并症（0=无 1=有）
            "hypertension": cm.hypertension, "ckd": cm.ckd, "chd": cm.chd,
            "angina": cm.angina, "mi": cm.mi, "stroke": cm.stroke,
            "dr": cm.dr, "dn": cm.dn, "df": cm.df,
            # 费用
            "drug_cost": cost.drug_cost, "lab_cost": cost.lab_cost,
            "service_cost": cost.service_cost, "supply_cost": cost.supply_cost,
            "other_cost": cost.other_cost,
            # 量表总分/分级
            "phq9_total": phq9_total,
            "phq9_level": calc_phq9_level(int(phq9_total)) if phq9_total is not None else None,
            "gad7_total": gad7_total,
            "gad7_level": calc_gad7_level(int(gad7_total)) if gad7_total is not None else None,
            "eq5d_mobility": eq5d.eq_mobility if eq5d else None,
            "eq5d_self_care": eq5d.eq_self_care if eq5d else None,
            "eq5d_usual_activity": eq5d.eq_usual_activity if eq5d else None,
            "eq5d_pain": eq5d.eq_pain if eq5d else None,
            "eq5d_anxiety": eq5d.eq_anxiety if eq5d else None,
            "eq5d_vas": eq5d.eq_vas_score if eq5d else None,
            "dtsq_total": (sum(getattr(dtsq, f"q{i}") or 0 for i in range(1, 10))
                           if dtsq else None),
        })
    return pd.DataFrame(rows)


def build_medication_table(db: Session, center_ids, visit_status=None) -> pd.DataFrame:
    """用药长表：一行一条用药记录。"""
    q = (
        db.query(Medication)
        .join(Visit)
        .join(Patient)
    )
    if center_ids is not None:
        q = q.filter(Patient.center_id.in_(center_ids))
    if visit_status:
        q = q.filter(Visit.status.in_(visit_status))
    rows = []
    for m in q.order_by(Patient.patient_code, Visit.visit_date).all():
        rows.append({
            "patient_code": m.visit.patient.patient_code,
            "center_code": m.visit.patient.center_code,
            "visit_type": m.visit.visit_type,
            "visit_date": m.visit.visit_date,
            "treatment_type": m.treatment_type,
            "drug_name": m.drug_name,
            "route": m.route,
            "dose": m.dose,
            "frequency": m.frequency,
            "start_date": m.start_date,
            "end_date": m.end_date,
            "is_ongoing": m.is_ongoing,
        })
    return pd.DataFrame(rows)


def build_ae_table(db: Session, center_ids) -> pd.DataFrame:
    """不良事件长表。"""
    q = db.query(AdverseEvent).join(Patient)
    if center_ids is not None:
        q = q.filter(Patient.center_id.in_(center_ids))
    rows = []
    for ae in q.order_by(Patient.patient_code, AdverseEvent.onset_date).all():
        rows.append({
            "patient_code": ae.patient.patient_code,
            "center_code": ae.patient.center_code,
            "term": ae.term,
            "onset_date": ae.onset_date,
            "end_date": ae.end_date,
            "severity": _label(SEVERITY_LABEL, ae.severity),
            "is_serious": ae.is_serious,
            "relation": _label(RELATION_LABEL, ae.relation),
            "outcome": _label(OUTCOME_LABEL, ae.outcome),
            "action_taken": ae.action_taken,
            "description": ae.description,
        })
    return pd.DataFrame(rows)


# ── 数据字典 ─────────────────────────────────────────

def build_data_dictionary() -> pd.DataFrame:
    """变量名 / 中文含义 / 所属表 / 类型 / 取值编码 / 单位。"""
    D = []
    def add(sheet, var, meaning, vtype, codes=None, unit=None):
        D.append({"sheet": sheet, "变量名": var, "中文含义": meaning,
                  "类型": vtype, "取值编码": codes or "", "单位": unit or ""})

    # 患者主表
    add("患者主表", "patient_code", "患者编号（中心前缀-4位流水，如 TJ01-0001）", "字符串")
    add("患者主表", "center_code", "中心编号", "字符串", "TJ-01~TJ-07")
    add("患者主表", "center_name", "中心名称", "字符串")
    add("患者主表", "full_name", "患者姓名（脱敏=首字+****）", "字符串")
    add("患者主表", "id_card", "身份证号（脱敏=前3位+****）", "字符串")
    add("患者主表", "phone", "联系电话（脱敏=前3位+****）", "字符串")
    add("患者主表", "gender", "性别", "字符串", "男/女")
    add("患者主表", "age", "年龄", "整数", unit="岁")
    add("患者主表", "marital_status", "婚姻状况", "字符串", "1未婚 2已婚 3离异 4丧偶")
    add("患者主表", "employment_status", "就业状况", "字符串", "1在职 2无工作 3退休")
    add("患者主表", "education_level", "文化程度", "字符串", "1文盲 2小学 3中学 4大学")
    add("患者主表", "insurance_coverage", "医保类型", "字符串", "1无 2商保 3社保 4均有")
    add("患者主表", "smoking_status", "吸烟状况", "字符串", "1不吸烟 2曾经 3目前")
    add("患者主表", "smoking_per_day", "每日吸烟量", "整数", unit="支")
    add("患者主表", "drinking_status", "饮酒状况", "字符串", "1不 2既往 3社交 4大量")
    add("患者主表", "drinking_per_day", "每日饮酒量", "整数")
    add("患者主表", "enrollment_date", "入组日期", "日期")
    add("患者主表", "consent_date", "知情同意日期", "日期")
    add("患者主表", "status", "入组状态", "字符串", "在研/已完成/脱落/退出")
    add("患者主表", "withdraw_reason", "退出/脱落原因", "文本")
    add("患者主表", "withdraw_date", "退出/脱落日期", "日期")

    # 访视宽表
    add("访视宽表", "patient_code", "患者编号（与患者主表关联）", "字符串")
    add("访视宽表", "center_code", "中心编号", "字符串", "TJ-01~TJ-07")
    add("访视宽表", "visit_type", "访视类型", "字符串", "baseline/M6/M12/M18/M24")
    add("访视宽表", "visit_date", "访视日期", "日期")
    add("访视宽表", "visit_status", "访视状态", "字符串", "草稿/待审核/质控通过/已签名/已锁定")
    add("访视宽表", "height_cm", "身高", "小数", unit="cm")
    add("访视宽表", "weight_kg", "体重", "小数", unit="kg")
    add("访视宽表", "bmi", "体质指数（自动计算）", "小数", unit="kg/m²")
    add("访视宽表", "waist_cm", "腰围", "小数", unit="cm")
    add("访视宽表", "hip_cm", "臀围", "小数", unit="cm")
    add("访视宽表", "sbp_mmhg", "收缩压", "整数", unit="mmHg")
    add("访视宽表", "dbp_mmhg", "舒张压", "整数", unit="mmHg")
    add("访视宽表", "heart_rate", "心率", "整数", unit="次/分")
    add("访视宽表", "fasting_glucose", "空腹血糖", "小数", unit="mmol/L")
    add("访视宽表", "hba1c", "糖化血红蛋白", "小数", unit="%")
    add("访视宽表", "tc", "总胆固醇", "小数", unit="mmol/L")
    add("访视宽表", "tg", "甘油三酯", "小数", unit="mmol/L")
    add("访视宽表", "hdl_c", "高密度脂蛋白胆固醇", "小数", unit="mmol/L")
    add("访视宽表", "ldl_c", "低密度脂蛋白胆固醇", "小数", unit="mmol/L")
    add("访视宽表", "alt", "谷丙转氨酶", "小数", unit="U/L")
    add("访视宽表", "ast", "谷草转氨酶", "小数", unit="U/L")
    add("访视宽表", "scr", "血清肌酐", "小数", unit="μmol/L")
    add("访视宽表", "egfr", "估算肾小球滤过率", "小数")
    add("访视宽表", "ua", "尿酸", "小数", unit="μmol/L")
    add("访视宽表", "bun", "尿素氮", "小数", unit="mmol/L")
    add("访视宽表", "lab_test_date", "化验日期", "日期")
    for var, meaning in [("hypertension", "高血压"), ("ckd", "慢性肾病"), ("chd", "冠心病"),
                         ("angina", "心绞痛"), ("mi", "心肌梗死"), ("stroke", "脑卒中"),
                         ("dr", "糖尿病视网膜病变"), ("dn", "糖尿病神经病变"), ("df", "糖尿病足")]:
        add("访视宽表", var, f"{meaning}（0=无 1=有）", "整数", "0/1")
    add("访视宽表", "drug_cost", "药品费", "小数", unit="元")
    add("访视宽表", "lab_cost", "检查化验费", "小数", unit="元")
    add("访视宽表", "service_cost", "诊疗服务费", "小数", unit="元")
    add("访视宽表", "supply_cost", "耗材费", "小数", unit="元")
    add("访视宽表", "other_cost", "其他费用", "小数", unit="元")
    add("访视宽表", "phq9_total", "PHQ-9 抑郁量表总分", "整数", "0-27")
    add("访视宽表", "phq9_level", "PHQ-9 分级", "字符串", "无/极轻微抑郁、轻度抑郁、中度抑郁、中重度抑郁、重度抑郁")
    add("访视宽表", "gad7_total", "GAD-7 焦虑量表总分", "整数", "0-21")
    add("访视宽表", "gad7_level", "GAD-7 分级", "字符串", "无焦虑症状、轻度焦虑、中度焦虑、重度焦虑")
    for var, meaning in [("eq5d_mobility", "EQ-5D 行动能力"), ("eq5d_self_care", "EQ-5D 自我照顾"),
                         ("eq5d_usual_activity", "EQ-5D 日常活动"), ("eq5d_pain", "EQ-5D 疼痛/不舒服"),
                         ("eq5d_anxiety", "EQ-5D 焦虑/沮丧")]:
        add("访视宽表", var, meaning, "整数", "1无困难~5无法/极度严重（5级）")
    add("访视宽表", "eq5d_vas", "EQ-5D 健康视觉模拟评分", "整数", "0最差~100最好")
    add("访视宽表", "dtsq_total", "DTSQ 糖尿病治疗满意度总分", "整数", "9-45（9题各1-5分）")

    # 用药表
    add("用药表", "patient_code", "患者编号（与患者主表关联）", "字符串")
    add("用药表", "center_code", "中心编号", "字符串")
    add("用药表", "visit_type", "访视类型", "字符串", "baseline/M6/M12/M18/M24")
    add("用药表", "visit_date", "访视日期", "日期")
    add("用药表", "treatment_type", "治疗类别", "字符串", "糖尿病/高血压/降脂/抗血小板/抗凝/其他")
    add("用药表", "drug_name", "药品名称", "字符串")
    add("用药表", "route", "给药途径", "字符串", "口服/皮下注射/静脉注射/吸入/局部")
    add("用药表", "dose", "剂量", "字符串")
    add("用药表", "frequency", "频次", "字符串", "QD/BID/TID/QW/Q2W/QM/PRN")
    add("用药表", "start_date", "开始日期", "日期")
    add("用药表", "end_date", "结束日期", "日期")
    add("用药表", "is_ongoing", "是否仍在使用", "布尔", "0/1")

    # AE 表
    add("不良事件表", "patient_code", "患者编号（与患者主表关联）", "字符串")
    add("不良事件表", "center_code", "中心编号", "字符串")
    add("不良事件表", "term", "不良事件名称", "字符串")
    add("不良事件表", "onset_date", "发生日期", "日期")
    add("不良事件表", "end_date", "结束日期", "日期")
    add("不良事件表", "severity", "严重程度", "字符串", "轻度/中度/重度")
    add("不良事件表", "is_serious", "是否严重不良事件（SAE）", "布尔", "0/1")
    add("不良事件表", "relation", "与研究药物关系", "字符串", "肯定有关/很可能有关/可能有关/可能无关/肯定无关")
    add("不良事件表", "outcome", "转归", "字符串", "已恢复/恢复中/未恢复/死亡/不详")
    add("不良事件表", "action_taken", "采取的措施", "字符串")
    add("不良事件表", "description", "事件描述", "文本")

    return pd.DataFrame(D)


# ── 输出格式 ─────────────────────────────────────────

def build_all_tables(db: Session, center_ids, deidentify: bool = True,
                     status_filter=None, visit_status=None) -> dict:
    """构建全部导出表。"""
    return {
        "患者主表": build_patient_table(db, center_ids, deidentify, status_filter),
        "访视宽表": build_visit_wide_table(db, center_ids, status_filter, visit_status),
        "用药表": build_medication_table(db, center_ids, visit_status),
        "不良事件表": build_ae_table(db, center_ids),
        "数据字典": build_data_dictionary(),
    }


def to_excel(tables: dict) -> bytes:
    """多 sheet Excel（每个 sheet ≤31 字符）。"""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, df in tables.items():
            # 空 DataFrame 也要占位，保证 sheet 齐全
            out = df if not df.empty else pd.DataFrame({"（无数据）": []})
            out.to_excel(writer, sheet_name=name[:31], index=False)
    return buf.getvalue()


def to_csv_zip(tables: dict) -> bytes:
    """CSV 打包为 zip（UTF-8 BOM，Excel 可直接打开）。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, df in tables.items():
            csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
            zf.writestr(f"{name}.csv", csv_bytes)
    return buf.getvalue()
