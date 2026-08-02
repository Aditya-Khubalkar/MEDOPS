from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class Patient(Base):
    __tablename__ = "patients"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    age = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    cases = relationship("Case", back_populates="patient")

class Case(Base):
    __tablename__ = "cases"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    status = Column(String, default="En Route") # En Route, Arrived, Triaged, Discharged
    priority = Column(String) # ESI-1, ESI-2...
    eta_minutes = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    patient = relationship("Patient", back_populates="cases")
    assessments = relationship("TriageAssessment", back_populates="case")

class TriageAssessment(Base):
    __tablename__ = "triage_assessments"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"))
    patient_input = Column(Text)
    chief_complaint = Column(String)
    audit_report = Column(Text)
    trace_id = Column(String)
    red_flags = Column(JSON)
    esi_score = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    case = relationship("Case", back_populates="assessments")
