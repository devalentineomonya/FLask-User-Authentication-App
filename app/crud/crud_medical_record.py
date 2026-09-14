from typing import List
from sqlalchemy.orm import Session

from app.crud.crud_base import CRUDBase
from app.db.models import MedicalRecord
from app.schemas.medical_record import MedicalRecordCreate, MedicalRecordUpdate

class CRUDMedicalRecord(CRUDBase[MedicalRecord, MedicalRecordCreate, MedicalRecordUpdate]):
    def get_by_patient(
        self, db: Session, *, patient_id: int, skip: int = 0, limit: int = 100
    ) -> List[MedicalRecord]:
        return (
            db.query(MedicalRecord)
            .filter(MedicalRecord.patient_id == patient_id)
            .order_by(MedicalRecord.created_at.desc(), MedicalRecord.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

medical_record = CRUDMedicalRecord(MedicalRecord)
