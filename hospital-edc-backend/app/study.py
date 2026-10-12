"""CRF study vocabulary. Legacy visit codes remain readable; never relabel old data."""
from typing import Literal

StudyGroup = Literal["integrated_weekly", "integrated_daily", "usual_weekly", "usual_daily"]
STUDY_GROUPS = {
    "integrated_weekly": "三一照护+周制剂",
    "integrated_daily": "三一照护+日制剂",
    "usual_weekly": "常规治疗+周制剂",
    "usual_daily": "常规治疗+日制剂",
}
VisitType = Literal["baseline", "W12", "W26", "interim", "M6", "M12", "M18", "M24"]
VISIT_TYPES = ("baseline", "W12", "W26", "interim", "M6", "M12", "M18", "M24")
