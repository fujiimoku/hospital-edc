"""随访窗口提醒（需求优先级 2）。

按访视计划窗口期，对即将到期/已到期但未完成访视的患者生成站内提醒。
主访视：baseline=基线；W12=入组后84天；W26=入组后182天。
中间采集按实际日期记录，尚无固定提醒计划。
到期前 7 天开始提醒；已过窗口仍提醒（标记"已超期"）。
"""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit

# 主访视：访视类型 → 距入组的天数
VISIT_PLAN_DAYS = {
    "baseline": 0,
    "W12": 84,
    "W26": 182,
}
REMIND_AHEAD_DAYS = 7  # 到期前 7 天开始提醒


def _next_expected_visit(patient: Patient, existing: dict) -> tuple:
    """返回 (visit_type, due_date)；全部完成则返回 (None, None)。"""
    if not patient.enrollment_date:
        return None, None
    # 历史月访视不能自动解释成新的周访视；待研究者核对。
    if any(vt in existing for vt in ("M6", "M12", "M18", "M24")):
        return None, None
    for vt, offset in VISIT_PLAN_DAYS.items():
        if vt not in existing:
            return vt, patient.enrollment_date + timedelta(days=offset)
    return None, None


def scan_followup_windows(db: Session, today: date | None = None) -> int:
    """扫描所有在研患者，为随访窗口期内未完成访视的患者给本中心研究者发提醒。

    返回生成的通知条数。已存在同类未读提醒的不重复发。
    """
    today = today or date.today()
    created = 0

    patients = db.query(Patient).filter(Patient.status == "enrolled").all()
    for p in patients:
        existing = {row[0] for row in db.query(Visit.visit_type)
                    .filter(Visit.patient_id == p.id).all()}
        vt, due = _next_expected_visit(p, existing)
        if vt is None:
            continue
        if due - today > timedelta(days=REMIND_AHEAD_DAYS):
            continue  # 还没进窗口

        overdue = today > due + timedelta(days=30)  # 超 30 天视为超期
        if overdue:
            content = (f"随访超期提醒：患者 {p.patient_code} 的 {vt} 访视已超期"
                       f"（计划日期 {due.isoformat()}），请尽快安排随访。")
        else:
            content = (f"随访窗口提醒：患者 {p.patient_code} 的 {vt} 访视窗口期临近"
                       f"（计划日期 {due.isoformat()}），请及时安排随访。")

        # 通知该中心所有在职研究者
        researchers = db.query(User).filter(
            User.center_id == p.center_id,
            User.role.in_(("researcher", "center_admin")),
            User.is_active == True,
        ).all()
        for u in researchers:
            dup = db.query(Notification).filter(
                Notification.user_id == u.id,
                Notification.type == "followup_window",
                Notification.is_read == False,
                Notification.content == content,
            ).first()
            if dup:
                continue
            db.add(Notification(user_id=u.id, center_id=p.center_id,
                                type="followup_window", content=content))
            created += 1

    if created:
        db.commit()
    return created
