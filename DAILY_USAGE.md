# 每日使用指南

## 📋 每天开始工作时

### 1. 启动系统（3秒完成）

**推荐：使用智能启动脚本**
1. 找到项目文件夹中的 `start_all_v2.bat`
2. **右键点击** → 选择 **"以管理员身份运行"**
3. 等待窗口显示"系统启动完成"

> 💡 `start_all_v2.bat` 会自动检测你的 MySQL 服务名称，更智能！

**或者使用原版脚本**
1. 找到 `start_all.bat`
2. **右键点击** → 选择 **"以管理员身份运行"**

就这么简单！系统会自动：
- ✓ 启动 MySQL 数据库
- ✓ 启动后端 API 服务
- ✓ 准备好所有功能

### 2. 访问系统
- **前端页面**：双击打开 `hospital-edc-frontend/index.html`
- **API 文档**：浏览器访问 http://localhost:8000/api/docs
- **默认账号**：`admin` / `Admin@123`

## 🛑 工作结束时

### 停止系统（可选）
如果想关闭服务节省资源：
1. 找到 `stop_all.bat`
2. **右键点击** → 选择 **"以管理员身份运行"**

> 💡 提示：如果不停止，下次开机后需要重新启动

## 🔍 遇到问题时

### 检查系统状态
双击运行 `check_status.bat`，会告诉你：
- ✓ MySQL 是否运行
- ✓ 后端是否运行
- ✓ 哪里出了问题

### 常见问题

#### ❌ 启动失败："拒绝访问"
**原因**：没有管理员权限
**解决**：右键点击 `start_all.bat`，选择"以管理员身份运行"

#### ❌ MySQL 启动失败："服务名称无效"
**原因**：系统找不到 MySQL 服务
**解决**：查看详细解决方案 → [MYSQL_TROUBLESHOOTING.md](MYSQL_TROUBLESHOOTING.md)

**快速方案：**
1. 双击运行 `find_mysql_service.bat` 查找服务名称
2. 使用 `start_all_v2.bat` 代替 `start_all.bat`（自动检测服务名称）
3. 或者手动启动：按 `Win + R` → 输入 `services.msc` → 找到 MySQL 服务 → 右键启动

#### ❌ 后端启动失败
**原因**：端口被占用或数据库连接失败
**解决**：
1. 检查 MySQL 是否运行（运行 `check_status.bat`）
2. 检查 8000 端口是否被占用：
   ```bash
   netstat -ano | findstr :8000
   ```
3. 查看后端窗口的错误信息

#### ❌ 登录失败
**原因**：账号未创建或密码错误
**解决**：
1. 运行初始化脚本：
   ```bash
   cd hospital-edc-backend
   python scripts/init_multi_center.py
   ```
2. 使用默认账号：`admin` / `Admin@123`

## 📱 创建桌面快捷方式

让启动更方便：

1. 右键点击 `start_all.bat`
2. 选择"发送到" → "桌面快捷方式"
3. 右键点击桌面快捷方式 → "属性"
4. 点击"高级"按钮
5. 勾选"用管理员身份运行"
6. 确定

以后双击桌面图标就能启动！

## 🔄 完整工作流程

### 第一次使用
```
1. 安装 MySQL 和 Python
2. 创建数据库：CREATE DATABASE hospital_edc;
3. 运行初始化：python scripts/init_multi_center.py
4. 启动系统：start_all.bat（管理员身份）
5. 登录：admin / Admin@123
```

### 每天使用
```
1. 启动系统：start_all.bat（管理员身份）
2. 打开前端：hospital-edc-frontend/index.html
3. 登录并开始工作
4. 结束时：stop_all.bat（可选）
```

### 创建新用户
```
1. 总管理员登录
2. 访问 API 文档：http://localhost:8000/api/docs
3. 找到 POST /api/invitation-codes/
4. 创建邀请码
5. 将邀请码发给新用户
6. 新用户使用邀请码注册
```

## 📚 更多帮助

- **快速开始**：[QUICK_START.md](QUICK_START.md)
- **完整指南**：[MULTI_CENTER_GUIDE.md](MULTI_CENTER_GUIDE.md)
- **数据库启动**：[START_DATABASE.md](START_DATABASE.md)
- **部署检查**：[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)

## 💡 小技巧

1. **设置 MySQL 自动启动**
   - 打开服务管理器（`services.msc`）
   - 找到 MySQL 服务 → 属性
   - 启动类型 → 自动
   - 以后开机自动启动，不用手动

2. **快速访问 API 文档**
   - 浏览器收藏 http://localhost:8000/api/docs
   - 方便随时查看接口

3. **定期备份数据库**
   ```bash
   mysqldump -u root -p hospital_edc > backup.sql
   ```

4. **查看后端日志**
   - 后端窗口会显示所有请求日志
   - 出错时查看红色错误信息

## 🆘 紧急情况

### 系统完全无法启动
1. 重启电脑
2. 检查 MySQL 是否安装
3. 手动启动 MySQL：`net start MySQL`
4. 再次运行 `start_all.bat`

### 数据丢失或损坏
1. 停止所有服务
2. 恢复数据库备份：
   ```bash
   mysql -u root -p hospital_edc < backup.sql
   ```
3. 重新启动系统

### 忘记管理员密码
1. 停止后端服务
2. 运行初始化脚本重置：
   ```bash
   python scripts/init_multi_center.py
   ```
3. 使用默认密码：`Admin@123`

---

**记住**：遇到问题先运行 `check_status.bat` 检查状态！
