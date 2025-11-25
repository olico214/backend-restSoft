from typing import List,Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
import socketio
import models 
from fastapi import APIRouter, Depends, HTTPException
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
    comentary: str = "" # Opcional, por defecto vacío
    type: str
    productIds: List[int]

class OrderUpdate(BaseModel):
    estatus: str
    comentary: str = ""
    productIds: Optional[List[int]] = None # <--- Nuevo campo


class InstanceUserCreate(BaseModel):
    url: str
    iduser: int

class InstanceUserUpdate(BaseModel):
    url: str
    iduser: int

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
    db_pedido = models.Pedido(
        phone=order.phone, 
        estatus="Nuevo",     # Estatus inicial
        type=order.type,     # <--- AHORA LO LEEMOS DEL FRONT
        comentary=order.comentary,
        user=user_id
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
        "user_id": user_id,
        "phone": db_pedido.phone,
        "type": db_pedido.type,         # <--- Agregado
        "comentary": db_pedido.comentary, # <--- Agregado
        "estatus": "Nuevo",
        "items": items_details,
        "created_at": str(db_pedido.id) # O un campo de fecha real si tienes
    }
    await sio.emit('nuevo_pedido', payload)
    return payload

@router.get("/orders/{user_id}")
def get_orders(user_id: int, db: Session = Depends(models.get_db)):
    # Traemos los pedidos del usuario con sus relaciones
    orders = db.query(models.Pedido).filter(models.Pedido.user == user_id).order_by(models.Pedido.id.desc()).all()
    
    # Formateamos para que el front lo entienda fácil
    result = []
    for o in orders:
        items = []
        for rel in o.items:
            # Asumiendo que tu relación está bien configurada en models.py
            if rel.product:
                items.append({"name": rel.product.name, "price": rel.product.price})
        
        result.append({
            "id": o.id,
            "phone": o.phone,
            "type": o.type,
            "estatus": o.estatus,
            "comentary": o.comentary,
            "items": items
        })
    return result

@router.put("/orders/{order_id}")
async def update_order(order_id: int, order_update: OrderUpdate, db: Session = Depends(models.get_db)):
    db_pedido = db.query(models.Pedido).filter(models.Pedido.id == order_id).first()
    
    if not db_pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    # A. Actualizar datos básicos
    db_pedido.estatus = order_update.estatus
    if order_update.comentary:
        db_pedido.comentary = order_update.comentary

    # B. Actualizar Productos (Solo si se envía la lista)
    if order_update.productIds is not None:
        # 1. Borrar relaciones existentes para este pedido
        db.query(models.ProductsPedidos).filter(models.ProductsPedidos.idPedido == order_id).delete()
        
        # 2. Insertar las nuevas relaciones
        for prod_id in order_update.productIds:
            relacion = models.ProductsPedidos(idProducts=prod_id, idPedido=order_id)
            db.add(relacion)

    db.commit()
    db.refresh(db_pedido)

    # C. Reconstruir respuesta para el WebSocket
    items_details = []
    # Volvemos a consultar para traer las relaciones nuevas
    updated_items = db.query(models.ProductsPedidos).filter(models.ProductsPedidos.idPedido == order_id).all()
    
    for rel in updated_items:
        if rel.product:
            items_details.append({"name": rel.product.name, "price": rel.product.price})

    payload = {
        "id": db_pedido.id,
        "user_id": db_pedido.user,
        "phone": db_pedido.phone,
        "type": db_pedido.type,
        "estatus": db_pedido.estatus,
        "comentary": db_pedido.comentary,
        "items": items_details
    }

    await sio.emit('actualizar_pedido', payload)

    return payload


# --- RUTAS DE INSTANCE USER ---

# 1. Crear nueva instancia
@router.post("/instance_user/")
def create_instance_user(instance: InstanceUserCreate, db: Session = Depends(models.get_db)):
    db_instance = models.InstanceUser(
        url=instance.url,
        iduser=instance.iduser
    )
    db.add(db_instance)
    db.commit()
    db.refresh(db_instance)
    return db_instance

# 2. Obtener instancias por ID de usuario
@router.get("/instance_user/{user_id}")
def get_instances_by_user(user_id: int, db: Session = Depends(models.get_db)):
    return db.query(models.InstanceUser).filter(models.InstanceUser.iduser == user_id).all()


@router.put("/instance_user/{instance_id}")
def update_instance_user(instance_id: int, instance: InstanceUserUpdate, db: Session = Depends(models.get_db)):
    # 1. Buscar el registro por su ID
    db_instance = db.query(models.InstanceUser).filter(models.InstanceUser.id == instance_id).first()

    # 2. Verificar si existe
    if not db_instance:
        raise HTTPException(status_code=404, detail="Instancia no encontrada")

    # 3. Actualizar los datos
    db_instance.url = instance.url
    db_instance.iduser = instance.iduser

    # 4. Guardar cambios
    db.commit()
    db.refresh(db_instance)
    
    return db_instance