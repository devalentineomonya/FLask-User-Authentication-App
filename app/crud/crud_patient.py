from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.crud.crud_base import CRUDBase
from app.db.models import Patient
from app.schemas.patient import PatientCreate, PatientUpdate

class CRUDPatient(CRUDBase[Patient, PatientCreate, PatientUpdate]):
    def get_by_email(self, db: Session, *, email: str) -> Optional[Patient]:
        return db.query(Patient).filter(Patient.email == email).first()

    def search(self, db: Session, *, query: str) -> List[Patient]:
        search_query = f"%{query}%"
        return db.query(Patient).filter(
            or_(
                Patient.first_name.ilike(search_query),
                Patient.last_name.ilike(search_query),
                Patient.email.ilike(search_query)
            )
        ).all()

patient = CRUDPatient(Patient)
