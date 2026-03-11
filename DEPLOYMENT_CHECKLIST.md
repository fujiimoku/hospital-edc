# 多中心EDC系统部署检查清单

## 部署前检查

### 环境准备
- [ ] Python 3.10+ 已安装
- [ ] MySQL 5.7+/8.0+ 已安装并运行
- [ ] 数据库 `hospital_edc` 已创建
- [ ] 数据库连接信息已配置（DATABASE_URL）
- [ ] 所有Python依赖已安装（`pip install -r requirements.txt`）

### 数据库初始化
- [ ] 已运行数据库迁移脚本
  - [ ] 方式1：`mysql -u root -p hospital_edc < migrations/multi_center_migration.sql`
  - [ ] 方式2：`python scripts/init_multi_center.py`
- [ ] 已验证表结构正确（centers, invitation_codes, users, patients等）
- [ ] 已创建总管理员账号
- [ ] 已创建主中心和分中心

### 后端服务
- [ ] 后端服务可以正常启动（`start.bat` 或 `uvicorn app.main:app`）
- [ ] API文档可以访问（http://localhost:8000/api/docs）
- [ ] 健康检查通过（http://localhost:8000/）

### 功能测试
- [ ] 总管理员可以登录
- [ ] 可以查看中心列表
- [ ] 可以查看邀请码列表
- [ ] 可以创建新的邀请码
- [ ] 可以使用邀请码注册新用户

## 部署步骤

### 1. 克隆代码
```bash
git clone <repository_url>
cd hospital-edc
```

### 2. 安装依赖
```bash
cd hospital-edc-backend
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
# source venv/bin/activate    # Linux/Mac
pip install -r requirements.txt
```

### 3. 配置数据库
```bash
# 修改 start.bat 中的 DATABASE_URL
# 或设置环境变量
set DATABASE_URL=mysql+pymysql://root:your_password@localhost/hospital_edc
```

### 4. 初始化数据库
```bash
# 方式1：使用SQL脚本（推荐用于现有数据库）
mysql -u root -p hospital_edc < migrations/multi_center_migration.sql

# 方式2：使用Python脚本（推荐用于新数据库）
python scripts/init_multi_center.py
```

### 5. 启动服务
```bash
# Windows
start.bat

# Linux/Mac
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 6. 验证部署
```bash
# 测试健康检查
curl http://localhost:8000/

# 测试登录
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=Admin@123"
```

## 生产环境额外检查

### 安全配置
- [ ] 修改默认管理员密码
- [ ] 配置HTTPS（使用nginx反向代理）
- [ ] 配置CORS允许的域名（不要使用 `allow_origins=["*"]`）
- [ ] 设置强密码策略
- [ ] 配置JWT密钥（SECRET_KEY）为随机强密钥
- [ ] 配置JWT过期时间（ACCESS_TOKEN_EXPIRE_MINUTES）

### 数据库优化
- [ ] 添加必要的索引
  ```sql
  CREATE INDEX idx_patients_center_id ON patients(center_id);
  CREATE INDEX idx_users_center_id ON users(center_id);
  CREATE INDEX idx_visits_patient_id ON visits(patient_id);
  ```
- [ ] 配置数据库连接池
- [ ] 配置数据库备份策略
- [ ] 启用慢查询日志

### 性能优化
- [ ] 配置Gunicorn/Uvicorn workers数量
- [ ] 配置nginx缓存
- [ ] 配置Redis缓存（可选）
- [ ] 配置CDN（可选）

### 监控和日志
- [ ] 配置应用日志
- [ ] 配置错误监控（如Sentry）
- [ ] 配置性能监控
- [ ] 配置数据库监控
- [ ] 配置告警机制

### 备份策略
- [ ] 配置数据库自动备份
- [ ] 配置代码版本控制
- [ ] 配置配置文件备份
- [ ] 测试恢复流程

## 用户培训检查

### 总管理员培训
- [ ] 如何登录系统
- [ ] 如何查看所有中心数据
- [ ] 如何创建新中心
- [ ] 如何生成邀请码
- [ ] 如何管理用户

### 分中心管理员培训
- [ ] 如何使用邀请码注册
- [ ] 如何查看本中心数据
- [ ] 如何为本中心生成邀请码
- [ ] 如何管理本中心用户

### 研究者培训
- [ ] 如何使用邀请码注册
- [ ] 如何创建患者
- [ ] 如何录入访视数据
- [ ] 如何提交表单

## 文档检查

- [ ] README.md 已更新
- [ ] API文档可访问
- [ ] 用户手册已准备
- [ ] 管理员手册已准备
- [ ] 故障排查指南已准备

## 上线后验证

### 功能验证
- [ ] 总管理员可以登录并查看所有数据
- [ ] 分中心管理员只能看到自己中心的数据
- [ ] 研究者只能看到自己中心的患者
- [ ] 邀请码注册流程正常
- [ ] 数据录入流程正常
- [ ] 数据查询性能正常

### 安全验证
- [ ] 跨中心数据访问被正确拒绝
- [ ] 未授权访问被正确拒绝
- [ ] SQL注入测试通过
- [ ] XSS测试通过
- [ ] CSRF测试通过

### 性能验证
- [ ] 页面加载时间 < 2秒
- [ ] API响应时间 < 500ms
- [ ] 并发用户测试通过
- [ ] 大数据量查询性能正常

## 回滚计划

### 准备工作
- [ ] 备份当前数据库
- [ ] 备份当前代码
- [ ] 准备回滚脚本
- [ ] 测试回滚流程

### 回滚步骤
1. 停止新版本服务
2. 恢复数据库备份
3. 部署旧版本代码
4. 启动旧版本服务
5. 验证功能正常

## 常见问题排查

### 数据库连接失败
- [ ] 检查MySQL是否运行
- [ ] 检查DATABASE_URL配置
- [ ] 检查数据库用户权限
- [ ] 检查防火墙设置

### 登录失败
- [ ] 检查用户名密码是否正确
- [ ] 检查用户是否已创建
- [ ] 检查用户是否被禁用
- [ ] 检查JWT配置

### 邀请码无效
- [ ] 检查邀请码是否存在
- [ ] 检查邀请码是否过期
- [ ] 检查邀请码使用次数
- [ ] 检查邀请码是否被停用

### 权限错误
- [ ] 检查用户角色
- [ ] 检查用户center_id
- [ ] 检查API权限配置
- [ ] 检查token是否有效

## 联系方式

技术支持：
- 文档：查看 MULTI_CENTER_GUIDE.md
- API文档：http://localhost:8000/api/docs
- 问题反馈：[GitHub Issues]

---

**检查人员**: _______________
**检查日期**: _______________
**部署环境**: [ ] 开发 [ ] 测试 [ ] 生产
**部署状态**: [ ] 通过 [ ] 失败
**备注**: _______________
