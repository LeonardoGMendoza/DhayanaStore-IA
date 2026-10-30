"""API da Dhayana Store: agentes de IA da loja (Redator e Despachante)."""
import hmac
import logging
import os
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from .config import carregar_env

carregar_env()

from .ia import oracle_do_ambiente  # noqa: E402
from .pedidos import ESTADOS, METODOS, PAGOS, SIGUIENTE, TZ, Pedidos, leer_mensaje, link_whatsapp, mensaje_cliente  # noqa: E402
from .redator import CATEGORIAS, Redator  # noqa: E402

log = logging.getLogger("dhayana")
app = FastAPI(title="Dhayana Store API", version="0.2.0")
origens = [o.strip() for o in os.getenv("DHAYANA_ORIGENS", "http://localhost:5173,http://127.0.0.1:5173,https://leonardogmendoza.github.io").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origens, allow_methods=["GET", "POST", "PATCH"], allow_headers=["*"])

MONEDA = os.getenv("DHAYANA_MONEDA", "S/")
PAIS = os.getenv("DHAYANA_PAIS_TEL", "51")  # código de país para los celulares sin prefijo
# Link público de seguimiento, ej. https://leonardogmendoza.github.io/MarketplaceDhayanaNicol/seguimiento.html?c=
LINK_SEGUIMIENTO = os.getenv("DHAYANA_LINK_SEGUIMIENTO", "")
TOKEN = os.getenv("DHAYANA_ADMIN_TOKEN", "")

redator = Redator(oracle_do_ambiente(), tienda=os.getenv("DHAYANA_TIENDA", "Dhayana Store"),
                  ciudad=os.getenv("DHAYANA_CIUDAD", "Trujillo"), moneda=MONEDA)
pedidos = Pedidos(os.getenv("DHAYANA_DATA_DIR", "./data"))
_pedidos = defaultdict(deque)
if not TOKEN:
    log.warning("DHAYANA_ADMIN_TOKEN vacío: el panel está abierto. Úsalo solo en tu computadora.")


def limitar(request: Request, maximo=20, janela=60):
    """Protege o custo da Oracle e o seguimento: no máximo 20 pedidos por minuto por IP."""
    ip = request.headers.get("cf-connecting-ip") or request.headers.get("x-real-ip") or (request.client.host if request.client else "?")
    agora, fila = time.time(), _pedidos[ip]
    while fila and agora - fila[0] > janela:
        fila.popleft()
    if len(fila) >= maximo:
        raise HTTPException(429, "Muchos pedidos. Espera un minuto.")
    fila.append(agora)


def admin(request: Request):
    """Só a vendedora usa o painel: com DHAYANA_ADMIN_TOKEN definido, exige o header X-Admin-Token."""
    if TOKEN and not hmac.compare_digest(request.headers.get("x-admin-token", ""), TOKEN):
        raise HTTPException(401, "Clave del panel incorrecta.")


def hoy():
    return datetime.now(TZ).date().isoformat()


def con_acciones(p):
    """Agrega al pedido el siguiente paso y el mensaje listo para WhatsApp."""
    sig = SIGUIENTE.get(p["estado"])
    link = (LINK_SEGUIMIENTO + p["codigo"]) if LINK_SEGUIMIENTO else ""
    texto = mensaje_cliente(p, p["estado"], MONEDA, link)
    p["siguiente"] = sig
    p["mensaje"] = texto
    p["whatsapp"] = link_whatsapp(p["cliente_telefono"], texto, PAIS) if texto else ""
    return p


# ---------------- Redator
class PedidoRedator(BaseModel):
    texto: str = Field(..., min_length=5, max_length=2500)
    costo: float = Field(0, ge=0, le=100000)
    ganancia: float = Field(20, ge=0, le=100000)


@app.get("/health")
def health():
    return {"ok": True, "ia": redator.chat is not None, "protegido": bool(TOKEN), "categorias": CATEGORIAS,
            "estados": ESTADOS, "pagos": PAGOS, "metodos": METODOS[1:], "moneda": MONEDA}


@app.post("/redator", dependencies=[Depends(admin)])
def escrever(pedido: PedidoRedator, request: Request):
    limitar(request)
    try:
        return redator.escrever(pedido.texto, pedido.costo, pedido.ganancia)
    except RuntimeError as erro:
        raise HTTPException(503, str(erro)) from erro
    except ValueError as erro:
        log.warning("Redator: %s", erro)
        raise HTTPException(502, "La IA respondió algo raro. Intenta de nuevo.") from erro
    except Exception as erro:  # noqa: BLE001
        log.warning("Oracle falhou: %s", type(erro).__name__)
        raise HTTPException(502, "No pude hablar con la IA ahora. Intenta en un momento.") from erro


# ---------------- Despachante
class Item(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=120)
    cantidad: int = Field(1, ge=1, le=100)
    precio: float = Field(0, ge=0, le=100000)
    costo: float = Field(0, ge=0, le=100000)


class NuevoPedido(BaseModel):
    cliente_nombre: str = Field(..., min_length=1, max_length=80)
    cliente_telefono: str = Field("", max_length=25)
    direccion: str = Field("", max_length=250)
    distrito: str = Field("", max_length=60)
    items: list[Item] = Field(..., min_length=1, max_length=30)
    delivery: float = Field(0, ge=0, le=1000)
    motorizado: str = Field("", max_length=60)
    metodo_pago: Literal["", "yape", "efectivo", "plin", "transferencia"] = ""
    origen: Literal["whatsapp", "marketplace", "catalogo", "otro"] = "whatsapp"
    notas: str = Field("", max_length=500)


class CambioEstado(BaseModel):
    estado: Literal["nuevo", "confirmado", "recogido", "en_camino", "entregado", "rechazado", "cancelado"]


class Cambios(BaseModel):
    pago: Literal["pendiente", "pagado", "repasado"] | None = None
    metodo_pago: Literal["", "yape", "efectivo", "plin", "transferencia"] | None = None
    motorizado: str | None = Field(None, max_length=60)
    delivery: float | None = Field(None, ge=0, le=1000)
    notas: str | None = Field(None, max_length=500)
    cliente_telefono: str | None = Field(None, max_length=25)
    direccion: str | None = Field(None, max_length=250)
    distrito: str | None = Field(None, max_length=60)


class Mensaje(BaseModel):
    texto: str = Field(..., min_length=3, max_length=3000)


@app.post("/pedidos/leer-mensaje", dependencies=[Depends(admin)])
def leer(m: Mensaje):
    """Pega el mensaje que llegó del catálogo y devuelve el pedido ya armado para revisar."""
    return leer_mensaje(m.texto)


@app.post("/pedidos", dependencies=[Depends(admin)])
def crear(p: NuevoPedido):
    try:
        return con_acciones(pedidos.crear(p.model_dump()))
    except ValueError as erro:
        raise HTTPException(422, str(erro)) from erro


@app.get("/pedidos", dependencies=[Depends(admin)])
def listar(dia: str | None = None, estado: str | None = None, todos: bool = False):
    dia = None if todos else (dia or hoy())
    return [con_acciones(p) for p in pedidos.listar(dia=dia, estado=estado)]


@app.get("/pedidos/resumen", dependencies=[Depends(admin)])
def resumen(dia: str | None = None):
    return pedidos.resumen(dia or hoy())


@app.get("/pedidos/dataset.csv", dependencies=[Depends(admin)], response_class=PlainTextResponse)
def dataset():
    return PlainTextResponse(pedidos.csv(), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=pedidos_dataset.csv"})


@app.get("/pedidos/{pid}", dependencies=[Depends(admin)])
def obtener(pid: int):
    p = pedidos.obtener(pid)
    if not p:
        raise HTTPException(404, "Pedido no encontrado")
    p = con_acciones(p)
    p["historial"] = pedidos.historial(pid)
    return p


@app.post("/pedidos/{pid}/estado", dependencies=[Depends(admin)])
def cambiar_estado(pid: int, c: CambioEstado):
    try:
        return con_acciones(pedidos.cambiar_estado(pid, c.estado))
    except KeyError as erro:
        raise HTTPException(404, "Pedido no encontrado") from erro
    except ValueError as erro:
        raise HTTPException(409, str(erro)) from erro


@app.patch("/pedidos/{pid}", dependencies=[Depends(admin)])
def actualizar(pid: int, c: Cambios):
    try:
        return con_acciones(pedidos.actualizar(pid, c.model_dump(exclude_none=True)))
    except KeyError as erro:
        raise HTTPException(404, "Pedido no encontrado") from erro
    except ValueError as erro:
        raise HTTPException(422, str(erro)) from erro


@app.get("/seguimiento/{codigo}")
def seguimiento(codigo: str, request: Request):
    """Público, para el cliente: solo el estado. Nunca devuelve teléfono ni dirección."""
    limitar(request)
    p = pedidos.por_codigo(codigo[:12])
    if not p:
        raise HTTPException(404, "No encontramos ese pedido")
    return {"codigo": p["codigo"], "estado": p["estado"], "creado_en": p["creado_en"],
            "productos": [f"{i['cantidad']} × {i['nombre']}" for i in p["items"]],
            "total": p["total_cliente"], "moneda": MONEDA,
            "historial": pedidos.historial(p["id"])}
