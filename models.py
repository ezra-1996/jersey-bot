from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class User:
    """User model representing a Telegram user"""
    telegram_id: int
    vote_choice: Optional[str] = None
    has_voted: bool = False
    has_ordered: bool = False

@dataclass
class Order:
    """Order model for jersey orders"""
    telegram_id: int
    full_name: str
    shirt_number: int
    shirt_name: str
    size: str
    receipt_file_id: str
    payment_time: datetime

@dataclass
class Deadlines:
    """Deadlines model"""
    vote_deadline: datetime
    payment_deadline: datetime

@dataclass
class Design:
    """Design model for jersey designs"""
    id: int
    name: str
    description: str
    image_file_id: str  # Telegram file_id
    created_at: datetime
    is_active: bool = True