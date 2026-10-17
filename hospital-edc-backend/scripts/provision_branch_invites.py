"""Create/reuse five branch centers and single-use invitations; never reset data."""
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import SessionLocal
from app.models import *  # Register all relationships.
from app.models.center import Center, InvitationCode
from app.models.user import User
from app.services.audit import log_action

CENTERS = [
    ('TJ-02', '南开大学附属医院', ('南开大学附属医院（天津市第四医院）',)),
    ('TJ-03', '天津市津南医院', ()),
    ('TJ-04', '天津市津南中医院', ('天津市津南中医医院',)),
    ('TJ-05', '蓟州区人民医院', ('天津市蓟州区人民医院', '天津市蓟县人民医院')),
    ('TJ-06', '天津北大医疗海洋石油医院', ('北大医疗海洋石油医院',)),
]


def provision(db, admin_username, role='researcher'):
    if role not in ('researcher', 'center_admin'):
        raise ValueError('仅支持录入人员或分中心管理员')
    admin = db.query(User).filter_by(username=admin_username, role='main_admin', is_active=1).first()
    if not admin:
        raise ValueError('请指定现有且启用的主中心管理员用户名')
    now = datetime.utcnow()
    results = []
    for code, name, aliases in CENTERS:
        matches = db.query(Center).filter(Center.center_name.in_((name, *aliases))).all()
        by_code = db.query(Center).filter_by(center_code=code).first()
        if len(matches) > 1 or (by_code and (not matches or by_code.id != matches[0].id)):
            raise ValueError(f'{name}的名称或中心编号冲突，请人工核对；本次不提交任何修改')
        center = matches[0] if matches else None
        if center and (not center.is_active or center.is_main_center):
            raise ValueError(f'{name}不是启用的分中心，请人工核对')
        if not center:
            center = Center(center_code=code, center_name=name, is_main_center=False, is_active=True)
            db.add(center)
            db.flush()
            log_action(db, admin, 'centers', center.id, 'create', name)
        invite = db.query(InvitationCode).filter(
            InvitationCode.center_id == center.id, InvitationCode.role == role,
            InvitationCode.is_active == True, InvitationCode.used_count == 0,
            InvitationCode.max_uses == 1, InvitationCode.expires_at > now,
        ).order_by(InvitationCode.id.desc()).first()
        if not invite:
            invite = InvitationCode(code=secrets.token_urlsafe(24), center_id=center.id,
                                    role=role, max_uses=1, used_count=0, is_active=True,
                                    expires_at=now + timedelta(days=7), created_by=admin.id)
            db.add(invite)
            db.flush()
            log_action(db, admin, 'invitation_codes', invite.id, 'create', f'center_id={center.id}; role={role}; single use')
        results.append((center.center_name, invite.code, invite.expires_at.isoformat() + 'Z', role))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admin-username', required=True)
    parser.add_argument('--role', choices=['researcher', 'center_admin'], default='researcher')
    args = parser.parse_args()
    with SessionLocal() as db:
        try:
            rows = provision(db, args.admin_username, args.role)
            db.commit()
        except Exception:
            db.rollback()
            raise
    print('医院\t邀请码\t到期时间(UTC)\t角色')
    for row in rows:
        print('\t'.join(row))


if __name__ == '__main__':
    main()
