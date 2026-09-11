"""
多中心系统初始化脚本

此脚本用于初始化多中心EDC系统：
1. 创建主中心和分中心（天津 7 家医院，见需求 2.1）
2. 创建总管理员账号
3. 为每个分中心生成管理员邀请码
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


# 7 家中心（需求 2.1 表；TJ-06/TJ-07 待招募）
CENTERS = [
    {"code": "TJ-01", "name": "天津医科大学第二医院",       "is_main": True,  "person": "陈雨",   "phone": "15332199139"},
    {"code": "TJ-02", "name": "南开大学附属医院（天津市第四医院）", "is_main": False, "person": "张宇宁", "phone": "13702153653"},
    {"code": "TJ-03", "name": "天津市津南医院",             "is_main": False, "person": "刘基凤", "phone": "18698167787"},
    {"code": "TJ-04", "name": "天津市津南中医医院",          "is_main": False, "person": "常彦飞", "phone": "18902037544"},
    {"code": "TJ-05", "name": "天津市蓟县人民医院",          "is_main": False, "person": "李万辉", "phone": "13682151850"},
    {"code": "TJ-06", "name": "待招募分中心六",             "is_main": False, "person": None,    "phone": None, "active": False},
    {"code": "TJ-07", "name": "待招募分中心七",             "is_main": False, "person": None,    "phone": None, "active": False},
]


def init_multi_center_system():
    db = SessionLocal()
    try:
        # 1. 创建/对齐中心
        main_center = None
        for c in CENTERS:
            center = db.query(Center).filter(Center.center_code == c["code"]).first()
            if not center:
                center = Center(
                    center_code=c["code"],
                    center_name=c["name"],
                    is_main_center=c["is_main"],
                    contact_person=c.get("person"),
                    contact_phone=c.get("phone"),
                    is_active=c.get("active", True),
                )
                db.add(center)
                db.commit()
                db.refresh(center)
                print(f"✓ 创建中心: {c['name']} ({c['code']})")
            else:
                # 对齐名称/负责人等信息（保留现有 id/激活状态）
                center.center_name = c["name"]
                center.is_main_center = c["is_main"]
                if c.get("person"):
                    center.contact_person = c["person"]
                if c.get("phone"):
                    center.contact_phone = c["phone"]
                db.commit()
                print(f"✓ 中心已存在并已对齐: {c['name']} ({c['code']})")
            if c["is_main"]:
                main_center = center

        # 2. 创建总管理员账号
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
            if admin_user.role != "main_admin" or admin_user.center_id != main_center.id:
                admin_user.role = "main_admin"
                admin_user.center_id = main_center.id
                db.commit()
                print(f"✓ 更新管理员账号为总管理员角色")
            else:
                print(f"✓ 总管理员账号已存在")

        # 3. 为每个在招分中心生成管理员邀请码
        centers = db.query(Center).filter(Center.is_main_center == False, Center.is_active == True).all()
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
