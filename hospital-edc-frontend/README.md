# 前端项目结构说明

## 目录结构

```
hospital-edc-frontend/
├── index.html          # 主HTML文件（模块化版本）
├── css/                # 样式文件
│   ├── main.css       # 主样式（全局、侧边栏、表单等）
│   └── auth.css       # 登录/注册页面样式
├── js/                 # JavaScript模块
│   ├── config.js      # 配置和工具函数（API、Token管理）
│   ├── auth.js        # 认证功能（登录、注册、登出）
│   ├── navigation.js  # 页面导航和标签页切换
│   └── app.js         # 应用主逻辑（初始化、仪表板、患者管理等）
└── pages/              # 页面模板（预留，用于未来扩展）
```

## 文件说明

### HTML文件
- **index.html**: 新的模块化主页面，包含基本结构和登录/注册表单

### CSS文件
- **main.css**: 包含全局样式、侧边栏、表单、动画等通用样式
- **auth.css**: 登录和注册页面的专用样式

### JavaScript模块

#### config.js
- API基础配置
- Token管理函数（getToken, setToken, clearToken）
- 用户信息管理（getUser, setUser）
- API请求封装函数

#### auth.js
- `doLogin()`: 登录功能
- `doRegister()`: 注册功能（支持邀请码）
- `doLogout()`: 登出功能
- `toggleAuthForm()`: 登录/注册表单切换
- `onLoginSuccess()`: 登录成功处理

#### navigation.js
- `showPage()`: 页面切换
- `switchTab()`: 标签页切换

#### app.js
- 应用初始化
- `loadDashboard()`: 加载仪表板数据
- `loadPatients()`: 加载患者列表
- `renderPatientTable()`: 渲染患者表格
- 其他业务逻辑函数

## 使用方法

### 开发环境

**重要**: 确保后端服务已启动（默认运行在 `http://localhost:8000`）

直接在浏览器中打开 `index.html` 文件即可，或使用本地服务器：

```bash
# 使用Python启动简单HTTP服务器
cd hospital-edc-frontend
python -m http.server 8080

# 或使用Node.js的http-server
npx http-server -p 8080
```

然后访问 `http://localhost:8080`

### 启动后端服务

在使用前端之前，请确保后端服务正在运行：

```bash
cd hospital-edc-backend
python -m uvicorn app.main:app --reload
```

后端服务将在 `http://localhost:8000` 启动。

### 生产环境
将整个 `hospital-edc-frontend` 目录部署到Web服务器（如Nginx、Apache）即可。

## 与原版本的区别

### 原版本（糖尿病研究 EDC 系统 Demo.html）
- 单个HTML文件，包含所有代码
- 约27000+ tokens，难以维护
- 所有CSS、JavaScript都内联在HTML中

### 新版本（hospital-edc-frontend/）
- 模块化结构，代码分离
- 易于维护和扩展
- CSS和JavaScript独立文件
- 更好的代码组织

## 功能特性

### 已实现
- ✅ 用户登录
- ✅ 用户注册（邀请码）
- ✅ 登录/注册表单切换
- ✅ Token管理
- ✅ 基础页面导航
- ✅ 仪表板框架
- ✅ 患者列表框架

### 待完善
- ⏳ 完整的患者管理功能
- ⏳ 数据录入功能
- ⏳ 知情同意功能
- ⏳ 已录入患者列表
- ⏳ 表单验证和提交
- ⏳ 更多业务逻辑

## 注意事项

1. **API地址配置**: 在 `js/config.js` 中修改 `API_BASE` 变量
2. **跨域问题**: 如果前后端分离部署，需要配置CORS
3. **原HTML文件**: 原 `糖尿病研究 EDC 系统 Demo.html` 文件保持不变，可以继续使用

## 后续扩展建议

1. 将更多功能从原HTML文件迁移到模块化版本
2. 考虑使用构建工具（Webpack、Vite等）
3. 引入前端框架（Vue、React等）进行重构
4. 添加单元测试
5. 优化性能和用户体验
