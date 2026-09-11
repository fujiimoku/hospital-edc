"""数据录入自动核查：提示但不阻止保存（需求 8.1）。

check_physical_exam / check_lab_results 返回 [{field, level, message}] 列表。
"""

# 字段 -> (中文含义, 下限, 上限, 单位)
_PHYSICAL_RULES = {
    "sbp_mmhg":  ("收缩压", 60, 250, "mmHg"),
    "dbp_mmhg":  ("舒张压", 40, 150, "mmHg"),
    "heart_rate": ("心率", 40, 200, "次/分"),
    "height_cm": ("身高", 100, 250, "cm"),
    "weight_kg": ("体重", 20, 300, "kg"),
    "waist_cm":  ("腰围", 50, 200, "cm"),
    "hip_cm":    ("臀围", 50, 200, "cm"),
}

_LAB_RULES = {
    "fasting_glucose": ("空腹血糖", 2, 30, "mmol/L"),
    "hba1c":  ("糖化血红蛋白", 3, 20, "%"),
    "tc":     ("总胆固醇", 1, 20, "mmol/L"),
    "tg":     ("甘油三酯", 0.1, 30, "mmol/L"),
    "hdl_c":  ("HDL-C", 0.1, 5, "mmol/L"),
    "ldl_c":  ("LDL-C", 0.1, 10, "mmol/L"),
    "alt":    ("ALT", 3, 1000, "U/L"),
    "ast":    ("AST", 3, 1000, "U/L"),
    "scr":    ("血肌酐", 20, 2000, "μmol/L"),
    "bun":    ("尿素氮", 1, 50, "mmol/L"),
    "ua":     ("尿酸", 90, 1000, "μmol/L"),
}


def _check_range(payload: dict, rules: dict) -> list:
    warnings = []
    for field, (label, low, high, unit) in rules.items():
        value = payload.get(field)
        if value is None:
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if value < low or value > high:
            warnings.append({
                "field": field,
                "level": "warn",
                "message": f"{label} {value}{unit} 超出合理范围（{low}~{high}{unit}），请核对",
            })
    return warnings


def check_physical_exam(payload: dict) -> list:
    warnings = _check_range(payload, _PHYSICAL_RULES)
    sbp = payload.get("sbp_mmhg")
    dbp = payload.get("dbp_mmhg")
    if sbp is not None and dbp is not None:
        try:
            if float(sbp) <= float(dbp):
                warnings.append({
                    "field": "sbp_mmhg",
                    "level": "warn",
                    "message": "收缩压应大于舒张压，请核对",
                })
        except (TypeError, ValueError):
            pass
    return warnings


def check_lab_results(payload: dict) -> list:
    return _check_range(payload, _LAB_RULES)


def check_visit_data(payload: dict) -> list:
    """对一次访视的全部表单数据做核查，返回 warnings 列表。"""
    warnings = []
    warnings += check_physical_exam(payload.get("physical_exam") or {})
    warnings += check_lab_results(payload.get("lab_results") or {})
    return warnings
