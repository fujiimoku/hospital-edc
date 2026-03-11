"""
多中心系统初始化脚本

此脚本用于初始化多中心EDC系统：
1. 创建主中心和示例分中心
2. 创建总管理员账号
3. 生成示例邀请码
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import SessionLocal
from app.models.center import Center, InvitationCode
from app.models.user import User
from app.dependencies import hash_password
from datetime import datetime, timedelta
import secrets


def init_multi_center_system():
    db = SessionLocal()
    try:
        # 1. 创建主中心
        main_center = db.query(Center).filter(Center.is_main_center == True).first()
        if not main_center:
            main_center = Center(
                center_code="CHN-001",
                center_name="总中心",
                is_main_center=True,
                contact_person="系统管理员",
                is_active=True
            )
            db.add(main_center)
            db.commit()
            db.refresh(main_center)
            print(f"✓ 创建主中心: {main_center.center_name} ({main_center.center_code})")
        else:
            print(f"✓ 主中心已存在: {main_center.center_name}")

        # 2. 创建示例分中心
        sub_centers_data = [
            {"code": "CHN-017", "name": "北京分中心"},
            {"code": "CHN-018", "name": "上海分中心"},
            {"code": "CHN-019", "name": "广州分中心"},
        ]

        for center_data in sub_centers_data:
            existing = db.query(Center).filter(Center.center_code == center_data["code"]).first()
            if not existing:
                center = Center(
                    center_code=center_data["code"],
                    center_name=center_data["name"],
                    is_main_center=False,
                    is_active=True
                )
                db.add(center)
                db.commit()
                print(f"✓ 创建分中心: {center_data['name']} ({center_data['code']})")
            else:
                print(f"✓ 分中心已存在: {center_data['name']}")

        # 3. 创建总管理员账号
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin_user = User(
                username="admin",
                hashed_password=hash_password("Admin@123"),
                full_name="系统管理员",
                role="main_admin",
                center_id=main_center.id,
                is_active=1
            )
            db.add(admin_user)
            db.commit()
            print(f"✓ 创建总管理员账号: admin / Admin@123")
        else:
            # 更新现有admin账号为main_admin角色
            if admin_user.role != "main_admin":
                admin_user.role = "main_admin"
                admin_user.center_id = main_center.id
                db.commit()
                print(f"✓ 更新管理员账号为总管理员角色")
            else:
                print(f"✓ 总管理员账号已存在")

        # 4. 为每个分中心生成一个邀请码（用于创建分中心管理员）
        centers = db.query(Center).filter(Center.is_main_center == False).all()
        for center in centers:
            existing_code = db.query(InvitationCode).filter(
                InvitationCode.center_id == center.id,
                InvitationCode.role == "center_admin",
                InvitationCode.is_active == True
            ).first()

            if not existing_code:
                code = secrets.token_urlsafe(12)
                invitation = InvitationCode(
                    code=code,
                    center_id=center.id,
                    role="center_admin",
                    max_uses=1,
                    expires_at=datetime.utcnow() + timedelta(days=30),
                    created_by=admin_user.id,
                    is_active=True
                )
                db.add(invitation)
                db.commit()
                print(f"✓ 为 {center.center_name} 生成管理员邀请码: {code}")
            else:
                print(f"✓ {center.center_name} 已有邀请码: {existing_code.code}")

        print("\n" + "="*60)
        print("多中心系统初始化完成！")
        print("="*60)
        print("\n登录信息：")
        print("  总管理员账号: admin")
        print("  密码: Admin@123")
        print("\n使用邀请码注册分中心管理员：")
        print("  POST /api/auth/register-with-code")
        print("  参数: username, password, full_name, invitation_code")
        print("\n查看所有邀请码：")
        print("  GET /api/invitation-codes/")
        print("="*60)

    except Exception as e:
        print(f"✗ 初始化失败: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_multi_center_system()
