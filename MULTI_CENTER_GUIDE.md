# 多中心EDC系统改造说明

## 概述

本系统已改造为支持多中心的EDC（电子数据采集）系统。多个研究中心共用一套部署，通过数据库中的 `center_id` 字段区分数据。

## 核心功能

### 1. 中心管理
- 支持主中心和多个分中心
- 主中心可以查看和管理所有中心的数据
- 分中心只能查看和管理自己中心的数据

### 2. 用户角色
系统支持以下角色：
- **main_admin（总中心管理员）**：可以查看所有中心的数据，管理所有中心和用户
- **center_admin（分中心管理员）**：只能查看和管理自己中心的数据和用户
- **researcher（研究者）**：只能查看和管理自己中心的患者数据
- **qc（质控员）**：只能查看和管理自己中心的数据

### 3. 邀请码注册系统
- 管理员可以生成邀请码
- 邀请码包含中心信息和角色信息
- 用户使用邀请码注册时自动分配到对应中心和角色
- 邀请码支持：
  - 使用次数限制
  - 过期时间设置
  - 启用/停用状态

## 数据库变更

### 新增表

#### centers（中心表）
```sql
CREATE TABLE centers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    center_code VARCHAR(20) UNIQUE NOT NULL,
    center_name VARCHAR(100) NOT NULL,
    is_main_center BOOLEAN DEFAULT FALSE,
    contact_person VARCHAR(100),
    contact_phone VARCHAR(20),
    contact_email VARCHAR(100),
    address VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP
);
```

#### invitation_codes（邀请码表）
```sql
CREATE TABLE invitation_codes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(50) UNIQUE NOT NULL,
    center_id INT NOT NULL,
    role VARCHAR(20) NOT NULL,
    max_uses INT DEFAULT 1,
    used_count INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    expires_at DATETIME,
    created_by INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 修改的表

#### users（用户表）
- 新增字段：`center_id INT` - 用户所属中心
- 修改字段：`role` 枚举值改为 `("researcher", "qc", "center_admin", "main_admin")`

#### patients（患者表）
- 新增字段：`center_id INT NOT NULL` - 患者所属中心

## API接口

### 认证相关

#### POST /api/auth/register-with-code
使用邀请码注册新账号
```json
{
  "username": "user001",
  "password": "Password@123",
  "full_name": "张三",
  "invitation_code": "邀请码"
}
```

#### POST /api/auth/login
登录（保持不变）

### 中心管理

#### GET /api/centers/
获取中心列表（需要登录）

#### POST /api/centers/
创建新中心（仅总管理员）
```json
{
  "center_code": "CHN-020",
  "center_name": "深圳分中心",
  "is_main_center": false,
  "contact_person": "李四",
  "contact_phone": "13800138000",
  "contact_email": "lisi@example.com",
  "address": "深圳市..."
}
```

#### GET /api/centers/{center_id}
获取中心详情

#### PUT /api/centers/{center_id}
更新中心信息（仅总管理员）

#### DELETE /api/centers/{center_id}
停用中心（仅总管理员）

### 邀请码管理

#### GET /api/invitation-codes/
获取邀请码列表（需要管理员权限）
- 总管理员可以看到所有邀请码
- 分中心管理员只能看到自己中心的邀请码

#### POST /api/invitation-codes/
创建邀请码（需要管理员权限）
```json
{
  "center_id": 2,
  "role": "researcher",
  "max_uses": 5,
  "expires_days": 30
}
```

#### GET /api/invitation-codes/validate/{code}
验证邀请码（公开接口，用于注册页面）

#### DELETE /api/invitation-codes/{code_id}
停用邀请码（需要管理员权限）

### 患者管理

#### GET /api/patients/
获取患者列表
- 总管理员可以看到所有中心的患者
- 其他用户只能看到自己中心的患者

#### POST /api/patients/
创建患者
- 患者会自动关联到用户所属的中心

#### GET /api/patients/stats
获取统计数据
- 根据用户权限返回对应中心的统计数据

## 初始化步骤

### 1. 数据库准备
确保MySQL已启动，数据库已创建：
```sql
CREATE DATABASE hospital_edc DEFAULT CHARACTER SET utf8mb4;
```

### 2. 运行初始化脚本
```bash
cd hospital-edc-backend
python scripts/init_multi_center.py
```

此脚本会：
- 创建主中心（CHN-001）
- 创建3个示例分中心（CHN-017, CHN-018, CHN-019）
- 创建总管理员账号（admin / Admin@123）
- 为每个分中心生成管理员邀请码

### 3. 启动后端
```bash
cd hospital-edc-backend
start.bat
```

### 4. 登录系统
使用总管理员账号登录：
- 用户名：admin
- 密码：Admin@123

## 使用流程

### 创建分中心管理员
1. 总管理员登录系统
2. 访问 `/api/invitation-codes/` 查看邀请码
3. 将邀请码发送给分中心管理员
4. 分中心管理员使用邀请码注册账号

### 创建研究者账号
1. 分中心管理员登录系统
2. 创建邀请码（role设为"researcher"）
3. 将邀请码发送给研究者
4. 研究者使用邀请码注册账号

### 数据录入
1. 研究者登录系统
2. 创建患者（自动关联到研究者所属中心）
3. 录入访视数据
4. 提交表单

### 数据查看
- **总管理员**：可以查看所有中心的患者和数据
- **分中心管理员/研究者**：只能查看自己中心的患者和数据

## 权限控制

### 数据访问权限
系统通过 `get_accessible_center_ids()` 函数控制数据访问：
- `main_admin`：返回 `None`（表示可访问所有中心）
- 其他角色：返回 `[user.center_id]`（只能访问自己的中心）

### API权限
- `require_admin`：需要管理员权限（center_admin 或 main_admin）
- `require_main_admin`：需要总管理员权限（仅 main_admin）

## 注意事项

1. **数据隔离**：分中心之间的数据完全隔离，互不可见
2. **邀请码安全**：邀请码应妥善保管，避免泄露
3. **角色分配**：创建邀请码时要正确设置角色
4. **中心归属**：患者一旦创建，其中心归属不可更改
5. **权限检查**：所有数据操作都会检查用户的中心权限

## 迁移现有数据

如果系统中已有数据，需要：
1. 为现有用户分配 `center_id`
2. 为现有患者分配 `center_id`
3. 更新现有管理员的角色为 `main_admin` 或 `center_admin`

可以使用以下SQL：
```sql
-- 更新现有管理员为总管理员
UPDATE users SET role = 'main_admin', center_id = 1 WHERE role = 'admin';

-- 为现有患者分配中心（根据center_code）
UPDATE patients p
JOIN centers c ON p.center_code = c.center_code
SET p.center_id = c.id;
```

## 前端适配建议

1. **登录后保存用户信息**：包括 `center_id` 和 `role`
2. **根据角色显示功能**：
   - 总管理员显示所有管理功能
   - 分中心管理员显示本中心管理功能
   - 研究者只显示数据录入功能
3. **添加中心选择器**（仅总管理员可见）
4. **显示当前用户所属中心**
5. **邀请码注册页面**：
   - 输入邀请码后自动验证
   - 显示将要加入的中心名称和角色

## 测试建议

1. 测试总管理员可以看到所有数据
2. 测试分中心管理员只能看到自己中心的数据
3. 测试邀请码注册流程
4. 测试邀请码过期和使用次数限制
5. 测试跨中心数据访问被拒绝
