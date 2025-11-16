import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from bson import ObjectId
from passlib.context import CryptContext

from database import db, create_document, get_documents, get_document_by_id, update_document, delete_document
from schemas import User, Category, Fooditem, Order

app = FastAPI(title="Food Court Ordering API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============ Auth models (simple tokenless demo auth for this environment) ==========
class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    is_admin: bool


# ===================== Public Endpoints =====================
@app.get("/")
def root():
    return {"message": "Food Court Ordering API running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["connection_status"] = "Connected"
            response["collections"] = db.list_collection_names()
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


# ===================== Auth =====================
@app.post("/auth/signup", response_model=LoginResponse)
def signup(payload: SignupRequest):
    # Check existing user
    existing = get_documents("user", {"email": payload.email}, limit=1)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    password_hash = pwd_context.hash(payload.password)
    user = User(name=payload.name, email=payload.email, password_hash=password_hash)
    user_id = create_document("user", user)
    return LoginResponse(user_id=user_id, name=user.name, email=user.email, is_admin=user.is_admin)


@app.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    users = get_documents("user", {"email": payload.email}, limit=1)
    if not users:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user = users[0]
    if not pwd_context.verify(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return LoginResponse(user_id=user["_id"], name=user["name"], email=user["email"], is_admin=user.get("is_admin", False))


# ===================== Categories =====================
class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None


@app.get("/categories")
def list_categories():
    return get_documents("category", {"is_active": True}, sort=[["name", 1]])


@app.post("/admin/categories")
def create_category(payload: CategoryCreate):
    cat = Category(**payload.model_dump())
    cat_id = create_document("category", cat)
    return {"_id": cat_id}


@app.put("/admin/categories/{category_id}")
def update_category(category_id: str, payload: CategoryCreate):
    ok = update_document("category", category_id, payload.model_dump())
    if not ok:
        raise HTTPException(404, "Category not found")
    return {"updated": True}


@app.delete("/admin/categories/{category_id}")
def remove_category(category_id: str):
    ok = delete_document("category", category_id)
    if not ok:
        raise HTTPException(404, "Category not found")
    return {"deleted": True}


# ===================== Food Items =====================
class FoodItemCreate(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category_id: str
    image_url: Optional[str] = None
    tags: Optional[List[str]] = []
    is_available: bool = True


@app.get("/items")
def list_items(q: Optional[str] = None, category: Optional[str] = None, min_price: Optional[float] = None, max_price: Optional[float] = None):
    filter_q = {"is_available": True}
    if category:
        filter_q["category_id"] = category
    if q:
        filter_q["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"tags": {"$elemMatch": {"$regex": q, "$options": "i"}}}
        ]
    if min_price is not None or max_price is not None:
        price_filter = {}
        if min_price is not None:
            price_filter["$gte"] = min_price
        if max_price is not None:
            price_filter["$lte"] = max_price
        filter_q["price"] = price_filter
    return get_documents("fooditem", filter_q, sort=[["title", 1]])


@app.get("/items/{item_id}")
def get_item(item_id: str):
    item = get_document_by_id("fooditem", item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    return item


@app.post("/admin/items")
def create_item(payload: FoodItemCreate):
    item = Fooditem(**payload.model_dump())
    item_id = create_document("fooditem", item)
    return {"_id": item_id}


@app.put("/admin/items/{item_id}")
def update_item(item_id: str, payload: FoodItemCreate):
    ok = update_document("fooditem", item_id, payload.model_dump())
    if not ok:
        raise HTTPException(404, "Item not found")
    return {"updated": True}


@app.delete("/admin/items/{item_id}")
def delete_item(item_id: str):
    ok = delete_document("fooditem", item_id)
    if not ok:
        raise HTTPException(404, "Item not found")
    return {"deleted": True}


# ===================== Orders =====================
class CartItem(BaseModel):
    item_id: str
    title: str
    price: float
    quantity: int
    image_url: Optional[str] = None


class CreateOrderRequest(BaseModel):
    user_id: Optional[str] = None
    items: List[CartItem]
    notes: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    pickup_name: Optional[str] = None


class UpdateOrderStatusRequest(BaseModel):
    status: str


@app.post("/orders")
def create_order(payload: CreateOrderRequest):
    if not payload.items:
        raise HTTPException(400, "Cart is empty")
    subtotal = sum(i.price * i.quantity for i in payload.items)
    tax = round(subtotal * 0.08, 2)
    total = round(subtotal + tax, 2)
    order_number = f"ORD-{str(ObjectId())[-6:].upper()}"
    order = Order(
        user_id=payload.user_id,
        order_number=order_number,
        items=[i.model_dump() for i in payload.items],
        subtotal=subtotal,
        tax=tax,
        total=total,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        pickup_name=payload.pickup_name,
        notes=payload.notes,
    )
    order_id = create_document("order", order)
    return {"_id": order_id, "order_number": order_number, "total": total}


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    order = get_document_by_id("order", order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    return order


@app.get("/orders")
def list_orders(user_id: Optional[str] = None):
    filt = {"user_id": user_id} if user_id else {}
    return get_documents("order", filt, sort=[["created_at", -1]])


@app.put("/admin/orders/{order_id}/status")
def update_order_status(order_id: str, payload: UpdateOrderStatusRequest):
    ok = update_document("order", order_id, {"status": payload.status})
    if not ok:
        raise HTTPException(404, "Order not found")
    return {"updated": True}


# ===================== Schema Export for Docs =====================
@app.get("/schema")
def get_schema():
    return {
        "collections": [
            "user",
            "category",
            "fooditem",
            "order"
        ],
        "notes": "Each class in schemas.py maps to a MongoDB collection (lowercase)."
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
