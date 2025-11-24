from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio
import models
import apis

# 1. Crear Tablas en BD si no existen
models.Base.metadata.create_all(bind=models.engine)

# 2. Iniciar App
app = FastAPI()

# 3. Configurar CORS (Para que Next.js no tenga problemas)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Incluir nuestras rutas (apis.py)
app.include_router(apis.router)

# 5. Montar el servidor de WebSockets
# Usamos la instancia 'sio' que creamos en apis.py
app.mount("/ws", socketio.ASGIApp(apis.sio))

print("🚀 Servidor iniciado. WebSockets en /ws")