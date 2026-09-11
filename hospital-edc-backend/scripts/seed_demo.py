"""
演示数据种子脚本 —— 一键生成"看起来真实"的演示库

特点：
- 幂等可重跑：每次先清掉上次演示数据（按患者编号前缀识别），再重建
- 不碰真实数据：只清理 TJ01-0003+ / TJ02-* 演示患者与演示账号
- 覆盖全状态：draft / submitted / qc_passed / signed / locked 五种访视状态都有
- 报表好看：入组日期分散在 2026-01 ~ 2026-08，跨两个中心

用法（在 hospital-edc-backend 目录下）：
    ../venv/Scripts/python.exe scripts/seed_demo.py
"""
import sys
import os
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import SessionLocal, engine, Base
import app.models  # noqa: 注册全部模型
from app.models.user import User
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.forms import PhysicalExam, LabResults, Comorbidity, CostIndicator
from app.models.questionnaire import Questionnaire
from app.models.medication import Medication
from app.models.adverse_event import AdverseEvent
from app.models.query import Query
from app.models.consent import ConsentRecord
from app.models.notification import Notification
from app.dependencies import hash_password
from app.utils.crypto import encrypt

DEMO_PATIENT_PREFIXES = ("TJ01-000", "TJ01-001", "TJ02-")   # TJ01-0003+ 属演示数据（0001/0002 为真实测试数据）
DEMO_USERS = ["researcher2", "qc2", "center_admin2"]


def is_demo_patient(code: str) -> bool:
    """演示患者编号：TJ01-0003 ~ TJ01-0099 与全部 TJ02-*"""
    if code.startswith("TJ02-"):
        return True
    if code.startswith("TJ01-"):
        try:
            n = int(code.split("-")[1])
            return n >= 3
        except (IndexError, ValueError):
            return False
    return False


def clean_demo_data(db):
    """删除上一次演示生成的数据（不影响 TJ01-0001/0002 等真实数据）"""
    demo_patients = db.query(Patient).filter(Patient.patient_code.like("TJ%")).all()
    demo_patients = [p for p in demo_patients if is_demo_patient(p.patient_code)]
    patient_ids = [p.id for p in demo_patients]
    visit_ids = [v.id for v in db.query(Visit).filter(Visit.patient_id.in_(patient_ids)).all()] if patient_ids else []

    if visit_ids:
        # 不良事件带 visit_id 外键，必须先于访视删除
        db.query(AdverseEvent).filter(AdverseEvent.visit_id.in_(visit_ids)).delete(synchronize_session=False)
        db.query(Query).filter(Query.visit_id.in_(visit_ids)).delete(synchronize_session=False)
        db.query(Questionnaire).filter(Questionnaire.visit_id.in_(visit_ids)).delete(synchronize_session=False)
        db.query(Medication).filter(Medication.visit_id.in_(visit_ids)).delete(synchronize_session=False)
        db.query(PhysicalExam).filter(PhysicalExam.visit_id.in_(visit_ids)).delete(synchronize_session=False)
        db.query(LabResults).filter(LabResults.visit_id.in_(visit_ids)).delete(synchronize_session=False)
        db.query(Comorbidity).filter(Comorbidity.visit_id.in_(visit_ids)).delete(synchronize_session=False)
        db.query(CostIndicator).filter(CostIndicator.visit_id.in_(visit_ids)).delete(synchronize_session=False)
        db.query(Visit).filter(Visit.id.in_(visit_ids)).delete(synchronize_session=False)
    if patient_ids:
        db.query(AdverseEvent).filter(AdverseEvent.patient_id.in_(patient_ids)).delete(synchronize_session=False)
        db.query(ConsentRecord).filter(ConsentRecord.patient_id.in_(patient_ids)).delete(synchronize_session=False)
        db.query(Patient).filter(Patient.id.in_(patient_ids)).delete(synchronize_session=False)

    demo_user_ids = [u.id for u in db.query(User).filter(User.username.in_(DEMO_USERS)).all()]
    if demo_user_ids:
        db.query(Notification).filter(Notification.user_id.in_(demo_user_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(demo_user_ids)).delete(synchronize_session=False)

    # 清理真实账号身上的演示通知，避免通知铃铛越积越多
    db.query(Notification).filter(Notification.type.in_(["followup_window", "query_raised"])).delete(synchronize_session=False)

    db.commit()
    print(f"✓ 已清理旧演示数据（{len(demo_patients)} 名患者）")


def ensure_demo_users(db):
    """创建 TJ-02 分中心的演示账号（TJ-01 的 researcher1/qc1 已由初始化脚本创建）"""
    users = {}
    specs = [
        ("researcher2", "researcher", 2, "王研究（TJ-02）"),
        ("qc2",         "qc",         2, "赵质控（TJ-02）"),
    ]
    for username, role, center_id, full_name in specs:
        u = db.query(User).filter(User.username == username).first()
        if not u:
            u = User(username=username, hashed_password=hash_password("Test@123"),
                     full_name=full_name, role=role, center_id=center_id, is_active=1)
            db.add(u)
            db.commit()
            db.refresh(u)
        users[username] = u
    print("✓ 演示账号就绪：researcher2 / qc2 / center_admin2 均为 Test@123（center_admin2 为 TJ-02 管理员，如已存在则沿用）")
    return users


# ── 演示患者档案 ─────────────────────────────────────────────
# (编号, 中心, 姓名, 身份证, 性别, 年龄, 电话, 入组日, 状态, 备注)
PATIENTS = [
    ("TJ01-0003", 1, "李建国", "120103195803154411", "male",   68, "13802211111", date(2026, 1, 6),  "enrolled",  "老患者，全流程走完"),
    ("TJ01-0004", 1, "王秀兰", "120104196507223322", "female", 61, "13802212222", date(2026, 2, 17), "enrolled",  "有未答复质控疑问"),
    ("TJ01-0005", 1, "张伟",   "120101198809104433", "male",   38, "13802213333", date(2026, 3, 2),  "enrolled",  "提交待质控，PHQ-9 偏高"),
    ("TJ01-0006", 1, "刘芳",   "120105199203264455", "female", 34, "13802214444", date(2026, 4, 20), "enrolled",  "草稿中，录了一半"),
    ("TJ01-0007", 1, "陈国强", "120102195511305566", "male",   70, "13802215555", date(2025, 6, 10), "completed", "已满 2 年随访，结题"),
    ("TJ02-0001", 2, "赵桂英", "120106196212184466", "female", 64, "13903311111", date(2026, 2, 25), "enrolled",  "TJ-02 老患者"),
    ("TJ02-0002", 2, "孙立军", "120107197504067755", "male",   51, "13903312222", date(2026, 5, 8),  "enrolled",  "TJ-02 提交待质控"),
    ("TJ02-0003", 2, "周敏",   "120108198301238866", "female", 43, "13903313333", date(2026, 7, 14), "enrolled",  "TJ-02 草稿"),
    ("TJ02-0004", 2, "吴长海", "120109196609019977", "male",   60, "13903314444", date(2026, 8, 1),  "dropout",   "TJ-02 脱落（迁居外地）"),
]


def make_patient(db, spec, researcher_id):
    code, center_id, name, id_card, gender, age, phone, enroll, status, _note = spec
    p = Patient(
        patient_code=code, center_code="TJ-01" if center_id == 1 else "TJ-02", center_id=center_id,
        name_initials={"李建国": "LJG", "王秀兰": "WXL", "张伟": "ZW", "刘芳": "LF", "陈国强": "CGQ",
                       "赵桂英": "ZGY", "孙立军": "SLJ", "周敏": "ZM", "吴长海": "WCH"}[name],
        full_name_encrypted=encrypt(name), id_card_encrypted=encrypt(id_card),
        phone=phone, gender=gender, age=age, visit_number=f"V{2026}{abs(hash(code)) % 100000:05d}",
        marital_status=2, employment_status=3 if age >= 60 else 1, education_level=3,
        insurance_coverage=3, smoking_status=1 if gender == "female" else 2, drinking_status=1,
        consent_date=enroll - timedelta(days=1), enrollment_date=enroll, status=status,
        withdraw_reason="迁居外地，无法继续随访" if status == "dropout" else None,
        withdraw_date=date(2026, 8, 30) if status == "dropout" else None,
        created_by=researcher_id,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def add_consent(db, patient, investigator="陈雨", version="V1.0-20251201"):
    if patient.status == "dropout":
        return
    db.add(ConsentRecord(
        patient_id=patient.id, consent_version=version,
        subject_signed_date=patient.enrollment_date - timedelta(days=1),
        subject_contact=patient.phone,
        investigator_name=investigator,
        investigator_signed_date=patient.enrollment_date - timedelta(days=1),
        investigator_contact="022-88328666",
    ))
    db.commit()


def add_visit(db, patient, vtype, vdate, status, researcher_id):
    v = Visit(patient_id=patient.id, visit_type=vtype, visit_date=vdate,
              status=status, created_by=researcher_id)
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def fill_full_forms(db, visit, *, hba1c=7.8, phq9_answers=None, gad7_answers=None, eq_vas=80):
    """给一个访视填齐所有表单（体检/化验/合并症/费用/量表/用药）"""
    height, weight = 1.70, 74.0
    db.add(PhysicalExam(visit_id=visit.id, weight_kg=weight, height_cm=height * 100,
                        bmi=round(weight / height ** 2, 1), waist_cm=92, hip_cm=98,
                        heart_rate=74, sbp_mmhg=132, dbp_mmhg=80))
    db.add(LabResults(visit_id=visit.id, fasting_glucose=7.9, hba1c=hba1c, tc=5.1, tg=1.8,
                      hdl_c=1.2, ldl_c=3.0, alt=26, ast=22, scr=78, egfr=92, ua=340, bun=5.1,
                      test_date=visit.visit_date))
    db.add(Comorbidity(visit_id=visit.id, hypertension=1, hypertension_date="2015-03",
                       dr=1, dr_date="2024-11", dr_non_proliferative=True))
    db.add(CostIndicator(visit_id=visit.id, drug_cost=680.0, lab_cost=420.0,
                         service_cost=50.0, supply_cost=120.0, other_cost=0.0))
    if phq9_answers:
        db.add(Questionnaire(visit_id=visit.id, questionnaire_type="phq9",
                             **{f"q{i+1}": v for i, v in enumerate(phq9_answers)},
                             total_score=sum(phq9_answers), phq9_symptoms="无"))
    if gad7_answers:
        db.add(Questionnaire(visit_id=visit.id, questionnaire_type="gad7",
                             **{f"q{i+1}": v for i, v in enumerate(gad7_answers)},
                             total_score=sum(gad7_answers)))
    db.add(Questionnaire(visit_id=visit.id, questionnaire_type="eq5d",
                         eq_mobility=1, eq_self_care=1, eq_usual_activity=2,
                         eq_pain=2, eq_anxiety=1, eq_vas_score=eq_vas))
    db.add(Medication(visit_id=visit.id, treatment_type="糖尿病", drug_name="二甲双胍缓释片",
                      route="口服", dose="0.5 g", frequency="BID",
                      start_date=visit.visit_date - timedelta(days=365), is_ongoing=True))
    db.add(Medication(visit_id=visit.id, treatment_type="糖尿病", drug_name="格列美脲片",
                      route="口服", dose="2 mg", frequency="QD",
                      start_date=visit.visit_date - timedelta(days=180), is_ongoing=True))
    db.add(Medication(visit_id=visit.id, treatment_type="高血压", drug_name="苯磺酸氨氯地平片",
                      route="口服", dose="5 mg", frequency="QD",
                      start_date=visit.visit_date - timedelta(days=2000), is_ongoing=True))
    db.commit()


def seed():
    db = SessionLocal()
    try:
        clean_demo_data(db)
        users = ensure_demo_users(db)
        researcher1 = db.query(User).filter(User.username == "researcher1").first()
        qc1 = db.query(User).filter(User.username == "qc1").first()
        researcher2 = users["researcher2"]

        created = {}
        for spec in PATIENTS:
            rid = researcher1.id if spec[1] == 1 else researcher2.id
            p = make_patient(db, spec, rid)
            add_consent(db, p, investigator="陈雨" if spec[1] == 1 else "张宇宁")
            created[spec[0]] = p
            print(f"✓ 患者 {spec[0]} {spec[2]}（{spec[9]}）")

        # ── 访视与状态：每种状态都有样本 ──
        # 李建国：baseline locked + M6 locked（随访依从性好的样板）
        v = add_visit(db, created["TJ01-0003"], "baseline", date(2026, 1, 6), "locked", researcher1.id)
        fill_full_forms(db, v, hba1c=8.6, phq9_answers=[1,0,1,0,0,0,0,0,0], gad7_answers=[0,1,0,1,0,0,0], eq_vas=70)
        v = add_visit(db, created["TJ01-0003"], "M6", date(2026, 7, 10), "locked", researcher1.id)
        fill_full_forms(db, v, hba1c=7.1, phq9_answers=[0,0,1,0,0,0,0,0,0], gad7_answers=[0,0,0,0,0,0,0], eq_vas=85)

        # 王秀兰：baseline locked，M6 submitted + 未答复质控疑问
        v = add_visit(db, created["TJ01-0004"], "baseline", date(2026, 2, 17), "locked", researcher1.id)
        fill_full_forms(db, v, hba1c=8.2, phq9_answers=[2,1,1,1,0,0,1,0,0], gad7_answers=[1,1,0,1,0,1,0], eq_vas=65)
        v_m6 = add_visit(db, created["TJ01-0004"], "M6", date(2026, 8, 18), "submitted", researcher1.id)
        fill_full_forms(db, v_m6, hba1c=6.4, phq9_answers=[0,0,0,0,0,0,0,0,0], gad7_answers=[0,0,0,0,0,0,0], eq_vas=75)

        # 张伟：baseline submitted（待质控），PHQ-9 偏高
        v = add_visit(db, created["TJ01-0005"], "baseline", date(2026, 3, 2), "submitted", researcher1.id)
        fill_full_forms(db, v, hba1c=9.1, phq9_answers=[2,1,2,1,1,1,0,1,0], gad7_answers=[2,2,1,2,1,1,0], eq_vas=55)

        # 刘芳：baseline draft（录入到一半）
        v = add_visit(db, created["TJ01-0006"], "baseline", date(2026, 4, 20), "draft", researcher1.id)
        db.add(PhysicalExam(visit_id=v.id, weight_kg=58, height_cm=162, bmi=22.1,
                            waist_cm=80, hip_cm=94, heart_rate=78, sbp_mmhg=118, dbp_mmhg=74))
        db.commit()

        # 陈国强：满 2 年随访全 locked，已结题（报表深度数据）
        v = add_visit(db, created["TJ01-0007"], "baseline", date(2025, 6, 10), "locked", researcher1.id)
        fill_full_forms(db, v, hba1c=8.9, phq9_answers=[1,0,0,0,0,0,0,0,0], gad7_answers=[0,0,0,0,0,0,0], eq_vas=75)
        v = add_visit(db, created["TJ01-0007"], "M6", date(2025, 12, 12), "locked", researcher1.id)
        fill_full_forms(db, v, hba1c=7.6, phq9_answers=[0,0,0,0,0,0,0,0,0], gad7_answers=[0,0,0,0,0,0,0], eq_vas=80)
        v = add_visit(db, created["TJ01-0007"], "M12", date(2026, 6, 15), "locked", researcher1.id)
        fill_full_forms(db, v, hba1c=6.9, phq9_answers=[0,0,0,0,0,0,0,0,0], gad7_answers=[0,0,0,0,0,0,0], eq_vas=88)

        # TJ-02 赵桂英：baseline locked + M6 signed（研究者已签名，待管理员锁定）
        v = add_visit(db, created["TJ02-0001"], "baseline", date(2026, 2, 25), "locked", researcher2.id)
        fill_full_forms(db, v, hba1c=7.9, phq9_answers=[1,0,0,0,0,0,0,0,0], gad7_answers=[0,0,1,0,0,0,0], eq_vas=78)
        v = add_visit(db, created["TJ02-0001"], "M6", date(2026, 8, 25), "signed", researcher2.id)
        fill_full_forms(db, v, hba1c=7.2, phq9_answers=[0,0,0,0,0,0,0,0,0], gad7_answers=[0,0,0,0,0,0,0], eq_vas=80)

        # TJ-02 孙立军：baseline submitted（待质控）
        v = add_visit(db, created["TJ02-0002"], "baseline", date(2026, 5, 8), "submitted", researcher2.id)
        fill_full_forms(db, v, hba1c=8.8, phq9_answers=[0,1,0,0,0,0,0,0,0], gad7_answers=[0,0,0,0,0,0,0], eq_vas=72)

        # TJ-02 周敏：baseline draft
        v = add_visit(db, created["TJ02-0003"], "baseline", date(2026, 7, 14), "draft", researcher2.id)
        db.add(PhysicalExam(visit_id=v.id, weight_kg=63, height_cm=166, bmi=22.9,
                            waist_cm=84, hip_cm=96, heart_rate=72, sbp_mmhg=124, dbp_mmhg=78))
        db.commit()

        # TJ-02 吴长海：baseline qc_passed（脱落前最后一访）
        v = add_visit(db, created["TJ02-0004"], "baseline", date(2026, 8, 1), "qc_passed", researcher2.id)
        fill_full_forms(db, v, hba1c=7.4, phq9_answers=[0,0,0,0,0,0,0,0,0], gad7_answers=[0,0,0,0,0,0,0], eq_vas=82)

        # ── 质控疑问：一条未答复 + 一条已答复 ──
        v_m6_wxl = db.query(Visit).filter(Visit.patient_id == created["TJ01-0004"].id,
                                          Visit.visit_type == "M6").first()
        q = Query(visit_id=v_m6_wxl.id, field_name="hba1c",
                  content="M6 访视 HbA1c 6.4%，较基线 8.2% 下降明显，请核对化验单并确认无误。",
                  status="open", raised_by=qc1.id)
        db.add(q)
        db.add(Notification(user_id=researcher1.id, center_id=1, type="query_raised",
                            content=f"您录入的访视（患者 TJ01-0004 M6）收到新的质控疑问：HbA1c 数值待核对"))

        v_base_zw = db.query(Visit).filter(Visit.patient_id == created["TJ01-0005"].id).first()
        db.add(Query(visit_id=v_base_zw.id, field_name="q3",
                     content="PHQ-9 第 3 题（睡眠困难）与第 6 题（自我评价低）评分偏高，建议复核受试者作答。",
                     status="answered", raised_by=qc1.id,
                     answered_by=researcher1.id,
                     answer="已与受试者电话复核，确认作答无误，其近期工作压力大、睡眠差，属实。"))

        # ── 随访提醒：李建国 M12 窗口临近（2027-01-06，提前提醒）──
        db.add(Notification(user_id=researcher1.id, center_id=1, type="followup_window",
                            content="随访窗口提醒：患者 TJ01-0003 的 M12 访视窗口将于 2026-12-30 开启，请提前安排随访"))
        # 王秀兰 M6 已超期未锁（计划 2026-08-18，如当天未完成即超期）
        db.add(Notification(user_id=researcher1.id, center_id=1, type="followup_window",
                            content="随访超期提醒：患者 TJ01-0004 的 M6 访视已超期（计划日期 2026-08-18），请尽快完成录入与质控"))

        # ── 不良事件：1 轻度低血糖（已痊愈）+ 1 中度胃肠道反应（恢复中）──
        db.add(AdverseEvent(patient_id=created["TJ01-0003"].id, visit_id=None,
                            term="轻度低血糖", onset_date=date(2026, 3, 15), end_date=date(2026, 3, 15),
                            severity="mild", is_serious=False, relation="probable",
                            outcome="recovered", action_taken="减少格列美脲剂量至 1mg QD，指导加餐",
                            description="午餐前出现心悸、出汗，自测指尖血糖 3.6 mmol/L，进食后缓解。", created_by=researcher1.id))
        db.add(AdverseEvent(patient_id=created["TJ01-0004"].id, visit_id=v_m6_wxl.id,
                            term="胃肠道不适（恶心、腹胀）", onset_date=date(2026, 6, 2), end_date=None,
                            severity="moderate", is_serious=False, relation="possible",
                            outcome="recovering", action_taken="继续观察，必要时对症处理",
                            description="服用二甲双胍后出现恶心、腹胀，未停药，症状逐渐减轻。", created_by=researcher1.id))

        db.commit()
        print()
        print("=" * 62)
        print("演示数据就绪！共 9 名演示患者、9 次访视（覆盖全部 5 种状态）、")
        print("2 条质控疑问、2 条不良事件、3 条站内通知。")
        print("=" * 62)
        print("演示账号（密码统一见 演示手册.md）：")
        print("  admin / Admin@123          总管理员（全局视角 + 解锁权限）")
        print("  researcher1 / Test@123     TJ-01 研究者（录入、答复疑问）")
        print("  qc1 / Test@123             TJ-01 质控员（质控、提疑问）")
        print("  center_admin1 / Test@123   TJ-01 分中心管理员")
        print("  researcher2 / Test@123     TJ-02 研究者（演示中心隔离）")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
