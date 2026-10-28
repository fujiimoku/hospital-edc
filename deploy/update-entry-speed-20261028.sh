#!/usr/bin/env bash
# Production update: build, stop writes, back up, fingerprint, verify, switch.
# Build from this release checkout; recover the original Compose project from container labels.
set -Eeuo pipefail
umask 077
MAINTENANCE=0
BACKUP_DIR=''
BACKEND=${EDC_BACKEND_CONTAINER:-edc-prod-backend}
NGINX=${EDC_NGINX_CONTAINER:-edc-prod-nginx}
MYSQL=${EDC_MYSQL_CONTAINER:-edc-prod-mysql}

fail() { printf '%s\n' "$*" >&2; return 1; }
on_error() {
  local code=$?
  trap - ERR
  if [[ $MAINTENANCE == 1 ]]; then
    docker stop "$NGINX" >/dev/null 2>&1 || true
    printf '\n更新未完成，网站入口保持停止，数据库未自动回退。\n' >&2
    if [[ -f "$BACKUP_DIR/state.sh" ]]; then
      printf '备份：%s\n如需回退镜像，运行：bash deploy/update-entry-speed-20261028.sh --rollback %q\n' "$BACKUP_DIR" "$BACKUP_DIR" >&2
    fi
  fi
  exit "$code"
}
trap on_error ERR

start_and_check() {
  local override=$1
  "${COMPOSE[@]}" -f "$override" up -d --no-deps --no-build --pull never --wait --wait-timeout 150 backend
  docker exec "$BACKEND" python -c 'from app.database import engine; from sqlalchemy import text; c=engine.connect(); assert c.execute(text("SELECT 1")).scalar()==1; c.close(); print("数据库连接正常")'
  docker start "$NGINX" >/dev/null
  docker exec "$NGINX" nginx -t
  docker exec "$NGINX" nginx -s reload
  docker exec "$NGINX" wget -q -O /dev/null http://127.0.0.1/
}

if [[ ${1:-} == --rollback ]]; then
  [[ $# == 2 && -f "$2/state.sh" ]] || fail '用法：bash deploy/update-entry-speed-20261028.sh --rollback 备份目录'
  # state.sh is written by this script with mode 600 inside the private backup directory.
  source "$2/state.sh"
  [[ -f "$CANDIDATE" ]] || fail '缺少发布状态文件，请勿手动猜测镜像或数据库。'
  MAINTENANCE=1
  docker stop "$NGINX" "$BACKEND" >/dev/null
  ALLOWED=$(docker run --rm --network none -e DATABASE_URL=sqlite:///:memory: -e SECRET_KEY=rollback-import-check -e FIELD_ENCRYPTION_KEY=rollback-import-check "$ROLLBACK_IMAGE" python -c 'import json; from app.models.visit import Visit; print(json.dumps(Visit.__table__.c.visit_type.type.enums))')
  "${COMPOSE[@]}" -f "$CANDIDATE" run --rm --no-deps -T -e "EDC_ALLOWED_VISIT_TYPES=$ALLOWED" backend python -c 'import json,os; from app.database import engine; from sqlalchemy import text; c=engine.connect(); actual={r[0] for r in c.execute(text("SELECT DISTINCT visit_type FROM visits"))}; extra=actual-set(json.loads(os.environ["EDC_ALLOWED_VISIT_TYPES"])); assert not extra, "已有旧镜像不支持的访视，禁止直接回退："+str(sorted(extra)); print("旧镜像访视兼容检查通过")'
  docker run --rm --network none -e DATABASE_URL=sqlite:///:memory: -e SECRET_KEY=rollback-check -e FIELD_ENCRYPTION_KEY=rollback-check "$ROLLBACK_IMAGE" python -c 'from app.models.patient_image import PatientImage; assert "visit_id" in PatientImage.__table__.c, "旧版本不支持访视图片，停止回退"'
  printf '回退仅切换程序，追踪标签保留在数据库中，旧页面暂不显示。\n'
  printf 'services:\n  backend:\n    image: %s\n' "$ROLLBACK_IMAGE" > "$ACTIVE_OVERRIDE"
  start_and_check "$ACTIVE_OVERRIDE"
  MAINTENANCE=0
  printf '已回退应用镜像。数据库和新增字段均保留，未恢复旧备份覆盖数据。\n'
  exit 0
fi
[[ $# == 0 ]] || fail '不支持的参数'
command -v docker >/dev/null
command -v gzip >/dev/null
docker compose version >/dev/null
[[ $(docker inspect -f '{{.State.Running}}' "$BACKEND") == true ]] || fail '后端未运行，请先核对当前部署状态。'
[[ $(docker inspect -f '{{.State.Running}}' "$NGINX") == true ]] || fail '网站入口未运行，请先核对当前部署状态。'
APP_DIR=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' "$BACKEND")
PROJECT=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$BACKEND")
CONFIG_FILES=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.config_files"}}' "$BACKEND")
[[ -d "$APP_DIR" && -n "$PROJECT" && -n "$CONFIG_FILES" ]] || fail '无法从运行容器恢复 Compose 配置。'
SCRIPT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
cd -- "$SCRIPT_ROOT"
ENV_FILE="$APP_DIR/hospital-edc-backend/.env.production"
[[ -f "$ENV_FILE" ]] || fail '缺少原生产环境文件；不要重新生成密钥。'
COMPOSE=(docker compose --project-directory "$APP_DIR" -p "$PROJECT" --env-file "$ENV_FILE")
IFS=',' read -r -a CONFIG_LIST <<< "$CONFIG_FILES"
for config in "${CONFIG_LIST[@]}"; do
  [[ -f "$config" ]] || fail "缺少原 Compose 配置：$config"
  COMPOSE+=(-f "$config")
done
"${COMPOSE[@]}" config --quiet
RELEASE_ID="$(date +%Y%m%d-%H%M%S)-$(git rev-parse --short=12 HEAD)"
BACKUP_DIR="${EDC_BACKUP_ROOT:-$HOME/edc-backups}/entry-speed-$RELEASE_ID"
mkdir -p "$BACKUP_DIR/config" "$APP_DIR/deploy"
NEW_IMAGE="edc-backend:entry-speed-$RELEASE_ID"
ROLLBACK_IMAGE="edc-backend:pre-entry-speed-$RELEASE_ID"
ACTIVE_OVERRIDE="$APP_DIR/deploy/active-release.override.yml"
CANDIDATE="$BACKUP_DIR/new-image.override.yml"
OLD_IMAGE=$(docker inspect -f '{{.Image}}' "$BACKEND")
docker tag "$OLD_IMAGE" "$ROLLBACK_IMAGE"
cp -- "$ENV_FILE" "$BACKUP_DIR/config/env.production"
for i in "${!CONFIG_LIST[@]}"; do cp -- "${CONFIG_LIST[$i]}" "$BACKUP_DIR/config/compose-$i.yml"; done
if [[ -f "$ACTIVE_OVERRIDE" ]]; then cp -- "$ACTIVE_OVERRIDE" "$BACKUP_DIR/config/previous-active.override.yml"; fi
printf 'services:\n  backend:\n    image: %s\n' "$NEW_IMAGE" > "$CANDIDATE"
declare -p APP_DIR PROJECT COMPOSE BACKUP_DIR BACKEND NGINX MYSQL NEW_IMAGE ROLLBACK_IMAGE ACTIVE_OVERRIDE CANDIDATE > "$BACKUP_DIR/state.sh"
printf '构建新镜像：%s\n回退镜像：%s\n备份目录：%s\n' "$NEW_IMAGE" "$ROLLBACK_IMAGE" "$BACKUP_DIR"
docker build -f deploy/Dockerfile.feedback-release --build-arg "BASE_IMAGE=$ROLLBACK_IMAGE" -t "$NEW_IMAGE" .
docker run --rm --network none -e DATABASE_URL=sqlite:///:memory: -e SECRET_KEY=isolated-build-check -e FIELD_ENCRYPTION_KEY=isolated-build-check "$NEW_IMAGE" python -c 'from app.main import app; paths=app.openapi()["paths"]; assert "/api/visits/{visit_id}/withdraw-submission" in paths; assert "/api/patients/{patient_id}/images" in paths; assert "/api/visits/{visit_id}/previous-medications" in paths; assert "/api/patients/{patient_id}/tracking" in paths; assert "/api/patients/{patient_id}/images/{image_id}/thumbnail" in paths; from pathlib import Path; assert Path("hospital-edc-frontend/js/entry-keyboard.js").is_file(); print("新镜像导入及路由检查通过")'
DB_VERSION=$(docker exec "$MYSQL" sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot -N -e "SELECT VERSION()"')
[[ "$DB_VERSION" == 8.4.* ]] || fail "当前数据库版本为 $DB_VERSION；本脚本仅支持 MySQL 8.4，请先核对。"
# Confirm original persistent storage before stopping the running service.
for pair in "$BACKEND:/app/uploads" "$MYSQL:/var/lib/mysql"; do
  container=${pair%%:*}; destination=${pair#*:}
  docker inspect -f '{{range .Mounts}}{{println .Destination}}{{end}}' "$container" | grep -Fx "$destination" >/dev/null || fail "缺少持久化挂载：$pair"
done
"${COMPOSE[@]}" -f "$CANDIDATE" run --rm --no-deps -T backend python -c 'import sys; sys.path.insert(0,"scripts"); from verify_images_migration import verify_images; from app.database import engine; c=engine.connect(); verify_images(c); c.close()'
"${COMPOSE[@]}" -f "$CANDIDATE" run --rm --no-deps -T backend python -c 'from app.database import engine; from sqlalchemy import inspect; assert "tracking_status" in {c["name"] for c in inspect(engine).get_columns("patients")}, "请先完成 20261022 工作流版本升级"'
printf '开始维护，暂停网站访问并备份……\n'
MAINTENANCE=1
docker stop "$NGINX" "$BACKEND" >/dev/null
docker exec "$MYSQL" sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysqldump -uroot --single-transaction --routines --triggers --events --hex-blob --no-tablespaces --set-gtid-purged=OFF "$MYSQL_DATABASE"' | gzip > "$BACKUP_DIR/database.sql.gz"
gzip -t "$BACKUP_DIR/database.sql.gz"
[[ -s "$BACKUP_DIR/database.sql.gz" ]] || fail '数据库备份为空'
gzip -dc "$BACKUP_DIR/database.sql.gz" | tail -n 10 | grep -q "Dump completed"
docker cp "$BACKEND:/app/uploads" "$BACKUP_DIR/uploads"
tar -czf "$BACKUP_DIR/uploads.tar.gz" -C "$BACKUP_DIR" uploads
tar -tzf "$BACKUP_DIR/uploads.tar.gz" >/dev/null
sha256sum "$BACKUP_DIR/database.sql.gz" "$BACKUP_DIR/uploads.tar.gz" > "$BACKUP_DIR/checksums.txt"
RUN=("${COMPOSE[@]}" -f "$CANDIDATE" run --rm --no-deps -T -v "$BACKUP_DIR:/migration-check" backend)
"${RUN[@]}" python scripts/verify_feedback_migration.py snapshot /migration-check/before.json
"${RUN[@]}" python scripts/verify_feedback_migration.py verify /migration-check/before.json
cp -- "$CANDIDATE" "$ACTIVE_OVERRIDE"
start_and_check "$ACTIVE_OVERRIDE"
MAINTENANCE=0
printf '\n更新完成。网站入口检查通过。\n备份目录：%s\n新镜像：%s\n' "$BACKUP_DIR" "$NEW_IMAGE"
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
