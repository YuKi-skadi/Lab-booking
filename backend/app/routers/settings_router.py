from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import PlainTextResponse
from typing import Optional, List
from pydantic import BaseModel, Field
import json
import io
from datetime import datetime
from uuid import uuid4

from ..settings_manager import get_settings_manager
from ..storage import get_storage
from ..admin_auth import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin_settings"])


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


class SemesterCreate(BaseModel):
    start_year: int = Field(..., ge=2000, le=2200)
    end_year: int = Field(..., ge=2000, le=2200)
    term: int = Field(..., ge=1, le=2)
    start_date: str
    end_date: str


def _validate_semester(data: SemesterCreate):
    if data.end_year <= data.start_year:
        raise HTTPException(status_code=400, detail="结束年份必须晚于开始年份")
    try:
        start = datetime.strptime(data.start_date, "%Y-%m-%d").date()
        end = datetime.strptime(data.end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="学期日期格式错误，应为 YYYY-MM-DD")
    if start > end:
        raise HTTPException(status_code=400, detail="学期开始日期不能晚于结束日期")
    return start, end


@router.get("/semesters")
async def list_semesters(password: str = Depends(require_admin)):
    mgr = get_settings_manager()
    return {"semesters": sorted(mgr.semesters, key=lambda item: item.get("start_date", ""), reverse=True)}


@router.post("/semesters")
async def create_semester(data: SemesterCreate, password: str = Depends(require_admin)):
    _validate_semester(data)
    mgr = get_settings_manager()
    code = f"{data.start_year}-{data.end_year}-{data.term}"
    if any(item.get("code") == code for item in mgr.semesters):
        raise HTTPException(status_code=400, detail="该学期已经存在")
    semester = {
        "id": f"semester_{uuid4().hex[:10]}",
        "code": code,
        "start_year": data.start_year,
        "end_year": data.end_year,
        "term": data.term,
        "start_date": data.start_date,
        "end_date": data.end_date,
    }
    semesters = list(mgr.semesters)
    semesters.append(semester)
    mgr.update({"semesters": semesters, "semester_version": mgr.semester_version + 1})
    return {"success": True, "semester": semester, "semesters": semesters}


@router.delete("/semesters/{semester_id}")
async def delete_semester(semester_id: str, password: str = Depends(require_admin)):
    mgr = get_settings_manager()
    semesters = list(mgr.semesters)
    remaining = [item for item in semesters if item.get("id") != semester_id]
    if len(remaining) == len(semesters):
        raise HTTPException(status_code=404, detail="学期不存在")
    mgr.update({"semesters": remaining, "semester_version": mgr.semester_version + 1})
    return {"success": True, "semesters": remaining}


@router.get("/settings")
async def get_settings(password: str = Depends(require_admin)):
    mgr = get_settings_manager()
    return {
        "admin_password": mgr.admin_password,
        "success_message": mgr.success_message,
        "time_slots": mgr.time_slots_raw,
        "subtitle": mgr.subtitle,
        "notice_lines": mgr.notice_lines,
    }


@router.put("/settings")
async def update_settings(data: SettingsUpdate, password: str = Depends(require_admin)):
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
async def get_classrooms(password: str = Depends(require_admin)):
    mgr = get_settings_manager()
    return {"classrooms": mgr.classrooms}


@router.post("/classrooms")
async def add_classroom(item: ClassroomItem, password: str = Depends(require_admin)):
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
async def rename_classroom(index: int, item: ClassroomItem, password: str = Depends(require_admin)):
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
async def delete_classroom(index: int, password: str = Depends(require_admin)):
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
async def get_majors(password: str = Depends(require_admin)):
    mgr = get_settings_manager()
    return {"majors": mgr.majors}


@router.post("/majors")
async def add_major(item: MajorItem, password: str = Depends(require_admin)):
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
async def delete_major(index: int, password: str = Depends(require_admin)):
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
    validation: Optional[dict] = None


class FormFieldCreate(BaseModel):
    key: str
    label: str
    type: str = "text"
    required: bool = False
    validation: Optional[dict] = Field(default_factory=dict)


@router.get("/form-fields")
async def get_form_fields(password: str = Depends(require_admin)):
    mgr = get_settings_manager()
    return {
        "built_in": mgr.form_fields,
        "custom": mgr.custom_fields,
    }


@router.put("/form-fields/{field_key}")
async def update_form_field(field_key: str, data: FormFieldUpdate, password: str = Depends(require_admin)):
    mgr = get_settings_manager()
    # Try built-in fields first, then custom fields
    fields = dict(mgr.form_fields)
    if field_key in fields:
        if data.required is not None:
            fields[field_key]["required"] = data.required
        if data.label is not None:
            fields[field_key]["label"] = data.label
        if data.validation is not None:
            fields[field_key]["validation"] = data.validation
        mgr.set("form_fields", fields)
        return {"success": True, "form_fields": fields}

    # Check custom fields
    customs = list(mgr.custom_fields)
    for i, cf in enumerate(customs):
        if cf.get("key") == field_key:
            if data.required is not None:
                customs[i]["required"] = data.required
            if data.label is not None:
                customs[i]["label"] = data.label
            if data.validation is not None:
                customs[i]["validation"] = data.validation
            mgr.set("custom_fields", customs)
            return {"success": True, "custom_fields": customs}

    raise HTTPException(status_code=404, detail="字段不存在")


@router.post("/form-fields/custom")
async def add_custom_field(data: FormFieldCreate, password: str = Depends(require_admin)):
    mgr = get_settings_manager()
    key = data.key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="字段 key 不能为空")
    # Check uniqueness
    if key in mgr.form_fields:
        raise HTTPException(status_code=400, detail="与内置字段重名")
    for cf in mgr.custom_fields:
        if cf.get("key") == key:
            raise HTTPException(status_code=400, detail="字段 key 已存在")

    customs = list(mgr.custom_fields)
    customs.append({
        "key": key,
        "label": data.label,
        "type": data.type,
        "required": data.required,
        "order": 90 + len(customs),
        "validation": data.validation or {},
    })
    mgr.set("custom_fields", customs)
    return {"success": True, "custom_fields": customs}


@router.delete("/form-fields/custom/{field_key}")
async def delete_custom_field(field_key: str, password: str = Depends(require_admin)):
    mgr = get_settings_manager()
    if field_key in mgr.form_fields:
        raise HTTPException(status_code=400, detail="不能删除内置字段")
    customs = [cf for cf in mgr.custom_fields if cf.get("key") != field_key]
    mgr.set("custom_fields", customs)
    return {"success": True, "custom_fields": customs}


# ==================== 数据库管理 ====================

@router.get("/db/backup")
async def backup_database(password: str = Depends(require_admin)):
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
async def import_database(password: str = Depends(require_admin), file: UploadFile = File(...)):
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
            classroom = b.get("classroom")
            if not classroom or not isinstance(classroom, str) or not classroom.strip():
                skipped += 1
                continue
            raw_status = (b.get("status") or "pending").strip().lower()
            valid_statuses = {"pending", "approved", "rejected", "cancelled"}
            status_map = {"confirmed": "approved", "active": "approved", "done": "approved"}
            status = raw_status if raw_status in valid_statuses else status_map.get(raw_status, "pending")

            booking_data = {
                "student_name": b.get("student_name") or "",
                "student_id": b.get("student_id") or "",
                "major": b.get("major") or "",
                "supervisor": b.get("supervisor") or "",
                "classroom": classroom,
                "booking_date": b.get("booking_date") or "",
                "start_time": b.get("start_time") or "",
                "end_time": b.get("end_time") or "",
                "purpose": b.get("purpose") or "",
                "phone": b.get("phone") or "",
                "status": status,
            }
            await storage.create_booking(booking_data)
            imported += 1
        except Exception:
            skipped += 1

    return {"success": True, "imported": imported, "skipped": skipped}


@router.get("/db/config")
async def get_db_config(password: str = Depends(require_admin)):
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
        "custom_fields": mgr.custom_fields,
        "all_fields": mgr.get_all_fields(),
        "success_message": mgr.success_message,
        "subtitle": mgr.subtitle,
        "notice_lines": mgr.notice_lines,
    }
