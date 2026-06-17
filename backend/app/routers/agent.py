from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime

from ..config import settings
from ..settings_manager import get_settings_manager
from ..storage import get_storage, StorageBackend

router = APIRouter(prefix="/api/agent", tags=["agent"])

_storage: StorageBackend = None


def get_storage_instance():
    global _storage
    if _storage is None:
        _storage = get_storage()
    return _storage


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


@router.get("/query")
async def agent_query(
    date: Optional[str] = Query(None, description="日期 YYYY-MM-DD"),
    classroom: Optional[str] = Query(None, description="教室名称"),
    time: Optional[str] = Query(None, description="时间 HH:MM"),
):
    storage = get_storage_instance()

    if not date:
        return {
            "type": "error",
            "message": "请提供查询日期，例如 /api/agent/query?date=2025-01-01",
            "suggestion": "使用 /api/agent/rooms 查看可用教室列表",
        }

    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return {"type": "error", "message": "日期格式错误，应为 YYYY-MM-DD"}

    mgr = get_settings_manager()
    classrooms = [classroom] if classroom else mgr.classrooms

    result = {"date": date, "classrooms": []}

    for room in classrooms:
        if room not in mgr.classrooms:
            continue

        bookings = await storage.check_availability(room, date)

        if time and not classroom:
            requested_s, requested_e = None, None
            parts = time.split("-")
            if len(parts) == 2:
                requested_s, requested_e = parts[0].strip(), parts[1].strip()
            elif ":" in time:
                requested_s = time.strip()
                h, m = _parse_time(requested_s)
                requested_e = f"{h:02d}:{(m + 45):02d}"
            else:
                return {"type": "error", "message": "时间格式错误，应为 HH:MM 或 HH:MM-HH:MM"}

            is_available = True
            for b in bookings:
                if b["status"] not in ("pending", "approved"):
                    continue
                if _time_overlap(requested_s, requested_e, b["start_time"], b["end_time"]):
                    is_available = False
                    result["classrooms"].append({
                        "classroom": room,
                        "available": False,
                        "reason": f"被 {b['student_name']} 预约 ({b['start_time']}-{b['end_time']})"
                    })
                    break
            if is_available:
                result["classrooms"].append({"classroom": room, "available": True})
        else:
            room_info = {"classroom": room, "bookings": []}
            for b in bookings:
                if b["status"] in ("pending", "approved"):
                    room_info["bookings"].append({
                        "student_name": b["student_name"],
                        "student_id": b["student_id"],
                        "start_time": b["start_time"],
                        "end_time": b["end_time"],
                        "purpose": b.get("purpose"),
                        "status": b["status"],
                    })
            result["classrooms"].append(room_info)

    summary_parts = [f"## {date} 实验室预约情况\n"]
    for room_info in result["classrooms"]:
        if "available" in room_info:
            status = "空闲" if room_info["available"] else f"已占用 ({room_info.get('reason', '')})"
            summary_parts.append(f"- {room_info['classroom']}: {status}")
        elif "bookings" in room_info:
            if room_info["bookings"]:
                summary_parts.append(f"### {room_info['classroom']}")
                for bk in room_info["bookings"]:
                    summary_parts.append(f"  - {bk['start_time']}-{bk['end_time']}: {bk['student_name']}({bk['student_id']}) [{bk['status']}]")
            else:
                summary_parts.append(f"### {room_info['classroom']}: 全天空闲")

    result["summary"] = "\n".join(summary_parts)
    return result


@router.get("/bookings")
async def agent_bookings(
    date: Optional[str] = Query(None, description="日期 YYYY-MM-DD"),
    classroom: Optional[str] = Query(None, description="教室名称"),
    student_id: Optional[str] = Query(None, description="学号"),
):
    storage = get_storage_instance()
    bookings = await storage.list_bookings(date_str=date, classroom=classroom, student_id=student_id, status=None)
    return {
        "count": len(bookings),
        "bookings": bookings,
    }


@router.get("/rooms")
async def agent_rooms():
    mgr = get_settings_manager()
    slots_raw = [s["slot"] for s in mgr.time_slots]
    return {
        "classrooms": mgr.classrooms,
        "time_slots": mgr.time_slots,
        "message": f"可用教室: {', '.join(mgr.classrooms)}。可用时间段: {', '.join(slots_raw)}",
    }


@router.get("/check")
async def agent_check_slot(
    classroom: str = Query(..., description="教室名称"),
    date: str = Query(..., description="日期"),
    start_time: str = Query(..., description="开始时间 HH:MM"),
    end_time: Optional[str] = Query(None, description="结束时间 HH:MM"),
):
    storage = get_storage_instance()
    mgr = get_settings_manager()

    if classroom not in mgr.classrooms:
        return {"available": False, "reason": f"教室 '{classroom}' 不存在。可用教室: {', '.join(mgr.classrooms)}"}

    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return {"available": False, "reason": "日期格式错误"}

    try:
        datetime.strptime(start_time, "%H:%M")
    except ValueError:
        return {"available": False, "reason": "时间格式错误"}

    if not end_time:
        h, m = _parse_time(start_time)
        end_time = f"{h:02d}:{(m + 45):02d}" if m + 45 < 60 else f"{(h + 1):02d}:{((m + 45) % 60):02d}"

    bookings = await storage.check_availability(classroom, date)
    for b in bookings:
        if _time_overlap(start_time, end_time, b["start_time"], b["end_time"]):
            return {
                "available": False,
                "classroom": classroom,
                "date": date,
                "time": f"{start_time}-{end_time}",
                "reason": f"该时间段已被 {b['student_name']}({b['student_id']}) 预约 ({b['start_time']}-{b['end_time']})",
            }

    return {
        "available": True,
        "classroom": classroom,
        "date": date,
        "time": f"{start_time}-{end_time}",
        "message": f"{classroom} 在 {date} {start_time}-{end_time} 可用",
    }
