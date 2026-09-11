# -*- coding: utf-8 -*-
"""阶段 4 验收：报表 + 随访提醒 + 通知"""
import json
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000"


def login(username, password):
    form = urllib.parse.urlencode({"username": username, "password": password}).encode()
    req = urllib.request.Request(BASE + "/api/auth/login", data=form, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["access_token"]


def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


admin = login("admin", "Admin@123")
researcher = login("researcher1", "Test@123")
qc = login("qc1", "Test@123")
print("logins ok")

# ── 1. 入组报表 ──
st, r = call("GET", "/api/reports/enrollment", token=admin)
assert st == 200, r
print("enrollment by_center:", r["by_center"])
print("enrollment by_month:", r["by_month"])
print("enrollment status_dist:", r["status_dist"])
assert any(c["total"] > 0 for c in r["by_center"])

# 研究者视角：只能看到本中心
st, r2 = call("GET", "/api/reports/enrollment", token=researcher)
assert st == 200, r2
total_all = sum(c["total"] for c in r["by_center"])
total_res = sum(c["total"] for c in r2["by_center"])
print(f"researcher enrollment total: {total_res} (admin: {total_all})")
assert total_res <= total_all
assert all(c["center_code"] == "TJ-01" for c in r2["by_center"]), "研究者应只见 TJ-01"

# ── 2. 访视完成率 ──
st, r = call("GET", "/api/reports/visit-completion", token=admin)
assert st == 200, r
print("visit-completion:", json.dumps(r["items"], ensure_ascii=False))
baseline = [i for i in r["items"] if i["visit_type"] == "baseline"]
assert baseline and baseline[0]["total"] >= 1

# ── 3. 数据完整率 ──
st, r = call("GET", "/api/reports/data-completeness", token=admin)
assert st == 200, r
print("data-completeness total_visits:", r["total_visits"])
for f in r["forms"]:
    print(f"  {f['label']}: {f['filled']}/{r['total_visits']} = {f['rate']}%")
assert r["total_visits"] >= 1

# ── 4. 汇总聚合（分中心可见全局聚合）──
st, r = call("GET", "/api/reports/summary", token=researcher)
assert st == 200, r
print("summary (researcher view):", {k: v for k, v in r.items() if k != "patients_by_center"})
assert "patients_by_center" in r and r["patients_total"] >= 1
# 汇总不包含患者明细字段
assert not any(k in r for k in ("patients", "patient_list", "items"))

# ── 5. 随访提醒：造一个入组很久的患者（TJ01-0002 或新建）──
# 直接把患者2的入组日期改到 8 个月前，触发 M6 窗口
import subprocess
sql = ("UPDATE patients SET enrollment_date = DATE_SUB(CURDATE(), INTERVAL 8 MONTH) "
       "WHERE patient_code='TJ01-0002';")
subprocess.run(["docker", "exec", "hospital-edc-mysql", "mysql",
                "-uroot", "-pedc123456", "hospital_edc", "-e", sql],
               capture_output=True)
print("patient TJ01-0002 enrollment_date -> 8 months ago")

st, r = call("POST", "/api/notifications/scan-followups", token=admin)
assert st == 200, r
print("scan-followups:", r)
assert r["created"] >= 1, "应生成至少 1 条随访提醒"

# 研究者应收到通知
st, r = call("GET", "/api/notifications/?unread_only=true", token=researcher)
assert st == 200, r
print("researcher unread:", r["unread"])
followups = [n for n in r["items"] if n["type"] == "followup_window"]
assert followups, "研究者应收到 followup_window 通知"
print("notification:", followups[0]["content"])

# 未读数接口
st, r = call("GET", "/api/notifications/unread-count", token=researcher)
assert st == 200 and r["unread"] >= 1, r
print("unread-count:", r["unread"])

# 标记已读
nid = followups[0]["id"]
st, r = call("PATCH", f"/api/notifications/{nid}/read", token=researcher)
assert st == 200, r
st, r = call("GET", "/api/notifications/unread-count", token=researcher)
assert st == 200, r
print(f"after read #{nid}: unread={r['unread']}")

# ── 6. QC 提 query → 研究者收到通知（阶段2已实现，回归验证）──
st, visits = call("GET", "/api/visits/?patient_id=1", token=researcher)
assert st == 200, visits
vid = visits[0]["id"] if isinstance(visits, list) else visits["items"][0]["id"]
st, r = call("POST", "/api/queries/", token=qc, body={
    "visit_id": vid, "field_name": "sbp_mmhg", "content": "阶段4回归：收缩压 130 请复核。"})
print("query raise:", st, r if st != 200 else "ok")
assert st in (200, 201), r
qid = r["id"]
# 通知发给访视创建者（visit 1 由 admin 创建）
st, r = call("GET", "/api/notifications/?limit=5", token=admin)
assert st == 200 and any(n["type"] == "query_raised" and not n["is_read"] for n in r["items"]), r
print("query_raised notification ok (visit creator)")
# 关闭回归用的 query
st, r = call("PATCH", f"/api/queries/{qid}/answer", token=researcher, body={"answer": "已复核无误"})
assert st == 200, r
st, r = call("PATCH", f"/api/queries/{qid}/close", token=qc)
assert st == 200, r
print("query closed")

print("\n✅ 阶段 4 报表/提醒/通知验收全部通过")
