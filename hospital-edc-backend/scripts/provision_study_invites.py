"""Single-use researcher and QC invitations for every active center, including TJ01."""
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import secrets
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import SessionLocal
from app.models import *
from app.models.center import Center, InvitationCode
from app.models.user import User
from app.services.audit import log_action


def provision(db, admin_username, count=1):
    if not 1 <= count <= 100:
        raise ValueError('每中心每角色邀请码数量应为1至100')
    admin = db.query(User).filter_by(username=admin_username, role='main_admin', is_active=1).first()
    if not admin:
        raise ValueError('必须指定启用的最高权限账号')
    now = datetime.utcnow()
    result = []
    for center in db.query(Center).filter_by(is_active=True).order_by(Center.id).all():
        for role in ('researcher', 'qc'):
            invites = db.query(InvitationCode).filter(
                InvitationCode.center_id == center.id, InvitationCode.role == role,
                InvitationCode.is_active == True, InvitationCode.max_uses == 1,
                InvitationCode.used_count == 0, InvitationCode.expires_at > now,
            ).order_by(InvitationCode.id).limit(count).all()
            while len(invites) < count:
                invite = InvitationCode(code=secrets.token_urlsafe(24), center_id=center.id,
                    role=role, max_uses=1, used_count=0, is_active=True,
                    expires_at=now+timedelta(days=7), created_by=admin.id)
                db.add(invite); db.flush()
                log_action(db, admin, 'invitation_codes', invite.id, 'create', f'center_id={center.id};role={role};single use')
                invites.append(invite)
            for invite in invites:
                result.append((center.center_name, role, invite.code, invite.expires_at.isoformat()+'Z'))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admin-username', required=True)
    parser.add_argument('--count', type=int, default=1, help='每中心每角色未使用邀请码数量；重复执行复用有效邀请码')
    args = parser.parse_args()
    with SessionLocal() as db:
        rows = provision(db, args.admin_username, args.count)
        db.commit()
    print('医院\t角色\t单次邀请码\t到期UTC')
    for row in rows:
        print('\t'.join(row))
