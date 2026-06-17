from datetime import datetime
from sqlalchemy import Column, Integer, String, Date, Time, DateTime, create_engine
from sqlalchemy.orm import declarative_base, Mapped, mapped_column

Base = declarative_base()


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_name: Mapped[str] = mapped_column(String(100), nullable=False)
    student_id: Mapped[str] = mapped_column(String(50), nullable=False)
    major: Mapped[str] = mapped_column(String(200), nullable=False)
    supervisor: Mapped[str] = mapped_column(String(100), nullable=False)
    classroom: Mapped[str] = mapped_column(String(100), nullable=False)
    booking_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    start_time: Mapped[str] = mapped_column(String(10), nullable=False)
    end_time: Mapped[str] = mapped_column(String(10), nullable=False)
    purpose: Mapped[str] = mapped_column(String(500), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "student_name": self.student_name,
            "student_id": self.student_id,
            "major": self.major,
            "supervisor": self.supervisor,
            "classroom": self.classroom,
            "booking_date": self.booking_date.isoformat() if self.booking_date else None,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "purpose": self.purpose,
            "phone": self.phone,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
