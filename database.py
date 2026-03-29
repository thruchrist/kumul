"""
KUMUL JOB SEARCH - DATABASE MODULE
===================================
Clean, normalized, production-ready database schema.

Design Principles:
- Proper normalization (3NF)
- Appropriate data types
- Strategic indexes for query performance
- Foreign key constraints for data integrity
- Timestamps for audit trails
- JSON fields only where schema flexibility is needed
- PNG-specific considerations
"""

import os
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, 
    Column, 
    String, 
    DateTime, 
    Text, 
    Integer, 
    Boolean, 
    JSON, 
    Float, 
    Enum, 
    Index, 
    CheckConstraint,
    ForeignKey,
    UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Engine with connection pooling
engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    echo=False  # Set to True for SQL debugging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ==========================================
# ENUM TYPES
# ==========================================

class ExperienceLevel(str):
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    EXECUTIVE = "executive"
    SPECIALIZED = "specialized"


class EmploymentType(str):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    CASUAL = "casual"
    INTERNSHIP = "internship"
    VOLUNTEER = "volunteer"


class InteractionType(str):
    GREETING = "greeting"
    JOB_SEARCH = "job_search"
    CATEGORY_BROWSE = "category_browse"
    SAVE_JOB = "save_job"
    VIEW_SAVED = "view_saved"
    SALARY_INQUIRY = "salary_inquiry"
    TIPS_REQUEST = "tips_request"
    PROFILE_UPDATE = "profile_update"
    HELP_REQUEST = "help_request"
    FEEDBACK = "feedback"
    ERROR = "error"
    OTHER = "other"


class AlertFrequency(str):
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


# ==========================================
# USER PROFILE TABLE
# ==========================================

class UserProfile(Base):
    """
    User profile information - one record per phone number.
    Updated incrementally as user shares information.
    """
    __tablename__ = "user_profiles"
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Identity (Phone number is the main identifier)
    phone_number = Column(String(30), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=True)
    
    # Location
    location = Column(String(100), nullable=True)  # Current location
    preferred_locations = Column(JSON, default=list)  # Array of preferred work locations
    
    # Professional Profile
    current_role = Column(String(100), nullable=True)  # Current job title
    target_roles = Column(JSON, default=list)  # Roles they're seeking
    skills = Column(JSON, default=list)  # Technical/soft skills
    experience_level = Column(String(20), nullable=True)  # entry/mid/senior/executive
    education = Column(String(200), nullable=True)  # Highest education
    qualifications = Column(JSON, default=list)  # Certificates, licenses
    
    # Preferences
    employment_type = Column(String(20), nullable=True)  # full_time/part_time/contract
    salary_min = Column(Integer, nullable=True)  # Minimum salary in PGK
    salary_max = Column(Integer, nullable=True)  # Maximum salary in PGK
    preferred_companies = Column(JSON, default=list)  # Companies they want to work for
    preferred_industries = Column(JSON, default=list)  # Industries of interest
    
    # Onboarding State
    is_onboarded = Column(Boolean, default=False)
    onboarding_step = Column(Integer, default=0)
    
    # Usage Statistics
    search_count = Column(Integer, default=0)
    jobs_saved_count = Column(Integer, default=0)
    applications_count = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_active_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)
    
    # Relationships
    saved_jobs = relationship("SavedJob", back_populates="user", cascade="all, delete-orphan")
    job_alerts = relationship("JobAlert", back_populates="user", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_profile_location', 'location'),
        Index('idx_profile_active', 'is_active'),
        Index('idx_profile_last_active', 'last_active_at'),
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for agent context"""
        return {
            "name": self.name,
            "location": self.location,
            "preferred_locations": self.preferred_locations or [],
            "current_role": self.current_role,
            "target_roles": self.target_roles or [],
            "skills": self.skills or [],
            "experience_level": self.experience_level,
            "education": self.education,
            "qualifications": self.qualifications or [],
            "employment_type": self.employment_type,
            "salary_range": f"{self.salary_min}-{self.salary_max} PGK" if self.salary_min else None,
            "preferred_companies": self.preferred_companies or [],
            "preferred_industries": self.preferred_industries or [],
            "is_onboarded": self.is_onboarded,
            "search_count": self.search_count
        }


# ==========================================
# INTERACTION LOG TABLE
# ==========================================

class InteractionLog(Base):
    """
    Detailed log of every user-bot interaction.
    Used for analytics, debugging, and improving the AI.
    """
    __tablename__ = "interaction_logs"
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # User Reference
    phone_number = Column(String(30), nullable=False, index=True)
    
    # Message Content
    user_message = Column(Text, nullable=False)
    bot_response = Column(Text, nullable=False)
    
    # Classification
    interaction_type = Column(String(30), default="other", index=True)
    intent_detected = Column(String(50), nullable=True)
    confidence_score = Column(Float, nullable=True)  # How confident was the intent detection
    
    # Extracted Entities
    entities = Column(JSON, default=dict)  # {"role": "Accountant", "location": "POM"}
    
    # Tools & Processing
    tools_used = Column(JSON, default=list)  # ["search_jobs", "save_job"]
    processing_time_ms = Column(Integer, nullable=True)  # How long the AI took
    error_message = Column(Text, nullable=True)  # If an error occurred
    
    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    client_ip = Column(String(45), nullable=True)  # IPv4/IPv6
    channel = Column(String(20), nullable=True)  # meta/twilio
    
    # Indexes
    __table_args__ = (
        Index('idx_log_type_date', 'interaction_type', 'created_at'),
        Index('idx_log_phone_date', 'phone_number', 'created_at'),
    )


# ==========================================
# SAVED JOBS TABLE
# ==========================================

class SavedJob(Base):
    """
    Jobs bookmarked by users for later review.
    """
    __tablename__ = "saved_jobs"
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # User Reference
    phone_number = Column(String(30), ForeignKey("user_profiles.phone_number", ondelete="CASCADE"), nullable=False, index=True)
    
    # Job Details
    job_title = Column(String(200), nullable=False)
    company = Column(String(200), nullable=True)
    location = Column(String(100), nullable=True)
    job_url = Column(Text, nullable=False)
    source = Column(String(100), nullable=True)  # Domain/source name
    description_snippet = Column(Text, nullable=True)
    
    # Job Metadata
    salary_range = Column(String(100), nullable=True)  # If mentioned
    employment_type = Column(String(30), nullable=True)  # full_time/part_time
    posted_date = Column(String(50), nullable=True)  # When job was posted
    
    # User Actions
    is_applied = Column(Boolean, default=False)
    applied_at = Column(DateTime, nullable=True)
    is_rejected = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)  # User's notes about this job
    
    # Timestamps
    saved_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = relationship("UserProfile", back_populates="saved_jobs")
    
    # Constraints & Indexes
    __table_args__ = (
        UniqueConstraint('phone_number', 'job_url', name='uq_user_job_url'),
        Index('idx_saved_applied', 'is_applied'),
        Index('idx_saved_date', 'saved_at'),
    )


# ==========================================
# JOB ALERTS TABLE
# ==========================================

class JobAlert(Base):
    """
    Automated job alerts set up by users.
    """
    __tablename__ = "job_alerts"
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # User Reference
    phone_number = Column(String(30), ForeignKey("user_profiles.phone_number", ondelete="CASCADE"), nullable=False, index=True)
    
    # Alert Configuration
    alert_name = Column(String(100), nullable=False)  # User-given name
    keywords = Column(JSON, default=list)  # ["Accountant", "Finance"]
    locations = Column(JSON, default=list)  # ["Port Moresby", "Lae"]
    companies = Column(JSON, default=list)  # ["BSP", "Kina Bank"]
    
    # Schedule
    frequency = Column(String(20), default="daily")  # daily/weekly/biweekly/monthly
    day_of_week = Column(Integer, nullable=True)  # 0=Monday, 6=Sunday (for weekly)
    time_of_day = Column(String(10), default="09:00")  # HH:MM format
    
    # Status
    is_active = Column(Boolean, default=True)
    last_triggered_at = Column(DateTime, nullable=True)
    last_job_count = Column(Integer, default=0)  # Jobs found in last trigger
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = relationship("UserProfile", back_populates="job_alerts")
    
    # Indexes
    __table_args__ = (
        Index('idx_alert_active', 'is_active'),
        Index('idx_alert_frequency', 'frequency'),
        Index('idx_alert_last_triggered', 'last_triggered_at'),
    )


# ==========================================
# FEEDBACK TABLE (Optional - for improvement)
# ==========================================

class UserFeedback(Base):
    """
    User feedback on job search results and AI responses.
    """
    __tablename__ = "user_feedback"
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # User Reference
    phone_number = Column(String(30), nullable=False, index=True)
    
    # Feedback Content
    feedback_type = Column(String(30), nullable=False)  # thumbs_up/thumbs_up/thumbs_down/bug/suggestion
    feedback_text = Column(Text, nullable=True)
    
    # Context
    related_interaction_id = Column(Integer, nullable=True)  # Link to interaction log
    related_job_id = Column(Integer, nullable=True)  # Link to saved job
    
    # Status
    is_resolved = Column(Boolean, default=False)
    admin_notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_feedback_type', 'feedback_type'),
        Index('idx_feedback_resolved', 'is_resolved'),
    )


# ==========================================
# TABLE CREATION
# ==========================================

def create_all_tables():
    """Create all tables in the database"""
    Base.metadata.create_all(bind=engine)
    print("✅ All tables created successfully")


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def get_db():
    """Get database session (for dependency injection)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_profile(phone_number: str) -> dict:
    """Get user profile as dictionary, return empty dict if not exists"""
    db = SessionLocal()
    try:
        profile = db.query(UserProfile).filter(
            UserProfile.phone_number == phone_number,
            UserProfile.is_active == True
        ).first()
        
        return profile.to_dict() if profile else {}
    except Exception as e:
        print(f"❌ Profile fetch error: {e}")
        return {}
    finally:
        db.close()


def update_user_profile(phone_number: str, updates: dict) -> bool:
    """Update user profile, create if doesn't exist"""
    if not updates:
        return False
    
    db = SessionLocal()
    try:
        profile = db.query(UserProfile).filter(
            UserProfile.phone_number == phone_number
        ).first()
        
        if not profile:
            profile = UserProfile(phone_number=phone_number)
            db.add(profile)
        
        # Update only valid fields
        valid_fields = [
            'name', 'location', 'preferred_locations', 'current_role',
            'target_roles', 'skills', 'experience_level', 'education',
            'qualifications', 'employment_type', 'salary_min', 'salary_max',
            'preferred_companies', 'preferred_industries', 'is_onboarded',
            'onboarding_step', 'search_count', 'jobs_saved_count', 
            'applications_count', 'is_active'
        ]
        
        for key, value in updates.items():
            if key in valid_fields and value is not None:
                setattr(profile, key, value)
        
        profile.updated_at = datetime.now(timezone.utc)
        profile.last_active_at = datetime.now(timezone.utc)
        
        db.commit()
        return True
    except Exception as e:
        print(f"❌ Profile update error: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def append_to_list_field(phone_number: str, field: str, value: str) -> bool:
    """Append a value to a list field (skills, target_roles, etc.)"""
    db = SessionLocal()
    try:
        profile = db.query(UserProfile).filter(
            UserProfile.phone_number == phone_number
        ).first()
        
        if not profile:
            return False
        
        current_list = getattr(profile, field, []) or []
        if value not in current_list:
            current_list.append(value)
            setattr(profile, field, current_list)
            profile.updated_at = datetime.now(timezone.utc)
            profile.last_active_at = datetime.now(timezone.utc)
            db.commit()
        
        return True
    except Exception as e:
        print(f"❌ Append to list error: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def log_interaction(
    phone_number: str, 
    user_message: str, 
    bot_response: str,
    interaction_type: str = "other",
    tools_used: list = None,
    intent: str = None,
    entities: dict = None,
    processing_time_ms: int = None,
    error_message: str = None,
    client_ip: str = None,
    channel: str = None
) -> int:
    """Log interaction and return the log ID"""
    db = SessionLocal()
    try:
        log = InteractionLog(
            phone_number=phone_number,
            user_message=user_message[:5000],  # Limit message length
            bot_response=bot_response[:10000],  # Limit response length
            interaction_type=interaction_type,
            intent_detected=intent,
            entities=entities or {},
            tools_used=tools_used or [],
            processing_time_ms=processing_time_ms,
            error_message=error_message,
            client_ip=client_ip,
            channel=channel
        )
        db.add(log)
        
        # Update user's last active
        profile = db.query(UserProfile).filter(
            UserProfile.phone_number == phone_number
        ).first()
        if profile:
            profile.last_active_at = datetime.now(timezone.utc)
        
        db.commit()
        return log.id
    except Exception as e:
        print(f"❌ Logging Error: {e}")
        db.rollback()
        return -1
    finally:
        db.close()


def save_job_for_user(phone_number: str, job_data: dict) -> int:
    """Save a job for user, return job ID (-1 if duplicate)"""
    db = SessionLocal()
    try:
        # Check for duplicate
        existing = db.query(SavedJob).filter(
            SavedJob.phone_number == phone_number,
            SavedJob.job_url == job_data.get("url")
        ).first()
        
        if existing:
            return -1  # Duplicate
        
        job = SavedJob(
            phone_number=phone_number,
            job_title=job_data.get("title", "Unknown")[:200],
            company=job_data.get("company")[:200] if job_data.get("company") else None,
            location=job_data.get("location")[:100] if job_data.get("location") else None,
            job_url=job_data.get("url"),
            source=job_data.get("source")[:100] if job_data.get("source") else None,
            description_snippet=job_data.get("description")[:500] if job_data.get("description") else None,
            salary_range=job_data.get("salary")[:100] if job_data.get("salary") else None,
            employment_type=job_data.get("employment_type")[:30] if job_data.get("employment_type") else None
        )
        db.add(job)
        
        # Update user's saved jobs count
        profile = db.query(UserProfile).filter(
            UserProfile.phone_number == phone_number
        ).first()
        if profile:
            profile.jobs_saved_count = (profile.jobs_saved_count or 0) + 1
        
        db.commit()
        return job.id
    except Exception as e:
        print(f"❌ Save job error: {e}")
        db.rollback()
        return -2  # Error
    finally:
        db.close()


def get_saved_jobs(phone_number: str, limit: int = 20) -> list:
    """Get saved jobs for user"""
    db = SessionLocal()
    try:
        jobs = db.query(SavedJob).filter(
            SavedJob.phone_number == phone_number
        ).order_by(SavedJob.saved_at.desc()).limit(limit).all()
        
        return [{
            "id": job.id,
            "title": job.job_title,
            "company": job.company,
            "location": job.location,
            "url": job.job_url,
            "source": job.source,
            "salary": job.salary_range,
            "type": job.employment_type,
            "saved_at": job.saved_at.strftime("%Y-%m-%d"),
            "is_applied": job.is_applied,
            "applied_at": job.applied_at.strftime("%Y-%m-%d") if job.applied_at else None
        } for job in jobs]
    except Exception as e:
        print(f"❌ Get saved jobs error: {e}")
        return []
    finally:
        db.close()


def mark_job_applied(job_id: int, phone_number: str) -> bool:
    """Mark a saved job as applied"""
    db = SessionLocal()
    try:
        job = db.query(SavedJob).filter(
            SavedJob.id == job_id,
            SavedJob.phone_number == phone_number
        ).first()
        
        if not job:
            return False
        
        job.is_applied = True
        job.applied_at = datetime.now(timezone.utc)
        
        # Update user's applications count
        profile = db.query(UserProfile).filter(
            UserProfile.phone_number == phone_number
        ).first()
        if profile:
            profile.applications_count = (profile.applications_count or 0) + 1
        
        db.commit()
        return True
    except Exception as e:
        print(f"❌ Mark applied error: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def delete_saved_job(job_id: int, phone_number: str) -> bool:
    """Delete a saved job"""
    db = SessionLocal()
    try:
        job = db.query(SavedJob).filter(
            SavedJob.id == job_id,
            SavedJob.phone_number == phone_number
        ).first()
        
        if not job:
            return False
        
        db.delete(job)
        
        # Update user's saved jobs count
        profile = db.query(UserProfile).filter(
            UserProfile.phone_number == phone_number
        ).first()
        if profile:
            profile.jobs_saved_count = max(0, (profile.jobs_saved_count or 1) - 1)
        
        db.commit()
        return True
    except Exception as e:
        print(f"❌ Delete saved job error: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def create_job_alert(phone_number: str, alert_data: dict) -> int:
    """Create a new job alert"""
    db = SessionLocal()
    try:
        alert = JobAlert(
            phone_number=phone_number,
            alert_name=alert_data.get("name", "My Alert"),
            keywords=alert_data.get("keywords", []),
            locations=alert_data.get("locations", []),
            companies=alert_data.get("companies", []),
            frequency=alert_data.get("frequency", "daily"),
            day_of_week=alert_data.get("day_of_week"),
            time_of_day=alert_data.get("time_of_day", "09:00")
        )
        db.add(alert)
        db.commit()
        return alert.id
    except Exception as e:
        print(f"❌ Create alert error: {e}")
        db.rollback()
        return -1
    finally:
        db.close()


def get_job_alerts(phone_number: str) -> list:
    """Get all job alerts for a user"""
    db = SessionLocal()
    try:
        alerts = db.query(JobAlert).filter(
            JobAlert.phone_number == phone_number
        ).order_by(JobAlert.created_at.desc()).all()
        
        return [{
            "id": alert.id,
            "name": alert.alert_name,
            "keywords": alert.keywords,
            "locations": alert.locations,
            "companies": alert.companies,
            "frequency": alert.frequency,
            "is_active": alert.is_active,
            "last_triggered": alert.last_triggered_at.strftime("%Y-%m-%d") if alert.last_triggered_at else "Never",
            "last_job_count": alert.last_job_count
        } for alert in alerts]
    except Exception as e:
        print(f"❌ Get alerts error: {e}")
        return []
    finally:
        db.close()


def toggle_alert_status(alert_id: int, phone_number: str) -> bool:
    """Toggle alert active/inactive status"""
    db = SessionLocal()
    try:
        alert = db.query(JobAlert).filter(
            JobAlert.id == alert_id,
            JobAlert.phone_number == phone_number
        ).first()
        
        if not alert:
            return False
        
        alert.is_active = not alert.is_active
        alert.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True
    except Exception as e:
        print(f"❌ Toggle alert error: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def delete_alert(alert_id: int, phone_number: str) -> bool:
    """Delete a job alert"""
    db = SessionLocal()
    try:
        alert = db.query(JobAlert).filter(
            JobAlert.id == alert_id,
            JobAlert.phone_number == phone_number
        ).first()
        
        if not alert:
            return False
        
        db.delete(alert)
        db.commit()
        return True
    except Exception as e:
        print(f"❌ Delete alert error: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def save_feedback(phone_number: str, feedback_type: str, feedback_text: str = None) -> int:
    """Save user feedback"""
    db = SessionLocal()
    try:
        feedback = UserFeedback(
            phone_number=phone_number,
            feedback_type=feedback_type,
            feedback_text=feedback_text
        )
        db.add(feedback)
        db.commit()
        return feedback.id
    except Exception as e:
        print(f"❌ Save feedback error: {e}")
        db.rollback()
        return -1
    finally:
        db.close()


def get_user_stats(phone_number: str) -> dict:
    """Get usage statistics for a user"""
    db = SessionLocal()
    try:
        profile = db.query(UserProfile).filter(
            UserProfile.phone_number == phone_number
        ).first()
        
        if not profile:
            return {
                "total_searches": 0,
                "total_saved": 0,
                "total_applied": 0,
                "total_alerts": 0,
                "member_since": None
            }
        
        alert_count = db.query(JobAlert).filter(
            JobAlert.phone_number == phone_number,
            JobAlert.is_active == True
        ).count()
        
        return {
            "total_searches": profile.search_count or 0,
            "total_saved": profile.jobs_saved_count or 0,
            "total_applied": profile.applications_count or 0,
            "total_alerts": alert_count,
            "member_since": profile.created_at.strftime("%Y-%m-%d")
        }
    except Exception as e:
        print(f"❌ Get stats error: {e}")
        return {}
    finally:
        db.close()


# ==========================================
# AUTO-CREATE TABLES ON IMPORT
# ==========================================

Base.metadata.create_all(bind=engine)