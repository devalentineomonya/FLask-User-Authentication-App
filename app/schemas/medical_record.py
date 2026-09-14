from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

# Shared properties
class MedicalRecordBase(BaseModel):
    patient_id: int
    appointment_id: Optional[int] = None
    diagnosis: Optional[str] = None
    treatment: Optional[str] = None
    prescription: Optional[str] = None
    notes: Optional[str] = None

# Properties to receive on medical record creation
class MedicalRecordCreate(MedicalRecordBase):
    pass

# Properties to receive on medical record update
class MedicalRecordUpdate(BaseModel):
    diagnosis: Optional[str] = None
    treatment: Optional[str] = None
    prescription: Optional[str] = None
    notes: Optional[str] = None

# Properties shared by models stored in DB
class MedicalRecordInDBBase(MedicalRecordBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

# Properties to return to client
class MedicalRecord(MedicalRecordInDBBase):
    pass

# Properties stored in DB
class MedicalRecordInDB(MedicalRecordInDBBase):
    pass

