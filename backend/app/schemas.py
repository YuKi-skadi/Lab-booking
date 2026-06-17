from datetime import date, time, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class BookingCreate(BaseModel):
    student_name: str = Field(..., min_length=1, max_length=100)
    student_id: str = Field(..., min_length=1, max_length=50)
    major: str = Field(..., min_length=1, max_length=200)
    supervisor: str = Field(..., min_length=1, max_length=100)
    classroom: str = Field(..., min_length=1, max_length=100)
    booking_date: str = Field(..., description="日期，格式 YYYY-MM-DD")
    start_time: str = Field(..., description="开始时间，格式 HH:MM")
    end_time: str = Field(..., description="结束时间，格式 HH:MM")
    purpose: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=20)


class BookingUpdate(BaseModel):
    status: Optional[str] = None
    student_name: Optional[str] = None
    student_id: Optional[str] = None
    major: Optional[str] = None
    supervisor: Optional[str] = None
    classroom: Optional[str] = None
    booking_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    purpose: Optional[str] = None
    phone: Optional[str] = None


class BookingResponse(BaseModel):
    id: int
    student_name: str
    student_id: str
    major: str
    supervisor: str
    classroom: str
    booking_date: str
    start_time: str
    end_time: str
    purpose: Optional[str] = None
    phone: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AvailabilityRequest(BaseModel):
    classroom: str
    date: str


class AvailabilityResponse(BaseModel):
    classroom: str
    date: str
    available_slots: List[dict]


class AgentQueryRequest(BaseModel):
    query: str = Field(..., description="自然语言查询")
    date: Optional[str] = None
    classroom: Optional[str] = None
    time: Optional[str] = None


class AdminAuth(BaseModel):
    password: str
