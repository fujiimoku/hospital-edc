def calc_phq9_level(score: int) -> str:
    if score <= 4:   return "无/极轻微抑郁"
    if score <= 9:   return "轻度抑郁"
    if score <= 14:  return "中度抑郁"
    if score <= 19:  return "中重度抑郁"
    return "重度抑郁"

def calc_gad7_level(score: int) -> str:
    if score <= 4:   return "无焦虑症状"
    if score <= 9:   return "轻度焦虑"
    if score <= 14:  return "中度焦虑"
    return "重度焦虑"

def calc_diet_level(score: float) -> str:
    if score <= 45:  return "差"
    if score <= 65:  return "尚可"
    if score <= 85:  return "一般"
    return "良好"

def calc_exercise_level(score: float) -> str:
    if score <= 20:  return "差"
    if score <= 30:  return "尚可"
    if score <= 40:  return "一般"
    return "良好"