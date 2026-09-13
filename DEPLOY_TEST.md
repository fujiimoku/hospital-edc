# 测试服务器部署手册(阿里云 ECS · 从零到可访问)

> 适用场景:初步部署测试。单实例、IP 直连 HTTP、只放演示数据。
> 正式对医院开放前,须完成:域名 → ICP 备案 → HTTPS → 等保评估(见 `服务器租用明细(客户对齐版).md`)。

---

## 0. 推荐服务器配置(选购时对照)

| 项目 | 选择 |
|---|---|
| 实例 | 通用算力型 u1 · ecs.u1-c1m2.large(2 vCPU / 4 GiB);最低预算可用经济型 e 2C2G |
| 地域 | 华北2(北京) |
| 镜像 | Ubuntu 22.04 64 位 |
| 系统盘 | ESSD Entry 40 GiB |
| 带宽 | 按使用流量,峰值 10 Mbps |
| 安全组 | 放行 80(测试期);SSH(22)限自己 IP;443 可先放行备用 |

> 买完顺手在 ECS 控制台开启「自动快照:每天 1 次、保留 7 天」。

## 1. 安装 Docker(Ubuntu 22.04)

```bash
ssh root@<服务器IP>

# 官方脚本装 Docker Engine + Compose 插件
curl -fsSL https://get.docker.com | bash
systemctl enable --now docker
docker compose version   # 确认 v2 可用
```

国内网络慢可用阿里镜像源安装:
```bash
curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun
```

## 2. 拿到代码

二选一:

```bash
# 方式 A:git(推荐;服务器能访问仓库时)
git clone <仓库地址> hospital-edc && cd hospital-edc

# 方式 B:本地打包上传(仓库未对外时)
# 本机: git archive -o edc.tar.gz HEAD
# 本机: scp edc.tar.gz root@<服务器IP>:~
# 服务器: mkdir hospital-edc && tar xzf edc.tar.gz -C hospital-edc && cd hospital-edc
```

## 3. 配置生产环境变量

```bash
cp hospital-edc-backend/.env.production.example hospital-edc-backend/.env.production
vim hospital-edc-backend/.env.production
```

三个密钥全部替换为强随机值(文件内有生成命令):
- `MYSQL_ROOT_PASSWORD`
- `SECRET_KEY`
- `FIELD_ENCRYPTION_KEY` ⚠️ 录入数据后永不可改

## 4. 启动

```bash
docker compose --env-file hospital-edc-backend/.env.production \
  -f docker-compose.prod.yml up -d --build
```

编排内容:MySQL 8.4(调优适配 4G 内存)+ 后端 2 worker + Nginx 80 入口 + 每日自动备份(保留 14 天,落 `./backups/`)。

## 5. 初始化与验证

```bash
# 建总管理员 + 7 中心 + 邀请码(在 backend 容器内执行)
docker compose -f docker-compose.prod.yml exec backend \
  python scripts/init_multi_center.py

# (可选)灌演示数据
docker compose -f docker-compose.prod.yml exec backend \
  python scripts/seed_demo.py
```

浏览器验证清单:
- [ ] `http://<IP>/` 打开登录页
- [ ] `http://<IP>/api/docs` API 文档可访问
- [ ] admin / Admin@123 登录(**登录后立即改密码**)
- [ ] 建患者 → 录入 → 提交 → 质控审计页走一遍
- [ ] 演示数据被清理/重灌正常

```bash
# 容器健康检查(4 个容器都应为 Up/healthy)
docker compose -f docker-compose.prod.yml ps

# 手动触发一次备份验证
docker exec edc-prod-backup sh -c \
  'mysqldump -h mysql -u root -p"$MYSQL_PWD" --single-transaction edc_prod | gzip > /backups/edc_manual.sql.gz'
ls -lh backups/
```

## 6. 日常运维

```bash
# 更新代码后重新部署
git pull   # 或重新上传
docker compose --env-file hospital-edc-backend/.env.production \
  -f docker-compose.prod.yml up -d --build

# 看日志
docker compose -f docker-compose.prod.yml logs -f backend --tail 100

# 连数据库(宿主机本机)
docker exec -it edc-prod-mysql mysql -u root -p edc_prod

# 恢复备份(新库或灾难恢复)
gunzip < backups/edc_YYYYMMDD_HHMMSS.sql.gz | \
  docker exec -i edc-prod-mysql mysql -u root -p edc_prod
```

## 7. 测试期红线

- ❌ 不录真实患者数据(无 HTTPS、无备案、无等保)
- ❌ 不把 3306 / 8000 端口暴露公网(当前配置已只绑本机/Nginx 内网)
- ✅ 每日备份自动落盘;建议再配 `crontab` 用 ossutil 同步 `./backups/` 到 OSS
- ✅ admin 初始密码 Admin@123 部署完成后立即修改

## 8. 转正式时要做的事

1. 域名购买 + ICP 备案(医院主体,10-20 工作日)
2. `deploy/nginx.prod.conf` 启用 443 段 + 免费证书(阿里云可免费申请 DV 证书)
3. 评估是否需要等保测评(医院信息科/伦理确认)
4. 视数据量决定是否迁移到 RDS(测试期单机 MySQL 足够)
