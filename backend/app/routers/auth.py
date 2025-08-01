from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, List
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from ..database import get_db
from ..models.user import User
from ..config import settings

router = APIRouter()

# Pydantic models
class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    medical_history: Optional[str] = None
    allergies: List[str] = []
    current_medications: List[str] = []
    blood_type: Optional[str] = None
    height: Optional[str] = None
    weight: Optional[str] = None

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a new access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email."""
    return db.query(User).filter(User.email == email).first()


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate a user."""
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Get current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.JWTError:
        raise credentials_exception
    
    user = get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user


@router.post("/register")
async def register_user(
    email: str,
    password: str,
    full_name: Optional[str] = None,
    age: Optional[int] = None,
    gender: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Register a new user."""
    
    # Check if user already exists
    if get_user_by_email(db, email):
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(password)
    user = User(
        email=email,
        hashed_password=hashed_password,
        full_name=full_name,
        age=age,
        gender=gender
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return {
        "message": "User registered successfully",
        "user_id": user.id,
        "email": user.email
    }


@router.post("/token")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login and get access token."""
    
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name
        }
    }


@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "date_of_birth": current_user.date_of_birth,
        "phone": current_user.phone,
        "address": current_user.address,
        "emergency_contact": current_user.emergency_contact,
        "medical_history": current_user.medical_history,
        "allergies": current_user.allergies,
        "current_medications": current_user.current_medications,
        "blood_type": current_user.blood_type,
        "height": current_user.height,
        "weight": current_user.weight,
        "age": current_user.age,
        "gender": current_user.gender,
        "is_verified": current_user.is_verified,
        "created_at": current_user.created_at,
        "last_login": current_user.last_login
    }


@router.put("/profile")
async def update_user_profile(
    profile_data: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user profile information."""
    
    # Update user fields
    if profile_data.full_name is not None:
        current_user.full_name = profile_data.full_name
    if profile_data.date_of_birth is not None:
        current_user.date_of_birth = profile_data.date_of_birth
    if profile_data.phone is not None:
        current_user.phone = profile_data.phone
    if profile_data.address is not None:
        current_user.address = profile_data.address
    if profile_data.emergency_contact is not None:
        current_user.emergency_contact = profile_data.emergency_contact
    if profile_data.medical_history is not None:
        current_user.medical_history = profile_data.medical_history
    if profile_data.blood_type is not None:
        current_user.blood_type = profile_data.blood_type
    if profile_data.height is not None:
        current_user.height = profile_data.height
    if profile_data.weight is not None:
        current_user.weight = profile_data.weight
    
    # Handle arrays - convert to comma-separated strings for storage
    if profile_data.allergies:
        current_user.allergies = ", ".join(profile_data.allergies)
    if profile_data.current_medications:
        current_user.current_medications = ", ".join(profile_data.current_medications)
    
    # Update timestamp
    current_user.updated_at = datetime.utcnow()
    
    # Save to database
    db.commit()
    db.refresh(current_user)
    
    return {
        "message": "Profile updated successfully",
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "date_of_birth": current_user.date_of_birth,
            "phone": current_user.phone,
            "address": current_user.address,
            "emergency_contact": current_user.emergency_contact,
            "medical_history": current_user.medical_history,
            "allergies": current_user.allergies,
            "current_medications": current_user.current_medications,
            "blood_type": current_user.blood_type,
            "height": current_user.height,
            "weight": current_user.weight
        }
    } 