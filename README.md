# 糖尿病研究 EDC 系统（Demo）

本仓库包含：
- 前端演示页：`糖尿病研究 EDC 系统 Demo.html`（直接浏览器打开）
- 后端 API：`hospital-edc-backend/`（FastAPI）

## 1. 打开网页（前端）

双击或用浏览器打开根目录的 `糖尿病研究 EDC 系统 Demo.html`。

- 页面会先显示登录框。
- 该页面默认会请求后端接口（见下文“启动后端联调”）。如果后端未启动或无可用账号，将无法登录。

> 如需修改后端地址：编辑 `糖尿病研究 EDC 系统 Demo.html`，找到 `const API_BASE = 'http://localhost:8000';` 并替换为你的后端地址。

## 2. 启动后端联调（推荐）

### 2.1 依赖准备

- Python 3.10+（建议）
- MySQL 5.7+/8.0+

安装 Python 依赖（在仓库根目录执行）：

```powershell
# （可选）创建并激活虚拟环境
python -m venv venv
& .\venv\Scripts\Activate.ps1

# 安装依赖
pip install -r .\requirements.txt
```

### 2.2 数据库准备（MySQL）

后端默认使用 `DATABASE_URL=mysql+pymysql://root:edc123456@127.0.0.1/hospital_edc`（见 `hospital-edc-backend\start.bat`）。

请确保：
- MySQL 已启动
- 已创建数据库 `hospital_edc`
- 账号/密码与 `DATABASE_URL` 匹配（或你自行修改 `DATABASE_URL`）

示例（按你的实际 root 密码执行）：

```sql
CREATE DATABASE hospital_edc DEFAULT CHARACTER SET utf8mb4;
```

### 2.3 启动后端

最简单方式：双击运行 `hospital-edc-backend\start.bat`。

启动后可访问：
- API 根地址：`http://localhost:8000/`
- API 文档：`http://localhost:8000/api/docs`

> 说明：后端在启动时会尝试自动建表（开发模式）。生产环境建议使用 Alembic 迁移。

## 3. 创建首个登录账号（重要）

当前后端的 `/api/auth/register` 需要管理员权限才能创建账号；因此首次使用时，需要先在数据库里手工插入一个 `admin` 用户。

### 3.1 生成 bcrypt 密码哈希

在已激活虚拟环境且装好依赖的情况下执行：

```powershell
python -c "import bcrypt; print(bcrypt.hashpw(b'Admin@123', bcrypt.gensalt()).decode())"
```

把输出的哈希值记下来（下面 SQL 会用到）。

### 3.2 插入管理员账号

在 MySQL 执行（把 `<HASH>` 替换为上一步输出）：

```sql
USE hospital_edc;
INSERT INTO users (username, hashed_password, full_name, role, is_active)
VALUES ('admin', '<HASH>', '管理员', 'admin', 1);
```

之后即可在网页登录：
- 用户名：`admin`
- 密码：`Admin123`

登录后你可以：
- 在“患者管理”中创建患者
- 在“数据录入”中创建访视并提交表单
- 在“知情同意”中查看/提交知情同意记录

## 4. 页面内操作流程（从 0 到提交）

1. 启动后端（见上文），并准备好可登录账号。
2. 打开 `糖尿病研究 EDC 系统 Demo.html` 并登录。
3. 进入左侧「患者管理」。

   - 新建患者：点击右上角「+ 创建患者」。
   - 使用已有患者：在列表里找到患者。
4. 在目标患者所在行，点击最右侧「录入」。

   - 这一步会自动进入「数据录入」页，并把当前患者带过去。
5. 在「数据录入」页顶部的「访视：」栏：

   - 如果已有访视：点击某个访视标签进行切换。
   - 如果显示“暂无访视”：点击右侧「+ 新建访视」，选择访视类型与就诊日期后创建。
6. 在下方各个 Tab（基本信息/合并症/药物治疗/量表等）录入数据。
7. 点击右上角：

   - 「保存草稿」：仅保存为草稿，可多次修改。
   - 「提交表单」：提交本次访视数据（提交前会先保存所有表单）。

## 5. 常见问题

- 登录提示“网络错误/登录失败”：确认后端已启动且 `API_BASE` 指向正确地址。
- 页面跨域问题：后端已配置允许跨域（包含 `file://` 直接打开 HTML 的场景）。
- 数据库连接失败：检查 MySQL 是否启动、`DATABASE_URL` 是否正确、数据库 `hospital_edc` 是否存在。
