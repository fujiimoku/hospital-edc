"""One-time trial cleanup. Run only after stopping writers and backing up DB/uploads.

Default: read-only plan. --apply requires the exact saved fingerprints and two password
prompts. Centers, old user identities and audit history remain; IDs are never reset.
"""
import argparse
import getpass
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path.cwd()))  # Production helper may be mounted at /ops, cwd=/app.
from sqlalchemy import MetaData, select, func, update, insert
from app.database import engine
from app.dependencies import hash_password
from verify_crf_migration import snapshot, compare

CLINICAL_TABLES = {
    'patients', 'visits', 'physical_exams', 'lab_results', 'comorbidities',
    'cost_indicators', 'followup_safety', 'questionnaires', 'medications',
    'lifestyle_assessments', 'meal_records', 'consent_records', 'adverse_events',
    'queries', 'patient_images', 'notifications',
}
PRESERVED_TABLES = {'centers', 'users', 'invitation_codes', 'audit_logs', 'alembic_version'}
HOSPITAL_CENTERS = [
    (1, 'TJ-01', '天津医科大学第二医院'),
    (2, 'TJ-02', '南开大学附属医院'),
    (3, 'TJ-03', '天津市津南医院'),
    (4, 'TJ-04', '天津市津南中医院'),
    (5, 'TJ-05', '蓟州区人民医院'),
    (6, 'TJ-06', '天津北大医疗海洋石油医院'),
    (7, 'TJ-07', '天津市宝坻人民医院'),
    (8, 'TJ-08', '天津市泰达医院'),
]
OLD_CENTER_NAMES = [
    '天津医科大学第二医院', '南开大学附属医院（天津市第四医院）',
    '天津市津南医院', '天津市津南中医医院', '天津市蓟县人民医院',
    '待招募分中心六', '待招募分中心七',
]


def validate_old_centers(connection, centers):
    actual = connection.execute(select(centers.c.id, centers.c.center_code, centers.c.center_name)
                                .order_by(centers.c.id)).all()
    expected = [(i, f'TJ-{i:02d}', name) for i, name in enumerate(OLD_CENTER_NAMES, 1)]
    if actual != expected:
        raise ValueError('中心列表与用户已核对的7个旧中心不一致，停止以免覆盖其他中心')


def verify_formal_centers(connection):
    centers = schema(connection).tables['centers']
    actual = connection.execute(select(centers.c.id, centers.c.center_code, centers.c.center_name,
                                       centers.c.is_main_center, centers.c.is_active)
                                .order_by(centers.c.id)).all()
    expected = [(i, code, name, i == 1, True) for i, code, name in HOSPITAL_CENTERS]
    if actual != expected:
        raise RuntimeError('正式中心配置校验失败')


def schema(connection):
    metadata = MetaData()
    metadata.reflect(bind=connection)
    actual = set(metadata.tables)
    if actual - CLINICAL_TABLES - PRESERVED_TABLES:
        raise RuntimeError('发现未评估的数据表，停止清理：' + str(sorted(actual - CLINICAL_TABLES - PRESERVED_TABLES)))
    if (CLINICAL_TABLES | (PRESERVED_TABLES - {'alembic_version'})) - actual:
        raise RuntimeError('数据库结构与当前发布版本不一致，停止清理')
    return metadata


def reset_database(connection, expected, username, password, center_id, keep_users, disable_centers=False,
                   formal_centers=False):
    """Caller owns the transaction. No files are deleted by this function."""
    tables = schema(connection)
    compare(connection, expected)
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{2,49}', username):
        raise ValueError('用户名须以英文字母开头，3至50位，仅含字母、数字、下划线、点或横线')
    if not 16 <= len(password.encode('utf-8')) <= 72:
        raise ValueError('密码须为16至72字节；建议使用至少16位随机英文、数字及符号')
    users, centers = tables.tables['users'], tables.tables['centers']
    if formal_centers:
        if disable_centers or center_id != 1:
            raise ValueError('正式中心模式须归属中心1，不能同时停用全部中心')
        validate_old_centers(connection, centers)
    if connection.execute(select(users.c.id).where(users.c.username == username)).first():
        raise ValueError('新用户名已存在；不会覆盖现有账号')
    if not connection.execute(select(centers.c.id).where(centers.c.id == center_id)).first():
        raise ValueError('归属中心不存在')
    existing = {r.username for r in connection.execute(select(users.c.username))}
    if set(keep_users) - existing:
        raise ValueError('指定保留的账号不存在')
    counts = {name: connection.execute(select(func.count()).select_from(tables.tables[name])).scalar_one()
              for name in sorted(CLINICAL_TABLES)}
    if not counts['patients']:
        raise ValueError('患者数已为0，拒绝重复清理；请单独核对账号')
    for table in reversed(tables.sorted_tables):
        if table.name in CLINICAL_TABLES:
            connection.execute(table.delete())
    disable = update(users).values(is_active=0)
    if keep_users:
        disable = disable.where(users.c.username.not_in(keep_users))
    connection.execute(disable)
    connection.execute(update(tables.tables['invitation_codes']).values(is_active=False))
    if disable_centers:
        connection.execute(update(centers).values(is_active=False))
    if formal_centers:
        for cid, code, name in HOSPITAL_CENTERS:
            values = dict(center_code=code, center_name=name, is_main_center=cid == 1, is_active=True)
            if cid <= 7:
                connection.execute(update(centers).where(centers.c.id == cid).values(**values))
            else:
                connection.execute(insert(centers).values(id=cid, **values))
        verify_formal_centers(connection)
    result = connection.execute(insert(users).values(username=username, hashed_password=hash_password(password),
                                full_name='核心客户管理员', role='main_admin', center_id=center_id, is_active=1))
    new_id = result.inserted_primary_key[0]
    connection.execute(insert(tables.tables['audit_logs']).values(
        table_name='trial_cleanup', record_id=0, field_name='counts', old_value=json.dumps(counts),
        new_value=json.dumps({'new_admin_id': new_id, 'kept_users': list(keep_users), 'disabled_centers': disable_centers,
                              'formal_centers': HOSPITAL_CENTERS if formal_centers else None}, ensure_ascii=False),
        action='trial_reset', user_id=new_id, center_id=center_id))
    for name in CLINICAL_TABLES:
        if connection.execute(select(func.count()).select_from(tables.tables[name])).scalar_one():
            raise RuntimeError('清理后校验失败，事务将回滚')
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--username')
    parser.add_argument('--center-id', type=int)
    parser.add_argument('--keep-user', action='append', default=[])
    parser.add_argument('--disable-centers', action='store_true')
    parser.add_argument('--formal-centers', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        with engine.connect() as connection:
            tables = schema(connection)
            if args.formal_centers:
                validate_old_centers(connection, tables.tables['centers'])
            plan = snapshot(connection)
        # Do not silently overwrite a previously reviewed plan.
        with args.plan.open('x', encoding='utf-8') as file:
            json.dump(plan, file, indent=2)
        print(json.dumps({name: plan[name]['count'] for name in sorted(CLINICAL_TABLES)}, indent=2))
        print('只读计划已保存，不含患者明文。未执行清理。')
        return
    if not args.username or not args.center_id:
        parser.error('--apply 必须提供 --username 和 --center-id')
    expected = json.loads(args.plan.read_text(encoding='utf-8'))
    password = getpass.getpass('设置新客户管理员密码（隐藏输入）：')
    if password != getpass.getpass('再次输入密码：'):
        raise ValueError('两次密码不同，未修改数据库')
    with engine.begin() as connection:
        counts = reset_database(connection, expected, args.username, password, args.center_id, args.keep_user,
                                args.disable_centers, args.formal_centers)
    if args.formal_centers:
        print('已配置并启用1个主中心及7个分中心：')
        for cid, code, name in HOSPITAL_CENTERS:
            print(code, name, '（主中心）' if cid == 1 else '（分中心）')
    print('数据库清理完成；中心、旧账号身份及历史审计保留，邀请码停用。')
    print('新管理员：' + args.username + '；请通过受保护的连接验证登录。')
    print('注意：本工具不删除磁盘原图；由备份/归档步骤处理 uploads，避免误删。')
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == '__main__':
    main()
