#!/usr/bin/env bash
# Scope confirmed for this hospital: 9 test patients, 16 visits, 1 image, 8 consents.
# Preserve audit/user identities; disable all existing centers, accounts and invitations.
set -Eeuo pipefail
umask 077
BACKUP_DIR=''
MAINTENANCE=0
on_error() {
  local code=$?
  trap - ERR
  if [[ $MAINTENANCE == 1 ]]; then
    docker stop edc-prod-nginx >/dev/null 2>&1 || true
    printf '\n流程未完成，入口保持停止。请提供报错，不要重新运行或覆盖数据库。备份：%s\n' "$BACKUP_DIR" >&2
  fi
  exit "$code"
}
trap on_error ERR
[[ $# == 0 ]] || { echo '此脚本不接受额外参数'; exit 1; }
[[ -t 0 ]] || { echo '请在交互式 SSH 终端执行，以便隐藏输入密码'; exit 1; }
APP_DIR=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' edc-prod-backend)
PROJECT=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' edc-prod-backend)
CONFIG_FILES=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.config_files"}}' edc-prod-backend)
SCRIPT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
[[ "$SCRIPT_ROOT" == "$(cd -- "$APP_DIR" && pwd -P)" ]]
cd "$APP_DIR"
COMPOSE=(docker compose --project-directory "$APP_DIR" -p "$PROJECT" --env-file "$APP_DIR/hospital-edc-backend/.env.production")
IFS=',' read -r -a CONFIG_LIST <<< "$CONFIG_FILES"
for file in "${CONFIG_LIST[@]}"; do COMPOSE+=(-f "$file"); done
"${COMPOSE[@]}" config --quiet
[[ $(docker inspect -f '{{.State.Running}}' edc-prod-backend) == true ]]
[[ $(docker inspect -f '{{.State.Running}}' edc-prod-nginx) == true ]]
docker exec edc-prod-backend python -c 'from app.database import engine; from sqlalchemy import text; c=engine.connect(); expected={"patients":9,"visits":16,"patient_images":1,"consent_records":8}; actual={k:c.execute(text("SELECT COUNT(*) FROM "+k)).scalar() for k in expected}; assert actual==expected, "数据数量已变化，请先重新核对，未清理："+str(actual); assert c.execute(text("SELECT COUNT(*) FROM users WHERE username=:u"), {"u":"hospital_admin"}).scalar()==0, "hospital_admin 已存在，停止以免覆盖账号"; print("已确认测试数据数量：",actual)'
RELEASE_ID=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="$HOME/edc-backups/trial-reset-$RELEASE_ID"
mkdir -p "$BACKUP_DIR/config"
cp hospital-edc-backend/.env.production "$BACKUP_DIR/config/env.production"
for i in "${!CONFIG_LIST[@]}"; do cp "${CONFIG_LIST[$i]}" "$BACKUP_DIR/config/compose-$i.yml"; done
IMAGE="edc-backend:pre-trial-reset-$RELEASE_ID"
docker tag "$(docker inspect -f '{{.Image}}' edc-prod-backend)" "$IMAGE"
printf 'services:\n  backend:\n    image: %s\n' "$IMAGE" > "$BACKUP_DIR/same-image.override.yml"
RUN=("${COMPOSE[@]}" -f "$BACKUP_DIR/same-image.override.yml" run --rm --no-deps
     -v "$APP_DIR/hospital-edc-backend/scripts:/ops:ro" -v "$BACKUP_DIR:/trial-reset" backend)
echo '开始维护：暂停录入，备份数据库和全部上传文件。'
MAINTENANCE=1
docker stop edc-prod-nginx edc-prod-backend >/dev/null
docker exec edc-prod-mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysqldump -uroot --single-transaction --routines --triggers --events --hex-blob --no-tablespaces --set-gtid-purged=OFF "$MYSQL_DATABASE"' | gzip > "$BACKUP_DIR/database.sql.gz"
gzip -t "$BACKUP_DIR/database.sql.gz"
docker cp edc-prod-backend:/app/uploads "$BACKUP_DIR/uploads"
"${RUN[@]}" python /ops/reset_trial_data.py --plan /trial-reset/before.json
# Recheck the user-reviewed scope after writes have been stopped (not just before stopping).
"${RUN[@]}" python -c 'import json; p=json.load(open("/trial-reset/before.json")); expected={"patients":9,"visits":16,"patient_images":1,"consent_records":8}; assert all(p[k]["count"]==v for k,v in expected.items()), "备份时数据数量变化，停止清理"; from app.config import settings; from pathlib import Path; assert Path(settings.UPLOAD_DIR).resolve()==Path("/app/uploads"), "上传目录不是预期卷，停止清理"'
printf '\n备份完成：%s\n即将创建 hospital_admin（中心1），停用所有旧中心、旧账号和邀请码。\n请设置至少16位密码；输入时不会显示字符。\n' "$BACKUP_DIR"
"${RUN[@]}" python /ops/reset_trial_data.py --plan /trial-reset/before.json --apply --username hospital_admin --center-id 1 --disable-centers
# Retire test files outside the live upload volume, without permanently deleting the backup.
"${RUN[@]}" python -c 'from pathlib import Path; import shutil; from app.config import settings; root=Path(settings.UPLOAD_DIR).resolve(); assert root==Path("/app/uploads"); target=Path("/trial-reset/retired-uploads"); target.mkdir(); [shutil.move(str(p),str(target/p.name)) for p in root.iterdir()]; print("原测试上传文件已移出在线目录并归档到备份目录")'
docker start edc-prod-backend >/dev/null
for attempt in $(seq 1 60); do
  if [[ $(docker inspect -f '{{.State.Health.Status}}' edc-prod-backend) == healthy ]]; then break; fi
  sleep 2
done
[[ $(docker inspect -f '{{.State.Health.Status}}' edc-prod-backend) == healthy ]]
docker exec edc-prod-backend python -c 'from app.database import engine; from sqlalchemy import text; c=engine.connect(); assert c.execute(text("SELECT COUNT(*) FROM patients")).scalar()==0; assert c.execute(text("SELECT COUNT(*) FROM patient_images")).scalar()==0; users=c.execute(text("SELECT username,role,center_id FROM users WHERE is_active=1")).all(); assert users==[("hospital_admin","main_admin",1)],str(users); assert c.execute(text("SELECT COUNT(*) FROM centers WHERE is_active=1")).scalar()==0; assert c.execute(text("SELECT COUNT(*) FROM invitation_codes WHERE is_active=1")).scalar()==0; print("清理及账号权限校验通过")'
docker start edc-prod-nginx >/dev/null
docker exec edc-prod-nginx nginx -t
docker exec edc-prod-nginx nginx -s reload
docker exec edc-prod-nginx wget -q -O /dev/null http://127.0.0.1/
MAINTENANCE=0
printf '\n测试数据清理完成；唯一启用账号：hospital_admin。\n旧中心全部停用；确认中心并启用后才能建档。\n备份与原图归档：%s\n' "$BACKUP_DIR"
