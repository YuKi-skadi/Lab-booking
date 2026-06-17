from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import PlainTextResponse
from typing import Optional, List
from pydantic import BaseModel
import json
import io

from ..settings_manager import get_settings_manager
from ..storage import get_storage

router = APIRouter(prefix="/api/admin", tags=["admin_settings"])


def check_admin(password: str):
    mgr = get_settings_manager()
    if not mgr.check_admin_password(password):
        raise HTTPException(status_code=403, detail="密码错误")


# ==================== 系统设置 ====================

class SubtitleUpdate(BaseModel):
    text: str = "请填写以下信息完成实验室预约"
    fontSize: str = "16px"
    fontWeight: str = "400"
    fontStyle: str = "normal"
    color: str = "#ffffff"


class TimeSlotItem(BaseModel):
    slot: str
    remark: str = ""


class SettingsUpdate(BaseModel):
    admin_password: Optional[str] = None
    success_message: Optional[str] = None
    time_slots: Optional[List[TimeSlotItem]] = None
    subtitle: Optional[SubtitleUpdate] = None
    notice_lines: Optional[List[str]] = None


@router.get("/settings")
async def get_settings(password: str = Query(...)):
    check_admin(password)
    mgr = get_settings_manager()
    return {
        "admin_password": mgr.admin_password,
        "success_message": mgr.success_message,
        "time_slots": mgr.time_slots_raw,
        "subtitle": mgr.subtitle,
        "notice_lines": mgr.notice_lines,
    }


@router.put("/settings")
async def update_settings(data: SettingsUpdate, password: str = Query(...)):
    check_admin(password)
    mgr = get_settings_manager()
    updates = {}
    if data.admin_password is not None:
        updates["admin_password"] = data.admin_password
    if data.success_message is not None:
        updates["success_message"] = data.success_message
    if data.time_slots is not None:
        updates["time_slots"] = [t.model_dump() for t in data.time_slots]
    if data.subtitle is not None:
        updates["subtitle"] = data.subtitle.model_dump()
    if data.notice_lines is not None:
        updates["notice_lines"] = data.notice_lines
    if updates:
        mgr.update(updates)
    return {"success": True, "message": "settings updated"}


# ==================== 教室管理 ====================

class ClassroomItem(BaseModel):
    name: str


@router.get("/classrooms")
async def get_classrooms(password: str = Query(...)):
    check_admin(password)
    mgr = get_settings_manager()
    return {"classrooms": mgr.classrooms}


@router.post("/classrooms")
async def add_classroom(item: ClassroomItem, password: str = Query(...)):
    check_admin(password)
    mgr = get_settings_manager()
    name = item.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="教室名称不能为空")
    if name in mgr.classrooms:
        raise HTTPException(status_code=400, detail="教室已存在")
    classrooms = list(mgr.classrooms)
    classrooms.append(name)
    mgr.set("classrooms", classrooms)
    return {"success": True, "classrooms": classrooms}


@router.put("/classrooms/{index}")
async def rename_classroom(index: int, item: ClassroomItem, password: str = Query(...)):
    check_admin(password)
    mgr = get_settings_manager()
    classrooms = list(mgr.classrooms)
    if index < 0 or index >= len(classrooms):
        raise HTTPException(status_code=404, detail="教室索引无效")
    new_name = item.name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="教室名称不能为空")
    if new_name in classrooms and classrooms[index] != new_name:
        raise HTTPException(status_code=400, detail="教室名称已存在")
    classrooms[index] = new_name
    mgr.set("classrooms", classrooms)
    return {"success": True, "classrooms": classrooms}


@router.delete("/classrooms/{index}")
async def delete_classroom(index: int, password: str = Query(...)):
    check_admin(password)
    mgr = get_settings_manager()
    classrooms = list(mgr.classrooms)
    if index < 0 or index >= len(classrooms):
        raise HTTPException(status_code=404, detail="教室索引无效")
    removed = classrooms.pop(index)
    mgr.set("classrooms", classrooms)
    return {"success": True, "removed": removed, "classrooms": classrooms}


# ==================== 专业预设管理 ====================

class MajorItem(BaseModel):
    name: str


@router.get("/majors")
async def get_majors(password: str = Query(...)):
    check_admin(password)
    mgr = get_settings_manager()
    return {"majors": mgr.majors}


@router.post("/majors")
async def add_major(item: MajorItem, password: str = Query(...)):
    check_admin(password)
    mgr = get_settings_manager()
    name = item.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="专业名称不能为空")
    if name in mgr.majors:
        raise HTTPException(status_code=400, detail="专业已存在")
    majors = list(mgr.majors)
    majors.append(name)
    majors.sort()
    mgr.set("majors", majors)
    return {"success": True, "majors": majors}


@router.delete("/majors/{index}")
async def delete_major(index: int, password: str = Query(...)):
    check_admin(password)
    mgr = get_settings_manager()
    majors = list(mgr.majors)
    if index < 0 or index >= len(majors):
        raise HTTPException(status_code=404, detail="专业索引无效")
    removed = majors.pop(index)
    mgr.set("majors", majors)
    return {"success": True, "removed": removed, "majors": majors}


# ==================== 表单字段配置 ====================

class FormFieldUpdate(BaseModel):
    required: Optional[bool] = None
    label: Optional[str] = None


@router.get("/form-fields")
async def get_form_fields(password: str = Query(...)):
    check_admin(password)
    mgr = get_settings_manager()
    return {"form_fields": mgr.form_fields}


@router.put("/form-fields/{field_key}")
async def update_form_field(field_key: str, data: FormFieldUpdate, password: str = Query(...)):
    check_admin(password)
    mgr = get_settings_manager()
    fields = dict(mgr.form_fields)
    if field_key not in fields:
        raise HTTPException(status_code=404, detail="字段不存在")
    if data.required is not None:
        fields[field_key]["required"] = data.required
    if data.label is not None:
        fields[field_key]["label"] = data.label
    mgr.set("form_fields", fields)
    return {"success": True, "form_fields": fields}


# ==================== 数据库管理 ====================

@router.get("/db/backup")
async def backup_database(password: str = Query(...)):
    check_admin(password)
    storage = get_storage()
    bookings = await storage.get_all_bookings()

    export = {
        "version": "1.0",
        "exported_at": __import__("datetime").datetime.now().isoformat(),
        "bookings": bookings,
    }

    json_str = json.dumps(export, ensure_ascii=False, indent=2)
    return PlainTextResponse(
        content=json_str,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=lab-bookings-backup.json"},
    )


@router.post("/db/import")
async def import_database(password: str = Query(...), file: UploadFile = File(...)):
    check_admin(password)
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"JSON 解析失败: {str(e)}")

    bookings = data.get("bookings", data if isinstance(data, list) else [])
    if not isinstance(bookings, list):
        raise HTTPException(status_code=400, detail="无效的数据格式，需要包含 bookings 数组")

    storage = get_storage()
    imported = 0
    skipped = 0
    for b in bookings:
        try:
            if not b.get("student_name") or not b.get("classroom"):
                skipped += 1
                continue
            booking_data = {
                "student_name": b.get("student_name"),
                "student_id": b.get("student_id", ""),
                "major": b.get("major", ""),
                "supervisor": b.get("supervisor", ""),
                "classroom": b.get("classroom"),
                "booking_date": b.get("booking_date"),
                "start_time": b.get("start_time"),
                "end_time": b.get("end_time"),
                "purpose": b.get("purpose"),
                "phone": b.get("phone"),
                "status": b.get("status", "pending"),
            }
            await storage.create_booking(booking_data)
            imported += 1
        except Exception:
            skipped += 1

    return {"success": True, "imported": imported, "skipped": skipped}


@router.get("/db/config")
async def get_db_config(password: str = Query(...)):
    check_admin(password)
    from ..config import settings

    backend = settings.storage_backend.lower()
    return {
        "storage_backend": backend,
        "sqlite_url": settings.sqlite_url if backend == "sqlite" else None,
        "mysql_host": settings.mysql_host if backend == "mysql" else None,
        "mysql_port": settings.mysql_port if backend == "mysql" else None,
        "mysql_database": settings.mysql_database if backend == "mysql" else None,
        "postgres_host": settings.postgres_host if backend == "postgres" else None,
        "postgres_port": settings.postgres_port if backend == "postgres" else None,
        "postgres_database": settings.postgres_database if backend == "postgres" else None,
        "json_data_dir": settings.json_data_dir if backend == "json" else None,
    }


# ==================== 公开接口（无需密码） ====================

@router.get("/public/form-config")
async def get_public_form_config():
    mgr = get_settings_manager()
    return {
        "classrooms": mgr.classrooms,
        "time_slots": mgr.time_slots,
        "majors": mgr.majors,
        "form_fields": mgr.form_fields,
        "success_message": mgr.success_message,
        "subtitle": mgr.subtitle,
        "notice_lines": mgr.notice_lines,
    }
