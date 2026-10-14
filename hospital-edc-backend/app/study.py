"""CRF study vocabulary. Legacy visit codes remain readable; never relabel old data."""
from typing import Literal

StudyGroup = Literal["integrated_weekly", "integrated_daily", "usual_weekly", "usual_daily"]
STUDY_GROUPS = {
    "integrated_weekly": "A组：三一照护+周制剂",
    "integrated_daily": "B组：三一照护+每日注射",
    "usual_weekly": "C组：常规诊疗+周制剂",
    # Preserve the existing database key. D's display was explicitly confirmed on 2026-10-14.
    "usual_daily": "D组：常规诊疗+周制剂",
}
GROUP_LETTERS = dict(zip(STUDY_GROUPS, "ABCD"))
StudySubgroup = Literal["icodec", "semaglutide", "icodec_semaglutide", "daily_glp1", "daily_insulin", "daily_combination"]
SUBGROUP_LABELS = {
    "icodec": "依柯胰岛素", "semaglutide": "司美格鲁肽注射液",
    "icodec_semaglutide": "依柯胰岛素 + 司美格鲁肽注射液",
    "daily_glp1": "利拉鲁肽/利司那肽注射液",
    "daily_insulin": "甘精/德谷/地特胰岛素",
    "daily_combination": "甘精胰岛素利司那肽注射液/德谷胰岛素利拉鲁肽注射液",
}
GROUP_SUBGROUPS = {g: list(SUBGROUP_LABELS)[:3] if g in ("integrated_weekly", "usual_weekly")
                   else list(SUBGROUP_LABELS)[3:] for g in STUDY_GROUPS}

def valid_subgroup(group, subgroup):
    return subgroup is None or subgroup in GROUP_SUBGROUPS.get(group, [])
VisitType = Literal["baseline", "W12", "W26", "interim", "M6", "M12", "M18", "M24"]
VISIT_TYPES = ("baseline", "W12", "W26", "interim", "M6", "M12", "M18", "M24")
