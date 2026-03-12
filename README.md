# 糖尿病研究 EDC 系统（Demo）

## 🎉 多中心版本已上线

本系统已升级为**多中心EDC系统**，支持多个研究中心共用一套部署！

### 📖 快速导航
- **每日使用**：[DAILY_USAGE.md](DAILY_USAGE.md) ⭐ 每天必看
- **快速开始**：[QUICK_START.md](QUICK_START.md)
- **完整文档**：[MULTI_CENTER_GUIDE.md](MULTI_CENTER_GUIDE.md)
- **数据库启动**：[START_DATABASE.md](START_DATABASE.md)

### 核心特性
- ✅ 多中心数据隔离
- ✅ 邀请码注册系统
- ✅ 分级权限管理（总管理员/分中心管理员/研究者/质控员）
- ✅ 总中心可查看所有数据，分中心只能查看自己的数据

## 🚀 每次开机后如何启动系统

### 🐳 如果你使用 Docker（推荐）

**你的 MySQL 在 Docker 里运行？** 查看 [DOCKER_MYSQL_GUIDE.md](DOCKER_MYSQL_GUIDE.md)

**快速启动：**
1. 确保 Docker Desktop 已启动
2. 双击运行 `start_all_docker.bat`
3. 等待启动完成

### 💻 如果你使用 Windows 服务

### 方法1：一键启动（最简单）⭐

1. 右键点击 `start_all.bat`
2. 选择"以管理员身份运行"
3. 等待启动完成

这个脚本会自动：
- 启动 MySQL 服务
- 启动后端 API 服务
- 显示访问地址

### 方法2：手动启动

**第1步：启动 MySQL**
```powershell
# 以管理员身份运行 PowerShell 或 CMD
net start MySQL
# 或者
net start MySQL80
```

**第2步：启动后端**
```powershell
cd hospital-edc-backend
start.bat
```

**详细说明：** 查看 [START_DATABASE.md](START_DATABASE.md)

---

## 原有内容

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

### 多中心系统（推荐）

运行初始化脚本自动创建管理员和示例中心：

```powershell
cd hospital-edc-backend
python scripts/init_multi_center.py
```

这将创建：
- 总管理员账号：`admin` / `Admin@123`
- 主中心和3个示例分中心
- 每个分中心的管理员邀请码

### 传统方式（手动创建）

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

提交后行为：
- 一旦该患者存在“已提交/已签名/已锁定”的访视，“概况”和“患者管理”中的该患者「录入」按钮会置灰不可点击。
- 如需修改已提交数据：进入左侧「已录入患者」页面，点击「管理/修改」进入。

## 5. 常见问题

- 登录提示“网络错误/登录失败”：确认后端已启动且 `API_BASE` 指向正确地址。
- 页面跨域问题：后端已配置允许跨域（包含 `file://` 直接打开 HTML 的场景）。
- 数据库连接失败：检查 MySQL 是否启动、`DATABASE_URL` 是否正确、数据库 `hospital_edc` 是否存在。
