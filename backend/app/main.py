"""API da Dhayana Store: agentes de IA da loja (começando pelo Redator)."""
import logging
import os
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import carregar_env

carregar_env()

from .ia import oracle_do_ambiente  # noqa: E402
from .redator import CATEGORIAS, Redator  # noqa: E402

log = logging.getLogger("dhayana")
app = FastAPI(title="Dhayana Store API", version="0.1.0")
origens = [o.strip() for o in os.getenv("DHAYANA_ORIGENS", "http://localhost:5173,http://127.0.0.1:5173,https://leonardogmendoza.github.io").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origens, allow_methods=["GET", "POST"], allow_headers=["*"])

redator = Redator(oracle_do_ambiente(), tienda=os.getenv("DHAYANA_TIENDA", "Dhayana Store"),
                  ciudad=os.getenv("DHAYANA_CIUDAD", "Trujillo"), moneda=os.getenv("DHAYANA_MONEDA", "S/"))
_pedidos = defaultdict(deque)


def limitar(request: Request, maximo=20, janela=60):
    """Protege o custo da Oracle: no máximo 20 pedidos por minuto por IP."""
    ip = request.headers.get("cf-connecting-ip") or request.headers.get("x-real-ip") or (request.client.host if request.client else "?")
    agora, fila = time.time(), _pedidos[ip]
    while fila and agora - fila[0] > janela:
        fila.popleft()
    if len(fila) >= maximo:
        raise HTTPException(429, "Muchos pedidos. Espera un minuto.")
    fila.append(agora)


class PedidoRedator(BaseModel):
    texto: str = Field(..., min_length=5, max_length=2500)
    costo: float = Field(0, ge=0, le=100000)
    ganancia: float = Field(20, ge=0, le=100000)


@app.get("/health")
def health():
    return {"ok": True, "ia": redator.chat is not None, "categorias": CATEGORIAS}


@app.post("/redator")
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
