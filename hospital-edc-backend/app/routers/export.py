import io
from datetime import date
from typing import Optional, List
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user, get_accessible_center_ids, require_admin
from app.services import export as export_service
from app.services.audit import log_action

router = APIRouter(prefix="/api/export", tags=["数据导出"])


@router.get("/")
def export_data(
    format: str = Query("xlsx", description="xlsx | csv"),
    deidentify: bool = Query(True, description="true=脱敏（姓名/身份证/电话掩码）"),
    status: Optional[List[str]] = Query(None, description="入组状态过滤：enrolled/completed/dropout/withdrawn"),
    visit_status: Optional[str] = Query(None, description="访视状态过滤：locked/signed/…（默认不过滤）"),
    center_id: Optional[int] = Query(None, description="限定中心（总中心可用）"),
    selected_centers: Optional[List[int]] = Query(None, description="选择一个或多个中心"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """一键导出分析数据表（多 sheet：患者主表/访视宽表/用药/不良事件/数据字典）。

    - 中心隔离：总中心可导全部（可指定 center_id），分中心只能导本中心。
    - 所有角色固定脱敏，不允许明文导出。
    - 每次导出写审计日志（需求 11.2）。
    """
    if format not in ("xlsx", "csv"):
        raise HTTPException(400, "format 仅支持 xlsx 或 csv")

    if not deidentify:
        raise HTTPException(403, "所有账号的数据导出均须脱敏，不支持明文导出")

    # 中心隔离
    center_ids = get_accessible_center_ids(current_user)
    requested = set(selected_centers or [])
    if center_id is not None:
        requested.add(center_id)
    if center_ids is not None:
        # 分中心：只能本中心
        if requested - set(center_ids):
            raise HTTPException(403, "无权导出该中心的数据")
    elif requested:
        # 总中心指定了中心
        center_ids = sorted(requested)

    visit_statuses = [visit_status] if visit_status else None

    tables = export_service.build_all_tables(
        db, center_ids, deidentify=deidentify,
        status_filter=status, visit_status=visit_statuses,
    )

    # 审计：记录导出范围/是否含隐私字段/操作人
    scope = "全部中心" if center_ids is None else f"中心{center_ids}"
    log_action(db, current_user, "exports", 0, "export",
               f"格式={format} 脱敏={deidentify} 范围={scope} "
               f"入组状态={status or '全部'} 访视状态={visit_status or '全部'}")
    db.commit()

    stamp = date.today().strftime("%Y%m%d")
    privacy = "脱敏" if deidentify else "含隐私"
    if format == "xlsx":
        content = export_service.to_excel(tables)
        filename = f"EDC导出_{privacy}_{stamp}.xlsx"
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        content = export_service.to_csv_zip(tables)
        filename = f"EDC导出_{privacy}_{stamp}.zip"
        media = "application/zip"

    return StreamingResponse(
        io.BytesIO(content),
        media_type=media,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        },
    )
