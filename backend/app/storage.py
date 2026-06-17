import json
import os
import shutil
from abc import ABC, abstractmethod
from datetime import date, datetime, time
from typing import Optional, List

from .config import settings


class StorageBackend(ABC):
    @abstractmethod
    async def create_booking(self, data: dict) -> dict:
        pass

    @abstractmethod
    async def get_booking(self, booking_id: int) -> Optional[dict]:
        pass

    @abstractmethod
    async def list_bookings(self, date_str: Optional[str] = None, classroom: Optional[str] = None,
                            student_id: Optional[str] = None, status: Optional[str] = None) -> List[dict]:
        pass

    @abstractmethod
    async def update_booking(self, booking_id: int, data: dict) -> Optional[dict]:
        pass

    @abstractmethod
    async def delete_booking(self, booking_id: int) -> bool:
        pass

    @abstractmethod
    async def check_availability(self, classroom: str, date_str: str) -> List[dict]:
        pass

    @abstractmethod
    async def get_all_bookings(self) -> List[dict]:
        pass


class SQLStorage(StorageBackend):
    def __init__(self):
        from .models import Booking
        from .database import _SessionLocal
        self.Booking = Booking
        self.SessionLocal = _SessionLocal

    def _run_sync(self, func):
        import asyncio
        return asyncio.get_event_loop().run_in_executor(None, func)

    async def create_booking(self, data: dict) -> dict:
        data = dict(data)
        if isinstance(data.get("booking_date"), str):
            data["booking_date"] = datetime.strptime(data["booking_date"], "%Y-%m-%d").date()
        booking = self.Booking(**data)
        db = self.SessionLocal()
        try:
            db.add(booking)
            db.commit()
            db.refresh(booking)
            return booking.to_dict()
        finally:
            db.close()

    async def get_booking(self, booking_id: int) -> Optional[dict]:
        db = self.SessionLocal()
        try:
            booking = db.query(self.Booking).filter(self.Booking.id == booking_id).first()
            return booking.to_dict() if booking else None
        finally:
            db.close()

    async def list_bookings(self, date_str=None, classroom=None, student_id=None, status=None):
        db = self.SessionLocal()
        try:
            q = db.query(self.Booking)
            if date_str:
                q = q.filter(self.Booking.booking_date == datetime.strptime(date_str, "%Y-%m-%d").date())
            if classroom:
                q = q.filter(self.Booking.classroom == classroom)
            if student_id:
                q = q.filter(self.Booking.student_id == student_id)
            if status:
                q = q.filter(self.Booking.status == status)
            return [b.to_dict() for b in q.order_by(self.Booking.booking_date.desc(), self.Booking.start_time).all()]
        finally:
            db.close()

    async def update_booking(self, booking_id: int, data: dict) -> Optional[dict]:
        db = self.SessionLocal()
        try:
            booking = db.query(self.Booking).filter(self.Booking.id == booking_id).first()
            if not booking:
                return None
            for k, v in data.items():
                if v is not None and hasattr(booking, k):
                    setattr(booking, k, v)
            booking.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(booking)
            return booking.to_dict()
        finally:
            db.close()

    async def delete_booking(self, booking_id: int) -> bool:
        db = self.SessionLocal()
        try:
            booking = db.query(self.Booking).filter(self.Booking.id == booking_id).first()
            if not booking:
                return False
            db.delete(booking)
            db.commit()
            return True
        finally:
            db.close()

    async def check_availability(self, classroom: str, date_str: str) -> List[dict]:
        db = self.SessionLocal()
        try:
            bookings = db.query(self.Booking).filter(
                self.Booking.classroom == classroom,
                self.Booking.booking_date == datetime.strptime(date_str, "%Y-%m-%d").date(),
                self.Booking.status.in_(["pending", "approved"])
            ).all()
            return [b.to_dict() for b in bookings]
        finally:
            db.close()

    async def get_all_bookings(self) -> List[dict]:
        db = self.SessionLocal()
        try:
            return [b.to_dict() for b in db.query(self.Booking).order_by(self.Booking.booking_date.desc(), self.Booking.start_time).all()]
        finally:
            db.close()


class JSONStorage(StorageBackend):
    def __init__(self):
        self.data_dir = settings.json_data_dir
        self.db_file = os.path.join(self.data_dir, "bookings.json")
        self.backup_dir = os.path.join(self.data_dir, "backups")
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        self._ensure_db()

    def _ensure_db(self):
        if not os.path.exists(self.db_file):
            self._write({"bookings": [], "_next_id": 1})

    def _read(self) -> dict:
        with open(self.db_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: dict):
        tmp = self.db_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.db_file)

    def _backup(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(self.backup_dir, f"bookings_{ts}.json")
        shutil.copy2(self.db_file, backup_path)

    async def create_booking(self, data: dict) -> dict:
        db = self._read()
        booking_id = db["_next_id"]
        db["_next_id"] += 1
        booking = {
            "id": booking_id,
            "student_name": data.get("student_name"),
            "student_id": data.get("student_id"),
            "major": data.get("major"),
            "supervisor": data.get("supervisor"),
            "classroom": data.get("classroom"),
            "booking_date": data.get("booking_date"),
            "start_time": data.get("start_time"),
            "end_time": data.get("end_time"),
            "purpose": data.get("purpose"),
            "phone": data.get("phone"),
            "status": data.get("status", "pending"),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        db["bookings"].append(booking)
        self._write(db)
        self._backup()
        return booking

    async def get_booking(self, booking_id: int) -> Optional[dict]:
        db = self._read()
        for b in db["bookings"]:
            if b["id"] == booking_id:
                return b
        return None

    async def list_bookings(self, date_str=None, classroom=None, student_id=None, status=None):
        db = self._read()
        result = db["bookings"]
        if date_str:
            result = [b for b in result if b.get("booking_date") == date_str]
        if classroom:
            result = [b for b in result if b.get("classroom") == classroom]
        if student_id:
            result = [b for b in result if b.get("student_id") == student_id]
        if status:
            result = [b for b in result if b.get("status") == status]
        result.sort(key=lambda x: (x.get("booking_date", ""), x.get("start_time", "")), reverse=True)
        return result

    async def update_booking(self, booking_id: int, data: dict) -> Optional[dict]:
        db = self._read()
        for b in db["bookings"]:
            if b["id"] == booking_id:
                for k, v in data.items():
                    if v is not None:
                        b[k] = v
                b["updated_at"] = datetime.now().isoformat()
                self._write(db)
                self._backup()
                return b
        return None

    async def delete_booking(self, booking_id: int) -> bool:
        db = self._read()
        for i, b in enumerate(db["bookings"]):
            if b["id"] == booking_id:
                db["bookings"].pop(i)
                self._write(db)
                self._backup()
                return True
        return False

    async def check_availability(self, classroom: str, date_str: str) -> List[dict]:
        db = self._read()
        return [b for b in db["bookings"] if b.get("classroom") == classroom and b.get("booking_date") == date_str and b.get("status") in ("pending", "approved")]

    async def get_all_bookings(self) -> List[dict]:
        db = self._read()
        return sorted(db["bookings"], key=lambda x: (x.get("booking_date", ""), x.get("start_time", "")), reverse=True)


def get_storage() -> StorageBackend:
    backend = settings.storage_backend.lower()
    if backend == "json":
        return JSONStorage()
    return SQLStorage()
