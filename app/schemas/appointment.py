from pydantic import AfterValidator, BaseModel, ConfigDict, model_validator
from typing import Annotated, Optional
from datetime import datetime
from enum import Enum

from app.core.timeutils import to_utc_naive

# Incoming times are stored and compared as naive UTC
UTCDateTime = Annotated[datetime, AfterValidator(to_utc_naive)]

class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"

# Shared properties
class AppointmentBase(BaseModel):
    patient_id: int
    doctor_id: int
    start_time: datetime
    end_time: datetime
    status: AppointmentStatus = AppointmentStatus.SCHEDULED
    notes: Optional[str] = None

# Properties to receive on appointment creation
class AppointmentCreate(AppointmentBase):
    start_time: UTCDateTime
    end_time: UTCDateTime

    @model_validator(mode="after")
    def check_time_range(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self

# Properties to receive on appointment update
class AppointmentUpdate(BaseModel):
    start_time: Optional[UTCDateTime] = None
    end_time: Optional[UTCDateTime] = None
    status: Optional[AppointmentStatus] = None
    notes: Optional[str] = None

class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatus

# Properties shared by models stored in DB
class AppointmentInDBBase(AppointmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

# Properties to return to client
class Appointment(AppointmentInDBBase):
    pass

# Properties stored in DB
class AppointmentInDB(AppointmentInDBBase):
    pass

# Appointment with patient and doctor details
class AppointmentDetail(Appointment):
    patient_name: str
    doctor_name: str
    doctor_specialization: str
