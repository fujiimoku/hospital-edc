# EDC 系统测试手册

> 三一照护研究 · 多中心 EDC 系统
> 覆盖：pytest 自动化测试 + 本地端到端手测脚本（M4 验收）

---

## 1. 测试环境准备

```bash
# 1) 启动 MySQL（Docker）
docker start hospital-edc-mysql     # root/edc123456, 端口 3306, 库名 hospital_edc

# 2) 启动后端（必须在 hospital-edc-backend 目录）
cd hospital-edc-backend
sh start_dev.sh                     # 127.0.0.1:8000，API 文档 /api/docs

# 3) 前端由后端托管，浏览器打开
http://127.0.0.1:8000/
```

**测试账号**（由 `scripts/init_multi_center.py` + 手工创建）：

| 账号 | 角色 | 中心 | 密码 |
|---|---|---|---|
| admin | 总管理员（main_admin） | TJ-01 | Admin@123 |
| researcher1 | 研究者 | TJ-01 | Test@123 |
| qc1 | 质控员 | TJ-01 | Test@123 |
| center_admin1 | 中心管理员 | TJ-01 | Test@123 |
| researcher2 | 研究者 | TJ-02 | Test@123 |

---

## 2. pytest 自动化测试

SQLite 内存库运行，**不需要 MySQL**，任何机器可跑：

```bash
cd hospital-edc-backend
../venv/Scripts/python.exe -m pytest tests/ -v
```

覆盖范围（26 个用例）：

| 文件 | 覆盖 |
|---|---|
| `tests/test_auth.py` | 登录成功/失败、token 校验、越权建患者 403 |
| `tests/test_patients.py` | 编号规则（TJ01-0001 流水）、姓名/身份证 Fernet 加密落库、中心隔离（列表/详情）、修改审计（old→new）、敏感字段审计只记 *** |
| `tests/test_visit_flow.py` | 四步状态流转全链路、异常值 warning 不阻断、query 闭环阻断 qc-review、锁定后禁改、解锁、量表总分自动计算、跨中心改表单 403 |
| `tests/test_export.py` | 加解密往返/掩码、导出 5 sheet、量表总分列、脱敏/明文、数据字典覆盖宽表列、研究者导隐私 403、分中心导出隔离、csv zip、导出审计、汇总报表无患者明细、入组报表中心隔离 |

---

## 3. 端到端手测脚本（浏览器）

按顺序执行，每步有预期结果。全程使用 http://127.0.0.1:8000/。

### 3.1 建库与账号（一次性）

1. `docker exec hospital-edc-mysql mysql -uroot -pedc123456 hospital_edc -e "SELECT * FROM centers;"` → 应有 7 家天津中心（TJ-06/07 为待招募停用）。
2. admin 登录 → 系统按需用邀请码注册分中心账号（`/api/auth/register-with-code`）。

### 3.2 建档与脱敏核验（researcher1 登录）

1. 「患者管理」→ 新建患者：姓名 张三 / 身份证 / 电话 / 婚姻状况 → 保存。
   - 预期：患者编号自动生成 `TJ01-0001` 格式（中心前缀 + 4 位流水）。
2. 库内核验：
   ```bash
   docker exec hospital-edc-mysql mysql -uroot -pedc123456 hospital_edc \
     -e "SELECT patient_code, full_name_encrypted FROM patients ORDER BY id DESC LIMIT 1;"
   ```
   - 预期：`full_name_encrypted` 为 `gAAAAAB...` 密文，**不是**明文。
3. 退出，用 researcher2（TJ-02）登录 → 患者列表看不到 TJ-01 患者。✅ 中心隔离

### 3.3 录入完整 CRF（researcher1）

1. 「数据录入」→ 选择患者 → 建基线访视。
2. 依次填：体格检查（身高 170 / 体重 80 / 血压 **300/130**）→ 保存。
   - 预期：黄色告警条出现"收缩压偏高"等 warning，**但数据已保存**，BMI 自动算出 27.7。
3. 化验（HbA1c 填 **45**）→ 保存 → 预期 warning + 保存成功。
4. 合并症、费用、用药（加 2 条）、PHQ-9 / GAD-7 / EQ-5D / DTSQ、生活方式、膳食。
   - 预期：量表总分与分级自动显示（如 PHQ-9 总分 8 → 轻度抑郁）。
5. 30 秒不动 → 预期自动保存 toast。

### 3.4 提交 → 质控 → 签名 → 锁定

| 步骤 | 操作者 | 动作 | 预期 |
|---|---|---|---|
| 1 | researcher1 | 点「提交」 | 状态变"待审核"，表单只读 |
| 2 | qc1 | 对血压字段提 query | 研究者收到站内通知（顶栏铃铛红点 +1） |
| 3 | qc1 | 点质控通过 | **被 400 阻断**："该访视还有 1 条未关闭的质疑" |
| 4 | researcher1 | 回答 query | 状态变 answered |
| 5 | qc1 | 关闭 query → 质控通过 | 状态变"质控通过" |
| 6 | researcher1 | 签名 | 状态变"已签名" |
| 7 | admin/center_admin | 锁定 | 状态变"已锁定"，任何修改接口返回 400 |
| 8 | admin（总中心） | 解锁 | 回到"已签名"，可改；只有 main_admin 能解锁 |

审计核验：
```bash
docker exec hospital-edc-mysql mysql -uroot -pedc123456 hospital_edc \
  -e "SELECT table_name,record_id,field_name,old_value,new_value,action FROM audit_logs ORDER BY id DESC LIMIT 10;"
```
- 预期：可见 sbp_mmhg 300→130 之类的前后值；id_card 等敏感字段只记 `***`。
- 或用 API：`GET /api/audit-logs/`（管理员）。

### 3.5 随访提醒

1. 把某在研患者入组日期改到 8 个月前（或等真实到期）：
   ```bash
   docker exec hospital-edc-mysql mysql -uroot -pedc123456 hospital_edc \
     -e "UPDATE patients SET enrollment_date=DATE_SUB(CURDATE(),INTERVAL 8 MONTH) WHERE patient_code='TJ01-0002';"
   ```
2. admin 调 `POST /api/notifications/scan-followups`（或配定时任务）。
3. researcher1 顶栏铃铛出现红点，下拉可见"随访超期提醒：患者 TJ01-0002 ..."。
4. 点通知 → 已读，红点数 -1。

### 3.6 数据导出（M3 北极星）

1. admin「数据导出」页：格式=Excel、脱敏=勾选 → 导出。
   - 预期：下载 `EDC导出_脱敏_YYYYMMDD.xlsx`，含 5 个 sheet：
     **患者主表 / 访视宽表 / 用药表 / 不良事件表 / 数据字典**。
   - 访视宽表一行=一次访视，含量表列：phq9_total、phq9_level、gad7_total、gad7_level、eq5d_vas、dtsq_total。
   - 患者主表：姓名=张\*、身份证=120\*\*\*\*。
   - 数据字典覆盖宽表全部列（变量名/中文含义/类型/取值编码/单位）。
2. admin 取消脱敏 → 导出 → 姓名/身份证为明文（需管理员权限）。
3. researcher1 勾"含隐私" → 预期 403"需要管理员权限"；导脱敏版只含 TJ-01 患者。
4. 格式=CSV → 下载 zip，解压 5 个 CSV（UTF-8 BOM，Excel 直接打开不乱码）。
5. 导出审计：
   ```bash
   docker exec hospital-edc-mysql mysql -uroot -pedc123456 hospital_edc \
     -e "SELECT * FROM audit_logs WHERE action='export' ORDER BY id DESC LIMIT 3;"
   ```
   - 预期：每次导出一行（格式/脱敏/范围/操作人）。

### 3.7 看板与报表

1. 登录任意角色 → 概况页。
   - 预期：在研患者总数 / 访视总数 / 未关闭质疑 / AE 数四张卡为真实数据；
     「最近患者」表有数据；「各中心入组进度」条形图；「访视完成率」表。
2. researcher2（TJ-02）登录看板：
   - 预期：可看全局聚合数（各中心入组计数），但患者列表/导出均只有 TJ-02。

### 3.8 多中心隔离矩阵

| 操作 | researcher1 (TJ-01) | researcher2 (TJ-02) | admin (总中心) |
|---|---|---|---|
| 患者列表 | 仅 TJ-01 | 仅 TJ-02 | 全部 |
| 他中心患者详情 | 403 | 403 | 200 |
| 他中心访视改表单 | 403 | 403 | 200 |
| 报表（入组/完成率） | 仅 TJ-01 | 仅 TJ-02 | 全部（可按中心筛选） |
| 汇总聚合（summary） | 全局聚合 | 全局聚合 | 全局聚合 |
| 导出 | 仅 TJ-01 脱敏 | 仅 TJ-02 脱敏 | 全部，可选脱敏/明文/中心 |

---

## 4. 验收结论记录

| 里程碑 | 验收方式 | 状态 |
|---|---|---|
| M3 数据导出 | `scripts/test_m3_export.py` 全绿 + 3.6 手测 | ✅ 2026-09-11 |
| M4 端到端 | pytest 26/26 + 本手册第 3 节全流程 | ✅ 2026-09-11 |
| M5 可部署 | `docker compose -f docker-compose.multi.yml up -d --build`：一镜像两实例 + Nginx 单入口（/project-a、/project-b）+ 数据物理隔离（A/B 各自库）+ Token 互认 401 验证 | ✅ 2026-09-11 |
