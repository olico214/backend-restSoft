from typing import List
from sqlalchemy.orm import Session
from pydantic import BaseModel
import socketio
import models 
from fastapi import APIRouter, Depends, HTTPException # <--- Agrega HTTPException
# 1. Creamos el Router y la instancia de SocketIO aquí
router = APIRouter()
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')

# --- ESQUEMAS (Validación de datos que entran) ---
class ProductCreate(BaseModel):
    name: str
    price: float
    estatus: str
    user: int

class OrderCreate(BaseModel):
    phone: str
    productIds: List[int]

# --- RUTAS DE PRODUCTOS ---
@router.post("/products/")
def create_product(product: ProductCreate, db: Session = Depends(models.get_db)):
    db_product = models.Product(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

@router.get("/products/{user_id}")
def list_products_by_user(user_id: int, db: Session = Depends(models.get_db)):
    # Filtramos donde la columna 'user' sea igual al 'user_id' que recibimos
    products = db.query(models.Product).filter(models.Product.user == user_id).all()
    return products


@router.put("/products/{product_id}")
def update_product(product_id: int, product: ProductCreate, db: Session = Depends(models.get_db)):
    # 1. Buscar el producto por su ID
    db_product = db.query(models.Product).filter(models.Product.id == product_id).first()

    # 2. Verificar si existe
    if not db_product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # 3. Actualizar los campos con los nuevos datos
    db_product.name = product.name
    db_product.price = product.price
    db_product.estatus = product.estatus
    # Opcional: si quieres permitir cambiar de usuario, descomenta la siguiente línea:
    # db_product.user = product.user 

    # 4. Guardar cambios en la base de datos
    db.commit()
    db.refresh(db_product)
    
    return db_product


# En apis.py

@router.post("/orders/{user_id}")
async def create_order(user_id: int, order: OrderCreate, db: Session = Depends(models.get_db)):
    # 1. Guardar Pedido (Ahora pasamos el user_id)
    db_pedido = models.Pedido(
        phone=order.phone, 
        estatus="pendiente", 
        user=user_id  # <--- Aquí asignamos el ID que viene de la URL
    )
    
    db.add(db_pedido)
    db.commit()
    db.refresh(db_pedido)

    # 2. Guardar Relaciones (Esto sigue igual)
    items_details = []
    for prod_id in order.productIds:
        relacion = models.ProductsPedidos(idProducts=prod_id, idPedido=db_pedido.id)
        db.add(relacion)
        
        prod = db.query(models.Product).filter(models.Product.id == prod_id).first()
        if prod:
            items_details.append({"name": prod.name, "price": prod.price})
    
    db.commit()

    # 3. Preparar Payload WebSocket
    payload = {
        "id": db_pedido.id,
        "user_id": user_id, # <--- Enviamos esto para filtrar en el frontend
        "phone": db_pedido.phone,
        "estatus": "pendiente",
        "items": items_details
    }

    # 4. Emitir Evento
    # Nota: Esto le avisa a TODOS. El frontend deberá filtrar si el mensaje es para él.
    await sio.emit('nuevo_pedido', payload)
    
    return payload