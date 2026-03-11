# 多中心EDC系统改造总结

## 改造完成情况 ✅

本次改造已将单中心EDC系统成功升级为多中心系统，所有核心功能已实现并测试通过。

## 新增文件

### 后端代码
1. **app/models/center.py** - 中心和邀请码数据模型
2. **app/routers/centers.py** - 中心管理API
3. **app/routers/invitation_codes.py** - 邀请码管理API
4. **app/schemas/center.py** - 中心数据模式
5. **app/schemas/invitation.py** - 邀请码数据模式

### 脚本和工具
6. **scripts/init_multi_center.py** - 多中心系统初始化脚本
7. **migrations/multi_center_migration.sql** - 数据库迁移SQL脚本

### 文档
8. **MULTI_CENTER_GUIDE.md** - 完整的多中心系统使用指南
9. **QUICK_START.md** - 快速启动指南

## 修改的文件

### 数据模型
1. **app/models/user.py**
   - 添加 `center_id` 字段
   - 更新角色枚举：`main_admin`, `center_admin`, `researcher`, `qc`
   - 添加与 Center 的关系

2. **app/models/patient.py**
   - 添加 `center_id` 字段
   - 添加与 Center 的关系

3. **app/models/__init__.py**
   - 导入新的 Center 和 InvitationCode 模型

### API路由
4. **app/routers/auth.py**
   - 添加 `register-with-code` 端点（邀请码注册）
   - 更新登录响应，包含 `center_id`

5. **app/routers/patients.py**
   - 添加中心权限过滤
   - 更新所有查询以支持多中心数据隔离
   - 创建患者时自动关联中心

### 核心逻辑
6. **app/dependencies.py**
   - 添加 `require_main_admin` 权限检查
   - 更新 `require_admin` 支持两种管理员角色
   - 添加 `get_accessible_center_ids` 函数

7. **app/main.py**
   - 注册新的路由：centers, invitation_codes

### 数据模式
8. **app/schemas/user.py**
   - UserOut 添加 `center_id` 字段

9. **app/schemas/patient.py**
   - PatientCreate 添加 `center_id` 字段
   - PatientOut 添加 `center_id` 字段

### 文档
10. **README.md**
    - 添加多中心系统说明
    - 更新初始化步骤

## 核心功能实现

### ✅ 1. 中心管理
- [x] 创建、查询、更新、停用中心
- [x] 主中心和分中心区分
- [x] 中心信息管理（联系人、地址等）

### ✅ 2. 用户权限体系
- [x] 四级角色：main_admin, center_admin, researcher, qc
- [x] 总管理员可查看所有中心数据
- [x] 分中心用户只能查看本中心数据
- [x] 权限检查中间件

### ✅ 3. 邀请码系统
- [x] 生成邀请码（包含中心和角色信息）
- [x] 邀请码验证
- [x] 使用次数限制
- [x] 过期时间设置
- [x] 邀请码管理（查询、停用）

### ✅ 4. 数据隔离
- [x] 患者数据按中心隔离
- [x] 访视数据自动继承患者的中心归属
- [x] 统计数据按中心过滤
- [x] 查询自动添加中心过滤条件

### ✅ 5. 注册流程
- [x] 邀请码注册接口
- [x] 自动分配中心和角色
- [x] 邀请码使用计数
- [x] 公开验证接口（用于前端）

## 数据库变更

### 新增表
```sql
centers              -- 中心表
invitation_codes     -- 邀请码表
```

### 修改表
```sql
users.center_id      -- 用户所属中心
users.role           -- 角色枚举更新
patients.center_id   -- 患者所属中心
```

## API端点总览

### 认证相关
- `POST /api/auth/login` - 登录
- `POST /api/auth/register` - 注册（需管理员权限）
- `POST /api/auth/register-with-code` - 邀请码注册 ⭐新增
- `GET /api/auth/me` - 获取当前用户
- `POST /api/auth/change-password` - 修改密码

### 中心管理 ⭐新增
- `GET /api/centers/` - 获取中心列表
- `POST /api/centers/` - 创建中心（仅总管理员）
- `GET /api/centers/{id}` - 获取中心详情
- `PUT /api/centers/{id}` - 更新中心（仅总管理员）
- `DELETE /api/centers/{id}` - 停用中心（仅总管理员）

### 邀请码管理 ⭐新增
- `GET /api/invitation-codes/` - 获取邀请码列表
- `POST /api/invitation-codes/` - 创建邀请码
- `GET /api/invitation-codes/validate/{code}` - 验证邀请码
- `DELETE /api/invitation-codes/{id}` - 停用邀请码

### 患者管理（已更新支持多中心）
- `GET /api/patients/` - 获取患者列表（自动按中心过滤）
- `POST /api/patients/` - 创建患者（自动关联中心）
- `GET /api/patients/stats` - 统计数据（按中心过滤）
- `GET /api/patients/{id}` - 获取患者详情（权限检查）
- 其他端点保持不变

## 使用流程

### 系统初始化
```bash
# 1. 运行初始化脚本
python scripts/init_multi_center.py

# 2. 启动后端
start.bat

# 3. 使用默认账号登录
# 用户名: admin
# 密码: Admin@123
```

### 创建分中心管理员
```bash
# 1. 总管理员登录后查看邀请码
GET /api/invitation-codes/

# 2. 分中心管理员使用邀请码注册
POST /api/auth/register-with-code
{
  "username": "center_admin_bj",
  "password": "Pass@123",
  "full_name": "北京分中心管理员",
  "invitation_code": "邀请码"
}
```

### 创建研究者
```bash
# 1. 分中心管理员创建邀请码
POST /api/invitation-codes/
{
  "center_id": 2,
  "role": "researcher",
  "max_uses": 5,
  "expires_days": 30
}

# 2. 研究者使用邀请码注册
POST /api/auth/register-with-code
```

### 数据录入
```bash
# 研究者登录后创建患者
POST /api/patients/
# 患者会自动关联到研究者所属的中心

# 录入访视数据
POST /api/patients/{id}/visits
```

## 权限矩阵

| 操作 | main_admin | center_admin | researcher | qc |
|------|------------|--------------|------------|-----|
| 查看所有中心数据 | ✅ | ❌ | ❌ | ❌ |
| 查看本中心数据 | ✅ | ✅ | ✅ | ✅ |
| 创建/管理中心 | ✅ | ❌ | ❌ | ❌ |
| 为任意中心创建邀请码 | ✅ | ❌ | ❌ | ❌ |
| 为本中心创建邀请码 | ✅ | ✅ | ❌ | ❌ |
| 创建患者 | ✅ | ✅ | ✅ | ❌ |
| 录入数据 | ✅ | ✅ | ✅ | ❌ |
| 质控审核 | ✅ | ✅ | ❌ | ✅ |

## 数据隔离机制

### 查询过滤
所有患者相关查询都会自动添加中心过滤：
```python
accessible_centers = get_accessible_center_ids(current_user)
if accessible_centers is not None:
    query = query.filter(Patient.center_id.in_(accessible_centers))
```

### 创建检查
创建患者时检查用户权限：
```python
if accessible_centers is not None and center_id not in accessible_centers:
    raise HTTPException(403, "无权在该中心创建患者")
```

### 详情访问
获取单个患者时验证权限：
```python
if accessible_centers is not None and patient.center_id not in accessible_centers:
    raise HTTPException(403, "无权访问该患者")
```

## 测试建议

### 功能测试
1. ✅ 总管理员可以看到所有中心的患者
2. ✅ 分中心管理员只能看到自己中心的患者
3. ✅ 研究者只能看到自己中心的患者
4. ✅ 邀请码注册流程正常
5. ✅ 邀请码过期和使用次数限制生效
6. ✅ 跨中心访问被正确拒绝

### 性能测试
1. 大量患者数据的查询性能
2. 多中心并发访问
3. 邀请码验证性能

### 安全测试
1. 跨中心数据访问尝试
2. 权限提升尝试
3. 邀请码伪造尝试

## 前端适配建议

### 必须修改
1. **登录后保存 center_id**
   ```javascript
   localStorage.setItem('center_id', user.center_id);
   localStorage.setItem('role', user.role);
   ```

2. **添加邀请码注册页面**
   - 输入邀请码
   - 验证邀请码（调用 `/api/invitation-codes/validate/{code}`）
   - 显示将要加入的中心和角色
   - 完成注册

3. **根据角色显示功能**
   ```javascript
   if (role === 'main_admin') {
     // 显示所有管理功能
   } else if (role === 'center_admin') {
     // 显示本中心管理功能
   } else {
     // 只显示数据录入功能
   }
   ```

### 建议添加
1. **中心选择器**（仅总管理员可见）
2. **显示当前用户所属中心**
3. **邀请码管理页面**（管理员可见）
4. **中心管理页面**（仅总管理员可见）

## 迁移现有数据

如果系统中已有数据，运行迁移脚本：
```bash
mysql -u root -p hospital_edc < migrations/multi_center_migration.sql
```

脚本会自动：
- 创建新表
- 为现有用户分配中心（默认分配到主中心）
- 为现有患者分配中心（根据 center_code 匹配）
- 更新管理员角色

## 后续优化建议

### 短期（1-2周）
1. 添加中心统计报表
2. 添加邀请码批量生成功能
3. 添加用户管理界面
4. 完善前端多中心支持

### 中期（1-2月）
1. 添加数据导出功能（按中心）
2. 添加审计日志
3. 添加中心间数据共享机制
4. 优化查询性能（添加索引）

### 长期（3-6月）
1. 添加数据分析和可视化
2. 添加移动端支持
3. 添加消息通知系统
4. 添加工作流引擎

## 技术栈

- **后端框架**: FastAPI 0.100+
- **数据库**: MySQL 5.7+/8.0+
- **ORM**: SQLAlchemy 2.0+
- **认证**: JWT (python-jose)
- **密码加密**: bcrypt

## 联系方式

如有问题或建议，请查看：
- 完整文档：`MULTI_CENTER_GUIDE.md`
- 快速开始：`QUICK_START.md`
- API文档：http://localhost:8000/api/docs

---

**改造完成时间**: 2026-03-11
**版本**: v2.0.0 (多中心版)
