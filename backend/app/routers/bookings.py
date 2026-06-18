from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, List
from datetime import datetime, date

from ..schemas import BookingCreate, BookingUpdate, BookingResponse, AvailabilityResponse, AdminAuth
from ..config import settings
from ..settings_manager import get_settings_manager
from ..storage import get_storage, StorageBackend
from pydantic import BaseModel
from typing import List as ListType

router = APIRouter(prefix="/api", tags=["bookings"])

_storage: StorageBackend = None


def get_storage_instance():
    global _storage
    if _storage is None:
        _storage = get_storage()
    return _storage


def get_classrooms():
    return get_settings_manager().classrooms


def get_time_slots():
    return get_settings_manager().parsed_time_slots


def _parse_time(t: str) -> tuple:
    parts = t.split(":")
    return int(parts[0]), int(parts[1])


def _time_overlap(s1: str, e1: str, s2: str, e2: str) -> bool:
    sh1, sm1 = _parse_time(s1)
    eh1, em1 = _parse_time(e1)
    sh2, sm2 = _parse_time(s2)
    eh2, em2 = _parse_time(e2)
    start1 = sh1 * 60 + sm1
    end1 = eh1 * 60 + em1
    start2 = sh2 * 60 + sm2
    end2 = eh2 * 60 + em2
    return start1 < end2 and start2 < end1


async def _check_conflict(storage, classroom: str, booking_date: str, start_time: str, end_time: str, exclude_id: int = None):
    bookings = await storage.check_availability(classroom, booking_date)
    for b in bookings:
        if exclude_id and b["id"] == exclude_id:
            continue
        if _time_overlap(start_time, end_time, b["start_time"], b["end_time"]):
            return b
    return None


@router.post("/bookings", response_model=BookingResponse)
async def create_booking(booking: BookingCreate):
    storage = get_storage_instance()

    valid_rooms = get_classrooms()
    if booking.classroom not in valid_rooms:
        raise HTTPException(status_code=400, detail=f"无效的教室，可用教室: {', '.join(valid_rooms)}")

    try:
        datetime.strptime(booking.booking_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYY-MM-DD")

    try:
        datetime.strptime(booking.start_time, "%H:%M")
        datetime.strptime(booking.end_time, "%H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="时间格式错误，应为 HH:MM")

    if _parse_time(booking.start_time) >= _parse_time(booking.end_time):
        raise HTTPException(status_code=400, detail="开始时间必须早于结束时间")

    conflict = await _check_conflict(storage, booking.classroom, booking.booking_date, booking.start_time, booking.end_time)
    if conflict:
        raise HTTPException(
            status_code=409,
            detail=f"该时间段已被预约！{conflict['student_name']}({conflict['student_id']}) 已预约了 {conflict['classroom']} 的 {conflict['start_time']}-{conflict['end_time']}"
        )

    data = booking.model_dump()
    data["status"] = "pending"
    result = await storage.create_booking(data)
    return result


class BatchBookingSlot(BaseModel):
    start_time: str
    end_time: str


class BatchBookingCreate(BaseModel):
    student_name: str
    student_id: str
    major: str
    supervisor: str
    classroom: str
    booking_date: str
    slots: ListType[BatchBookingSlot]
    purpose: Optional[str] = None
    phone: Optional[str] = None
    custom_data: Optional[dict] = None


@router.post("/bookings/batch")
async def create_batch_booking(booking: BatchBookingCreate):
    storage = get_storage_instance()

    valid_rooms = get_classrooms()
    if booking.classroom not in valid_rooms:
        raise HTTPException(status_code=400, detail=f"无效的教室，可用教室: {', '.join(valid_rooms)}")

    try:
        datetime.strptime(booking.booking_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYY-MM-DD")

    for slot in booking.slots:
        try:
            datetime.strptime(slot.start_time, "%H:%M")
            datetime.strptime(slot.end_time, "%H:%M")
        except ValueError:
            raise HTTPException(status_code=400, detail="时间格式错误，应为 HH:MM")
        if _parse_time(slot.start_time) >= _parse_time(slot.end_time):
            raise HTTPException(status_code=400, detail="开始时间必须早于结束时间")

    results = []
    errors = []

    for slot in booking.slots:
        conflict = await _check_conflict(storage, booking.classroom, booking.booking_date, slot.start_time, slot.end_time)
        if conflict:
            errors.append({
                "slot": f"{slot.start_time}-{slot.end_time}",
                "message": f"该时间段已被 {conflict['student_name']}({conflict['student_id']}) 预约"
            })
            continue

        data = {
            "student_name": booking.student_name,
            "student_id": booking.student_id,
            "major": booking.major,
            "supervisor": booking.supervisor,
            "classroom": booking.classroom,
            "booking_date": booking.booking_date,
            "start_time": slot.start_time,
            "end_time": slot.end_time,
            "purpose": booking.purpose,
            "phone": booking.phone,
            "custom_data": booking.custom_data or {},
            "status": "pending",
        }
        result = await storage.create_booking(data)
        results.append(result)

    if errors and not results:
        raise HTTPException(status_code=409, detail="; ".join(e["message"] for e in errors))

    return {
        "success": len(results),
        "failed": len(errors),
        "errors": errors,
        "bookings": results,
    }


@router.get("/bookings", response_model=List[BookingResponse])
async def list_bookings(
    date: Optional[str] = Query(None, description="日期 YYYY-MM-DD"),
    classroom: Optional[str] = Query(None, description="教室名称"),
    student_id: Optional[str] = Query(None, description="学号"),
    status: Optional[str] = Query(None, description="状态: pending/approved/rejected/cancelled"),
):
    storage = get_storage_instance()
    return await storage.list_bookings(date_str=date, classroom=classroom, student_id=student_id, status=status)


@router.get("/bookings/all", response_model=List[BookingResponse])
async def get_all_bookings(password: str = Query(...)):
    if not get_settings_manager().check_admin_password(password):
        raise HTTPException(status_code=403, detail="密码错误")
    storage = get_storage_instance()
    return await storage.get_all_bookings()


@router.get("/bookings/{booking_id}", response_model=BookingResponse)
async def get_booking(booking_id: int):
    storage = get_storage_instance()
    result = await storage.get_booking(booking_id)
    if not result:
        raise HTTPException(status_code=404, detail="预约记录不存在")
    return result


@router.put("/bookings/{booking_id}", response_model=BookingResponse)
async def update_booking(booking_id: int, booking: BookingUpdate, password: str = Query(...)):
    if not get_settings_manager().check_admin_password(password):
        raise HTTPException(status_code=403, detail="密码错误")
    storage = get_storage_instance()
    existing = await storage.get_booking(booking_id)
    if not existing:
        raise HTTPException(status_code=404, detail="预约记录不存在")

    update_data = {k: v for k, v in booking.model_dump().items() if v is not None}
    result = await storage.update_booking(booking_id, update_data)
    return result


class BatchStatusUpdate(BaseModel):
    ids: ListType[int]
    status: str


@router.put("/bookings/batch-status")
async def batch_update_status(data: BatchStatusUpdate, password: str = Query(...)):
    if not get_settings_manager().check_admin_password(password):
        raise HTTPException(status_code=403, detail="密码错误")
    if data.status not in ("approved", "rejected", "pending", "cancelled"):
        raise HTTPException(status_code=400, detail="无效的状态值")
    if not data.ids:
        raise HTTPException(status_code=400, detail="请选择至少一条记录")

    storage = get_storage_instance()
    updated = 0
    for bid in data.ids:
        result = await storage.update_booking(bid, {"status": data.status})
        if result:
            updated += 1
    return {"success": True, "updated": updated, "total": len(data.ids)}


@router.delete("/bookings/{booking_id}")
async def delete_booking(booking_id: int, password: str = Query(...)):
    if not get_settings_manager().check_admin_password(password):
        raise HTTPException(status_code=403, detail="密码错误")
    storage = get_storage_instance()
    success = await storage.delete_booking(booking_id)
    if not success:
        raise HTTPException(status_code=404, detail="预约记录不存在")
    return {"message": "删除成功"}


@router.get("/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: int, student_id: str = Query(...)):
    storage = get_storage_instance()
    existing = await storage.get_booking(booking_id)
    if not existing:
        raise HTTPException(status_code=404, detail="预约记录不存在")
    if existing["student_id"] != student_id:
        raise HTTPException(status_code=403, detail="只能取消自己的预约")
    await storage.update_booking(booking_id, {"status": "cancelled"})
    return {"message": "取消成功"}


@router.get("/availability")
async def check_availability(classroom: str = Query(...), date: str = Query(...)):
    if classroom not in get_classrooms():
        raise HTTPException(status_code=400, detail=f"无效的教室")

    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYY-MM-DD")

    storage = get_storage_instance()
    booked = await storage.check_availability(classroom, date)

    slots = []
    for ts in get_time_slots():
        is_available = True
        booked_by = None
        for b in booked:
            if _time_overlap(ts["start"], ts["end"], b["start_time"], b["end_time"]):
                is_available = False
                booked_by = f"{b['student_name']}({b['student_id']})"
                break
        slots.append({
            "start": ts["start"],
            "end": ts["end"],
            "available": is_available,
            "booked_by": booked_by,
        })

    return {
        "classroom": classroom,
        "date": date,
        "slots": slots,
    }


@router.get("/classrooms")
async def list_classrooms():
    return {"classrooms": get_classrooms(), "time_slots": get_time_slots()}


@router.get("/schedule")
async def public_schedule(
    date: str = Query(..., description="日期 YYYY-MM-DD"),
    start_time: Optional[str] = Query(None, description="只返回此时间之后的时段 HH:MM"),
    end_time: Optional[str] = Query(None, description="只返回此时间之前的时段 HH:MM"),
):
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYY-MM-DD")

    storage = get_storage_instance()
    classrooms = get_classrooms()
    all_time_slots = get_time_slots()

    # 过滤时间段
    filtered_slots = all_time_slots
    if start_time or end_time:
        filtered_slots = []
        for ts in all_time_slots:
            if start_time and ts["start"] < start_time:
                continue
            if end_time and ts["end"] > end_time:
                continue
            filtered_slots.append(ts)

    result = {
        "date": date,
        "time_range": f"{start_time or '开始'}-{end_time or '结束'}",
        "classrooms": [],
    }

    for room in classrooms:
        booked = await storage.check_availability(room, date)
        slots_status = []
        for ts in filtered_slots:
            occupied = False
            for b in booked:
                if b["status"] not in ("pending", "approved"):
                    continue
                if _time_overlap(ts["start"], ts["end"], b["start_time"], b["end_time"]):
                    occupied = True
                    break
            slots_status.append({
                "start": ts["start"],
                "end": ts["end"],
                "remark": ts.get("remark", ""),
                "slot": ts.get("slot", f"{ts['start']}-{ts['end']}"),
                "available": not occupied,
            })

        result["classrooms"].append({
            "name": room,
            "occupied_count": sum(1 for s in slots_status if not s["available"]),
            "slots": slots_status,
        })

    return result


@router.post("/admin/auth")
async def admin_auth(auth: AdminAuth):
    if get_settings_manager().check_admin_password(auth.password):
        return {"success": True, "message": "验证成功"}
    raise HTTPException(status_code=403, detail="密码错误")
