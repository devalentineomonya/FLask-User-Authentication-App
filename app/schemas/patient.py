from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional
from datetime import date, datetime

# Shared properties
class PatientBase(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    email: EmailStr
    phone: str
    address: str
    insurance_provider: Optional[str] = None
    insurance_id: Optional[str] = None

# Properties to receive on patient creation
class PatientCreate(PatientBase):
    pass

# Properties to receive on patient update
class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_id: Optional[str] = None

# Properties shared by models stored in DB
class PatientInDBBase(PatientBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

# Properties to return to client
class Patient(PatientInDBBase):
    pass

# Properties stored in DB
class PatientInDB(PatientInDBBase):
    pass

