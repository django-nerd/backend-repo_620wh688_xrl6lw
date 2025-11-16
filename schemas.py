"""
Database Schemas for Food Court Ordering System

Each Pydantic model below corresponds to a MongoDB collection.
The collection name is the lowercase class name (e.g., User -> "user").
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, EmailStr


class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Unique email address")
    password_hash: str = Field(..., description="BCrypt password hash")
    is_admin: bool = Field(False, description="Admin privileges")
    avatar_url: Optional[str] = None
    is_active: bool = True


class Category(BaseModel):
    name: str = Field(..., description="Category name")
    description: Optional[str] = Field(None, description="Category description")
    image_url: Optional[str] = None
    is_active: bool = True


class Fooditem(BaseModel):
    title: str = Field(..., description="Item title")
    description: Optional[str] = None
    price: float = Field(..., ge=0)
    category_id: str = Field(..., description="Reference to category _id")
    image_url: Optional[str] = None
    tags: List[str] = []
    is_available: bool = True
    rating: float = 0.0


class Order(BaseModel):
    user_id: Optional[str] = Field(None, description="User placing the order (optional for guest)")
    order_number: str = Field(..., description="Human-friendly order number")
    items: List[dict] = Field(..., description="List of {item_id, title, price, quantity, image_url}")
    subtotal: float = 0.0
    tax: float = 0.0
    total: float = 0.0
    status: Literal["pending", "preparing", "ready", "completed", "cancelled"] = "pending"
    notes: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    pickup_name: Optional[str] = None
"""
Notes:
- Define new collections by creating new Pydantic classes in this file.
- The system will use these schemas for validation and documentation.
"""
