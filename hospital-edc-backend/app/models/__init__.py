# 统一导出所有 Model，方便 alembic env.py 导入
from app.models.user import User  # noqa
from app.models.patient import Patient  # noqa
from app.models.visit import Visit  # noqa
from app.models.forms import PhysicalExam, LabResults, Comorbidity, CostIndicator  # noqa
from app.models.medication import Medication  # noqa
from app.models.questionnaire import Questionnaire  # noqa
from app.models.lifestyle import LifestyleAssessment, MealRecord  # noqa
from app.models.consent import ConsentRecord  # noqa
