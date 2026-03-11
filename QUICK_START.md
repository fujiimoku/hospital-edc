# 多中心EDC系统快速启动指南

## 快速开始（3步）

### 第1步：准备数据库
```bash
# 启动MySQL，创建数据库
mysql -u root -p
CREATE DATABASE hospital_edc DEFAULT CHARACTER SET utf8mb4;
exit
```

### 第2步：运行迁移脚本
```bash
cd hospital-edc-backend

# 方式1：使用SQL脚本（推荐用于现有数据库）
mysql -u root -p hospital_edc < migrations/multi_center_migration.sql

# 方式2：使用Python初始化脚本（推荐用于新数据库）
python scripts/init_multi_center.py
```

### 第3步：启动后端
```bash
cd hospital-edc-backend
start.bat
```

访问 http://localhost:8000/api/docs 查看API文档

## 默认账号

**总管理员账号：**
- 用户名：`admin`
- 密码：`Admin@123`

## 快速测试流程

### 1. 登录总管理员
```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=Admin@123"
```

### 2. 查看中心列表
```bash
curl -X GET "http://localhost:8000/api/centers/" \
  -H "Authorization: Bearer <your_token>"
```

### 3. 查看邀请码
```bash
curl -X GET "http://localhost:8000/api/invitation-codes/" \
  -H "Authorization: Bearer <your_token>"
```

### 4. 创建邀请码
```bash
curl -X POST "http://localhost:8000/api/invitation-codes/" \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "center_id": 2,
    "role": "researcher",
    "max_uses": 5,
    "expires_days": 30
  }'
```

### 5. 使用邀请码注册
```bash
curl -X POST "http://localhost:8000/api/auth/register-with-code" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "researcher001",
    "password": "Pass@123",
    "full_name": "研究员001",
    "invitation_code": "<邀请码>"
  }'
```

## 系统架构

```
多中心EDC系统
├── 总中心 (CHN-001)
│   └── 总管理员 (main_admin)
│       ├── 可查看所有中心数据
│       ├── 管理所有中心
│       └── 生成邀请码
│
├── 分中心1 (CHN-017)
│   ├── 分中心管理员 (center_admin)
│   │   ├── 只能查看本中心数据
│   │   └── 为本中心生成邀请码
│   └── 研究者 (researcher)
│       └── 录入本中心患者数据
│
├── 分中心2 (CHN-018)
└── 分中心3 (CHN-019)
```

## 核心API端点

### 认证
- `POST /api/auth/login` - 登录
- `POST /api/auth/register-with-code` - 使用邀请码注册
- `GET /api/auth/me` - 获取当前用户信息

### 中心管理（需要管理员权限）
- `GET /api/centers/` - 获取中心列表
- `POST /api/centers/` - 创建中心（仅总管理员）
- `GET /api/centers/{id}` - 获取中心详情
- `PUT /api/centers/{id}` - 更新中心（仅总管理员）

### 邀请码管理（需要管理员权限）
- `GET /api/invitation-codes/` - 获取邀请码列表
- `POST /api/invitation-codes/` - 创建邀请码
- `GET /api/invitation-codes/validate/{code}` - 验证邀请码（公开）
- `DELETE /api/invitation-codes/{id}` - 停用邀请码

### 患者管理（自动按中心过滤）
- `GET /api/patients/` - 获取患者列表
- `POST /api/patients/` - 创建患者
- `GET /api/patients/stats` - 获取统计数据

## 权限说明

| 角色 | 权限 |
|------|------|
| main_admin | 查看所有中心数据、管理所有中心、创建任意中心的邀请码 |
| center_admin | 查看本中心数据、为本中心创建邀请码 |
| researcher | 查看和录入本中心患者数据 |
| qc | 查看本中心数据、进行质控 |

## 常见问题

### Q: 如何添加新的分中心？
A: 使用总管理员账号调用 `POST /api/centers/` 接口

### Q: 如何为分中心创建管理员？
A:
1. 总管理员创建邀请码（role设为"center_admin"）
2. 将邀请码发送给分中心管理员
3. 分中心管理员使用邀请码注册

### Q: 分中心管理员如何添加研究者？
A:
1. 分中心管理员登录
2. 创建邀请码（role设为"researcher"）
3. 将邀请码发送给研究者
4. 研究者使用邀请码注册

### Q: 如何迁移现有数据？
A: 运行 `migrations/multi_center_migration.sql` 脚本，会自动：
- 创建新表
- 为现有用户和患者分配中心
- 更新管理员角色

### Q: 邀请码可以重复使用吗？
A: 可以，创建邀请码时设置 `max_uses` 参数即可

### Q: 邀请码会过期吗？
A: 会，创建邀请码时设置 `expires_days` 参数

## 下一步

1. 查看完整文档：[MULTI_CENTER_GUIDE.md](MULTI_CENTER_GUIDE.md)
2. 访问API文档：http://localhost:8000/api/docs
3. 根据需求调整前端页面以支持多中心功能

## 技术支持

如有问题，请查看：
- 完整文档：`MULTI_CENTER_GUIDE.md`
- API文档：http://localhost:8000/api/docs
- 数据库迁移脚本：`migrations/multi_center_migration.sql`
- 初始化脚本：`scripts/init_multi_center.py`
