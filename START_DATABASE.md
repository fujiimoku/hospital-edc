# 数据库启动指南

## 🚀 快速启动（推荐）

### 一键启动所有服务
**右键点击 `start_all.bat`，选择"以管理员身份运行"**

这个脚本会自动：
1. ✓ 启动 MySQL 服务
2. ✓ 等待 MySQL 初始化
3. ✓ 启动后端 API 服务
4. ✓ 显示访问地址

### 一键停止所有服务
**右键点击 `stop_all.bat`，选择"以管理员身份运行"**

### 检查系统状态
**双击运行 `check_status.bat`**

会检查：
- MySQL 服务是否运行
- MySQL 连接是否正常
- 后端服务是否运行

---

## Windows 系统启动 MySQL

### 方法1：使用服务管理器（推荐）

1. **打开服务管理器**
   - 按 `Win + R`
   - 输入 `services.msc`
   - 按回车

2. **找到 MySQL 服务**
   - 在服务列表中找到 `MySQL` 或 `MySQL80`（数字可能不同）
   - 右键点击服务
   - 选择"启动"

3. **设置自动启动（可选）**
   - 右键点击 MySQL 服务
   - 选择"属性"
   - 将"启动类型"改为"自动"
   - 点击"确定"
   - 这样每次开机会自动启动

### 方法2：使用命令行

**以管理员身份运行 PowerShell 或 CMD：**

```powershell
# 启动 MySQL 服务
net start MySQL

# 或者如果服务名是 MySQL80
net start MySQL80

# 停止 MySQL 服务
net stop MySQL
```

### 方法3：使用 MySQL Workbench

1. 打开 MySQL Workbench
2. 点击左侧的"Local instance MySQL"
3. 输入密码连接
4. 如果服务未启动，会提示启动

### 方法4：创建快捷启动脚本

创建一个 `start_mysql.bat` 文件：

```batch
@echo off
echo 正在启动 MySQL 服务...
net start MySQL
if %errorlevel% == 0 (
    echo MySQL 服务启动成功！
) else (
    echo MySQL 服务启动失败，请检查服务名称或以管理员身份运行
)
pause
```

**使用方法：**
- 右键点击 `start_mysql.bat`
- 选择"以管理员身份运行"

## 验证 MySQL 是否运行

### 方法1：使用命令行
```bash
# 检查 MySQL 服务状态
sc query MySQL

# 或者
mysql -u root -p
# 如果能连接说明服务正常运行
```

### 方法2：使用任务管理器
1. 按 `Ctrl + Shift + Esc` 打开任务管理器
2. 切换到"服务"标签
3. 查找 `MySQL` 或 `MySQL80`
4. 状态应该显示"正在运行"

## 常见问题

### Q: 找不到 MySQL 服务
**A:** 可能的服务名称：
- MySQL
- MySQL80
- MySQL57
- MYSQL
- mysqld

在服务管理器中搜索 "mysql" 查看实际的服务名称

### Q: 提示"拒绝访问"
**A:** 需要以管理员身份运行命令或脚本

### Q: 服务启动失败
**A:** 可能原因：
1. 端口 3306 被占用
   ```bash
   netstat -ano | findstr :3306
   ```
2. 配置文件错误（检查 my.ini）
3. 数据目录权限问题

### Q: 如何设置开机自动启动
**A:**
1. 打开服务管理器（`services.msc`）
2. 找到 MySQL 服务
3. 右键 → 属性
4. 启动类型 → 自动
5. 确定

## 完整启动流程

### 每次开机后启动系统的步骤：

1. **启动 MySQL**
   ```bash
   # 以管理员身份运行
   net start MySQL
   ```

2. **验证数据库连接**
   ```bash
   mysql -u root -p
   # 输入密码后应该能连接
   ```

3. **启动后端服务**
   ```bash
   cd e:\hospital-edc\hospital-edc-backend
   start.bat
   ```

4. **访问系统**
   - API文档：http://localhost:8000/api/docs
   - 前端页面：打开 `hospital-edc-frontend/index.html`

## 一键启动脚本（推荐）

创建 `start_all.bat` 文件：

```batch
@echo off
echo ========================================
echo 启动医院 EDC 系统
echo ========================================

echo.
echo [1/3] 启动 MySQL 服务...
net start MySQL
if %errorlevel% neq 0 (
    echo MySQL 启动失败，请检查服务或以管理员身份运行
    pause
    exit /b 1
)
echo MySQL 服务启动成功！

echo.
echo [2/3] 等待 MySQL 初始化...
timeout /t 3 /nobreak > nul

echo.
echo [3/3] 启动后端服务...
cd /d e:\hospital-edc\hospital-edc-backend
start "EDC Backend" cmd /k start.bat

echo.
echo ========================================
echo 系统启动完成！
echo ========================================
echo.
echo API 文档: http://localhost:8000/api/docs
echo 前端页面: 打开 hospital-edc-frontend/index.html
echo.
pause
```

**使用方法：**
1. 将上述内容保存为 `e:\hospital-edc\start_all.bat`
2. 右键点击文件
3. 选择"以管理员身份运行"

## 快捷方式设置

### 创建桌面快捷方式：
1. 右键点击 `start_all.bat`
2. 选择"发送到" → "桌面快捷方式"
3. 右键点击桌面快捷方式 → 属性
4. 点击"高级"
5. 勾选"用管理员身份运行"
6. 确定

这样每次双击桌面快捷方式就能一键启动整个系统！
