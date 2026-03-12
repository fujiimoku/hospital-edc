# Docker 版 MySQL 使用指南

## 🎯 你的情况

你的 MySQL 是在 **Docker 容器**中运行的，不是 Windows 服务。这就是为什么 `net start MySQL` 命令无效的原因。

从你的 Docker Desktop 截图看到：
- ✅ 有 MySQL 8.0 容器（绿点，正在运行）
- ⚪ 有 MySQL 8.1 容器（灰点，已停止）

## 🚀 快速启动（推荐）

### 使用 Docker 专用启动脚本

**直接运行（不需要管理员权限）：**
```bash
# 双击运行
start_all_docker.bat
```

这个脚本会：
1. ✓ 检查 Docker 是否运行
2. ✓ 启动 MySQL 容器
3. ✓ 启动后端服务

### 停止系统
```bash
# 双击运行
stop_all_docker.bat
```

### 检查状态
```bash
# 双击运行
check_status_docker.bat
```

## 📋 每天使用流程

### 方法1：使用脚本（最简单）

**每天开始工作：**
1. 确保 Docker Desktop 已启动（看到底部显示 "Engine running"）
2. 双击运行 `start_all_docker.bat`
3. 等待启动完成

**工作结束：**
1. 双击运行 `stop_all_docker.bat`（可选）

### 方法2：使用 Docker Desktop

**启动 MySQL：**
1. 打开 Docker Desktop
2. 找到 `mysql` 容器（8.0 版本）
3. 点击播放按钮 ▶️
4. 等待容器启动（绿点）

**启动后端：**
```bash
cd hospital-edc-backend
start.bat
```

### 方法3：使用命令行

**启动 MySQL 容器：**
```bash
# 查看所有容器
docker ps -a

# 启动 MySQL 容器（假设容器名是 mysql）
docker start mysql

# 查看运行状态
docker ps
```

**启动后端：**
```bash
cd hospital-edc-backend
start.bat
```

## 🔧 常用 Docker 命令

### 查看容器状态
```bash
# 查看运行中的容器
docker ps

# 查看所有容器（包括停止的）
docker ps -a

# 查看 MySQL 容器
docker ps -a | findstr mysql
```

### 启动/停止容器
```bash
# 启动容器
docker start mysql

# 停止容器
docker stop mysql

# 重启容器
docker restart mysql
```

### 查看日志
```bash
# 查看 MySQL 日志
docker logs mysql

# 实时查看日志
docker logs -f mysql
```

### 进入容器
```bash
# 进入 MySQL 容器
docker exec -it mysql bash

# 在容器内连接 MySQL
mysql -u root -p
```

## 🔍 连接信息

根据你的 Docker 容器配置，MySQL 连接信息可能是：

**默认配置：**
- 主机：`localhost` 或 `127.0.0.1`
- 端口：`3306`
- 用户：`root`
- 密码：需要查看容器启动时的配置

**查看容器端口映射：**
```bash
docker ps --format "{{.Names}}: {{.Ports}}"
```

**查看容器环境变量：**
```bash
docker inspect mysql | findstr MYSQL_ROOT_PASSWORD
```

## ⚙️ 配置后端连接

编辑 `hospital-edc-backend/start.bat`，确保 `DATABASE_URL` 正确：

```batch
set DATABASE_URL=mysql+pymysql://root:你的密码@127.0.0.1:3306/hospital_edc
```

如果不知道密码，可以：

**方法1：重置密码**
```bash
docker exec -it mysql mysql -u root -p
# 进入后执行：
ALTER USER 'root'@'%' IDENTIFIED BY 'edc123456';
FLUSH PRIVILEGES;
```

**方法2：创建新容器**
```bash
# 停止并删除旧容器
docker stop mysql
docker rm mysql

# 创建新容器（设置密码为 edc123456）
docker run -d --name mysql \
  -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=edc123456 \
  -e MYSQL_DATABASE=hospital_edc \
  mysql:8.0
```

## 🎯 初始化数据库

**方法1：使用 Python 脚本**
```bash
cd hospital-edc-backend
python scripts/init_multi_center.py
```

**方法2：手动创建数据库**
```bash
# 进入容器
docker exec -it mysql mysql -u root -p

# 创建数据库
CREATE DATABASE hospital_edc DEFAULT CHARACTER SET utf8mb4;
exit

# 运行初始化脚本
cd hospital-edc-backend
python scripts/init_multi_center.py
```

**方法3：导入 SQL 文件**
```bash
# 复制 SQL 文件到容器
docker cp migrations/multi_center_migration.sql mysql:/tmp/

# 在容器内执行
docker exec -it mysql mysql -u root -p hospital_edc < /tmp/multi_center_migration.sql
```

## 🆘 常见问题

### Q: Docker Desktop 未启动
**现象：** 运行脚本提示 "Docker 未运行"
**解决：**
1. 打开 Docker Desktop 应用
2. 等待底部显示 "Engine running"
3. 重新运行启动脚本

### Q: 容器启动失败
**现象：** 容器无法启动或立即停止
**解决：**
```bash
# 查看错误日志
docker logs mysql

# 常见原因：
# 1. 端口被占用 → 修改端口映射
# 2. 数据损坏 → 删除容器重建
# 3. 内存不足 → 增加 Docker 内存限制
```

### Q: 无法连接到 MySQL
**现象：** 后端提示数据库连接失败
**解决：**
1. 确认容器正在运行：`docker ps`
2. 确认端口映射：`docker ps` 查看 PORTS 列
3. 确认密码正确：检查 `start.bat` 中的 `DATABASE_URL`
4. 测试连接：
   ```bash
   docker exec -it mysql mysql -u root -p
   ```

### Q: 数据丢失
**现象：** 重启容器后数据不见了
**原因：** 容器被删除（`docker rm`）会丢失数据
**解决：** 使用数据卷持久化数据
```bash
docker run -d --name mysql \
  -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=edc123456 \
  -v mysql_data:/var/lib/mysql \
  mysql:8.0
```

## 💡 最佳实践

### 1. 设置 Docker Desktop 自动启动
- 打开 Docker Desktop
- Settings → General
- 勾选 "Start Docker Desktop when you log in"

### 2. 使用数据卷
```bash
# 创建数据卷
docker volume create mysql_data

# 使用数据卷运行容器
docker run -d --name mysql \
  -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=edc123456 \
  -e MYSQL_DATABASE=hospital_edc \
  -v mysql_data:/var/lib/mysql \
  mysql:8.0
```

### 3. 定期备份
```bash
# 备份数据库
docker exec mysql mysqldump -u root -pedc123456 hospital_edc > backup.sql

# 恢复数据库
docker exec -i mysql mysql -u root -pedc123456 hospital_edc < backup.sql
```

### 4. 使用 Docker Compose（推荐）
创建 `docker-compose.yml`：
```yaml
version: '3.8'
services:
  mysql:
    image: mysql:8.0
    container_name: hospital-edc-mysql
    ports:
      - "3306:3306"
    environment:
      MYSQL_ROOT_PASSWORD: edc123456
      MYSQL_DATABASE: hospital_edc
    volumes:
      - mysql_data:/var/lib/mysql
    restart: unless-stopped

volumes:
  mysql_data:
```

启动：
```bash
docker-compose up -d
```

## 📚 相关文档

- **每日使用**：[DAILY_USAGE.md](DAILY_USAGE.md)
- **快速开始**：[QUICK_START.md](QUICK_START.md)
- **完整指南**：[MULTI_CENTER_GUIDE.md](MULTI_CENTER_GUIDE.md)

---

**记住**：使用 Docker 版本时，用 `start_all_docker.bat` 代替 `start_all.bat`！
