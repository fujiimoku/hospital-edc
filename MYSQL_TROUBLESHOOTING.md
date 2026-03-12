# MySQL 服务启动问题解决方案

## 问题：找不到 MySQL 服务

当你看到 "The service name is invalid" 错误时，说明系统找不到 MySQL 服务。

## 解决步骤

### 步骤1：查找 MySQL 服务名称

**方法A：使用查找脚本（推荐）**
1. 双击运行 `find_mysql_service.bat`
2. 查看输出的服务名称（Name 列）
3. 记住这个名称

**方法B：使用服务管理器**
1. 按 `Win + R`
2. 输入 `services.msc`，按回车
3. 在服务列表中找到包含 "MySQL" 的服务
4. 记住服务名称（不是显示名称）

**方法C：使用命令行**
```powershell
# 以管理员身份运行 PowerShell
Get-Service | Where-Object {$_.DisplayName -like '*mysql*'}
```

### 步骤2：根据情况选择解决方案

#### 情况A：找到了 MySQL 服务

**使用新的启动脚本（推荐）**
1. 使用 `start_all_v2.bat` 代替 `start_all.bat`
2. 这个脚本会自动尝试多个常见的服务名称

**或者手动修改启动脚本**
1. 右键点击 `start_all.bat`，选择"编辑"
2. 找到第11行：`net start MySQL`
3. 将 `MySQL` 改为你找到的服务名称
4. 保存文件

例如，如果你的服务名称是 `MySQL8.0`：
```batch
net start MySQL8.0
```

#### 情况B：没有找到 MySQL 服务

说明 MySQL 可能：
1. 未安装
2. 安装了但未配置为 Windows 服务
3. 使用了其他方式运行（如 XAMPP、WAMP）

**解决方案：**

**如果使用 XAMPP：**
1. 打开 XAMPP Control Panel
2. 点击 MySQL 旁边的 "Start" 按钮
3. 然后只需启动后端：
   ```bash
   cd hospital-edc-backend
   start.bat
   ```

**如果使用 WAMP：**
1. 启动 WAMP
2. 确保 MySQL 是绿色（运行中）
3. 然后只需启动后端

**如果需要安装 MySQL：**
1. 下载 MySQL Installer：https://dev.mysql.com/downloads/installer/
2. 安装时选择 "MySQL Server"
3. 配置为 Windows 服务
4. 记住设置的 root 密码

### 步骤3：验证 MySQL 是否运行

**方法1：使用命令行**
```bash
mysql -u root -p
# 输入密码，如果能连接说明 MySQL 正在运行
```

**方法2：使用检查脚本**
```bash
# 双击运行
check_status.bat
```

**方法3：查看服务状态**
```powershell
# 以管理员身份运行
sc query MySQL
# 或使用你的服务名称
```

## 常见 MySQL 服务名称

根据安装方式和版本，MySQL 服务名称可能是：
- `MySQL` - 默认名称
- `MySQL80` - MySQL 8.0
- `MySQL57` - MySQL 5.7
- `MySQL56` - MySQL 5.6
- `MYSQL` - 大写版本
- `mysqld` - 某些安装方式
- `MySQL8.0` - 带点号的版本
- `wampmysqld` - WAMP 安装
- `wampmysqld64` - WAMP 64位

## 快速解决方案总结

### 方案1：使用新的智能启动脚本
```bash
# 右键以管理员身份运行
start_all_v2.bat
```
这个脚本会自动尝试所有常见的服务名称。

### 方案2：手动启动 MySQL
```bash
# 1. 打开服务管理器
Win + R → services.msc

# 2. 找到 MySQL 服务，右键启动

# 3. 启动后端
cd hospital-edc-backend
start.bat
```

### 方案3：使用 MySQL Workbench
```bash
# 1. 打开 MySQL Workbench
# 2. 连接到本地实例（会自动启动服务）
# 3. 启动后端
cd hospital-edc-backend
start.bat
```

## 设置 MySQL 自动启动（推荐）

这样以后开机就不用手动启动了：

1. 按 `Win + R`，输入 `services.msc`
2. 找到 MySQL 服务
3. 右键 → 属性
4. 启动类型 → **自动**
5. 点击"确定"

以后每次开机 MySQL 会自动启动，你只需要运行后端即可。

## 仍然无法解决？

### 检查清单
- [ ] 确认 MySQL 已安装
- [ ] 确认以管理员身份运行脚本
- [ ] 确认找到了正确的服务名称
- [ ] 确认服务状态不是"已禁用"
- [ ] 确认端口 3306 没有被占用

### 查看详细错误
```bash
# 查看 MySQL 服务状态
sc query MySQL

# 查看端口占用
netstat -ano | findstr :3306

# 尝试手动启动并查看错误
net start MySQL
```

### 联系支持
如果以上方法都不行，请提供：
1. `find_mysql_service.bat` 的输出
2. MySQL 安装方式（官方安装包/XAMPP/WAMP/其他）
3. 错误信息截图
