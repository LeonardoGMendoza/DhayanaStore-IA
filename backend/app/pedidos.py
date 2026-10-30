"""Agente Despachante: pedidos, estados, pagos y el resumen del día.

Cada pedido guardado es también una fila del dataset para el machine learning
(ej.: ¿qué pedidos terminan "rechazado" en la puerta?). Por eso se guarda el
historial de estados con fecha y hora, y se puede exportar a CSV.
"""
import csv
import io
import json
import re
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Perú no tiene horario de verano: UTC-5 todo el año
TZ = timezone(timedelta(hours=-5))

ESTADOS = ["nuevo", "confirmado", "recogido", "en_camino", "entregado", "rechazado", "cancelado"]
FINALES = {"entregado", "rechazado", "cancelado"}
SIGUIENTE = {"nuevo": "confirmado", "confirmado": "recogido", "recogido": "en_camino", "en_camino": "entregado"}
PAGOS = ["pendiente", "pagado", "repasado"]  # repasado = el motorizado ya le pasó el dinero (Yape)
METODOS = ["", "yape", "efectivo", "plin", "transferencia"]

MENSAJES = {
    "confirmado": "¡Hola {nombre}! 😊 Tu pedido #{codigo} está confirmado. Total: {moneda} {total}. Te avisamos cuando salga.",
    "recogido": "¡Hola {nombre}! Ya tenemos tu pedido #{codigo} listo para salir 📦",
    "en_camino": "¡Hola {nombre}! Tu pedido #{codigo} ya está en camino 🛵 Total a pagar: {moneda} {total}. Síguelo aquí: {link}",
    "entregado": "¡Gracias por tu compra, {nombre}! 💛 Esperamos que disfrutes tu pedido. Cualquier cosa, aquí estamos.",
    "cancelado": "Hola {nombre}, tu pedido #{codigo} fue cancelado. Si quieres, te ayudamos a elegir otro producto.",
}

ESQUEMA = """
CREATE TABLE IF NOT EXISTS pedidos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  codigo TEXT UNIQUE NOT NULL,
  creado_en TEXT NOT NULL,
  actualizado_en TEXT NOT NULL,
  cliente_nombre TEXT NOT NULL,
  cliente_telefono TEXT NOT NULL DEFAULT '',
  direccion TEXT NOT NULL DEFAULT '',
  distrito TEXT NOT NULL DEFAULT '',
  items TEXT NOT NULL,
  total_productos REAL NOT NULL,
  costo_productos REAL NOT NULL,
  delivery REAL NOT NULL DEFAULT 0,
  motorizado TEXT NOT NULL DEFAULT '',
  estado TEXT NOT NULL DEFAULT 'nuevo',
  pago TEXT NOT NULL DEFAULT 'pendiente',
  metodo_pago TEXT NOT NULL DEFAULT '',
  origen TEXT NOT NULL DEFAULT 'whatsapp',
  notas TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS historial (
  pedido_id INTEGER NOT NULL REFERENCES pedidos(id),
  estado TEXT NOT NULL,
  en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pedidos_creado ON pedidos(creado_en);
"""


def ahora():
    return datetime.now(TZ).isoformat(timespec="seconds")


def numero(txt):
    """'S/ 1,250.50' -> 1250.5"""
    t = re.sub(r"[^\d.,]", "", txt or "")
    if "," in t and "." in t:
        t = t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return 0.0


def leer_mensaje(texto):
    """Lee el mensaje que manda el catálogo web por WhatsApp y arma el pedido.

    • 2 × Mesa auxiliar con divisiones — S/ 190
    Nombre: Ana
    Entrega en: La Esperanza
    """
    items, nombre, direccion = [], "", ""
    for linea in (texto or "").splitlines():
        linea = linea.strip()
        m = re.match(r"^[•\-*]\s*(\d+)\s*[×xX]\s*(.+?)(?:\s+[—–-]\s+(.+))?$", linea)
        if m:
            cant, nombre_prod, precio_txt = int(m.group(1)), m.group(2).strip(), m.group(3) or ""
            nombre_prod = re.sub(r"\s*\(consultar precio\)$", "", nombre_prod)
            subtotal = numero(precio_txt)
            items.append({"nombre": nombre_prod, "cantidad": cant, "precio": round(subtotal / cant, 2) if cant else 0, "costo": 0})
            continue
        m = re.match(r"^nombre\s*:\s*(.+)$", linea, re.I)
        if m:
            nombre = m.group(1).strip()
            continue
        m = re.match(r"^entrega en\s*:\s*(.+)$", linea, re.I)
        if m:
            direccion = m.group(1).strip()
    return {"cliente_nombre": nombre, "direccion": direccion, "items": items}


def mensaje_cliente(pedido, estado, moneda="S/", link_seguimiento=""):
    plantilla = MENSAJES.get(estado)
    if not plantilla:
        return ""
    if not link_seguimiento:
        plantilla = plantilla.replace(" Síguelo aquí: {link}", "")
    total = pedido["total_productos"] + pedido["delivery"]
    nombre = (pedido["cliente_nombre"] or "").split(" ")[0]
    return plantilla.format(nombre=nombre, codigo=pedido["codigo"], moneda=moneda, total=f"{total:g}", link=link_seguimiento)


def link_whatsapp(telefono, texto, prefijo="51"):
    tel = re.sub(r"\D", "", telefono or "")
    if not tel:
        return ""
    if len(tel) == 9:  # celular peruano sin código de país
        tel = prefijo + tel
    from urllib.parse import quote
    return f"https://wa.me/{tel}?text={quote(texto)}"


class Pedidos:
    def __init__(self, carpeta):
        Path(carpeta).mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(Path(carpeta) / "tienda.db", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(ESQUEMA)
        self._lock = threading.Lock()

    # ---------- lectura
    def _dict(self, fila):
        d = dict(fila)
        d["items"] = json.loads(d["items"])
        d["ganancia"] = round(d["total_productos"] - d["costo_productos"], 2)
        d["total_cliente"] = round(d["total_productos"] + d["delivery"], 2)
        return d

    def obtener(self, pid):
        f = self.db.execute("SELECT * FROM pedidos WHERE id = ?", (pid,)).fetchone()
        return self._dict(f) if f else None

    def por_codigo(self, codigo):
        f = self.db.execute("SELECT * FROM pedidos WHERE codigo = ?", ((codigo or "").upper(),)).fetchone()
        return self._dict(f) if f else None

    def listar(self, dia=None, estado=None):
        sql, args = "SELECT * FROM pedidos WHERE 1=1", []
        if dia:
            sql += " AND substr(creado_en, 1, 10) = ?"
            args.append(dia)
        if estado:
            sql += " AND estado = ?"
            args.append(estado)
        sql += " ORDER BY id DESC LIMIT 300"
        return [self._dict(f) for f in self.db.execute(sql, args)]

    def historial(self, pid):
        return [dict(f) for f in self.db.execute("SELECT estado, en FROM historial WHERE pedido_id = ? ORDER BY rowid", (pid,))]

    # ---------- escritura
    def crear(self, datos):
        items = [i for i in datos.get("items", []) if i.get("nombre") and i.get("cantidad", 0) > 0]
        if not items:
            raise ValueError("El pedido necesita al menos un producto")
        if not (datos.get("cliente_nombre") or "").strip():
            raise ValueError("Falta el nombre del cliente")
        total = round(sum(i["cantidad"] * i.get("precio", 0) for i in items), 2)
        costo = round(sum(i["cantidad"] * i.get("costo", 0) for i in items), 2)
        t = ahora()
        with self._lock, self.db:
            for _ in range(5):
                codigo = secrets.token_hex(3).upper()  # ej. 3F9A1C: también sirve de link de seguimiento
                try:
                    cur = self.db.execute(
                        """INSERT INTO pedidos (codigo, creado_en, actualizado_en, cliente_nombre, cliente_telefono,
                           direccion, distrito, items, total_productos, costo_productos, delivery, motorizado, metodo_pago, origen, notas)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (codigo, t, t, datos["cliente_nombre"].strip(), datos.get("cliente_telefono", "").strip(),
                         datos.get("direccion", "").strip(), datos.get("distrito", "").strip(), json.dumps(items, ensure_ascii=False), total, costo,
                         float(datos.get("delivery") or 0), datos.get("motorizado", "").strip(),
                         datos.get("metodo_pago", ""), datos.get("origen", "whatsapp"), datos.get("notas", "").strip()))
                    break
                except sqlite3.IntegrityError:
                    continue
            self.db.execute("INSERT INTO historial VALUES (?,?,?)", (cur.lastrowid, "nuevo", t))
        return self.obtener(cur.lastrowid)

    def cambiar_estado(self, pid, estado):
        if estado not in ESTADOS:
            raise ValueError("Estado inválido")
        p = self.obtener(pid)
        if not p:
            raise KeyError(pid)
        if p["estado"] in FINALES:
            raise ValueError(f"El pedido ya está {p['estado']}")
        t = ahora()
        with self._lock, self.db:
            self.db.execute("UPDATE pedidos SET estado = ?, actualizado_en = ? WHERE id = ?", (estado, t, pid))
            self.db.execute("INSERT INTO historial VALUES (?,?,?)", (pid, estado, t))
        return self.obtener(pid)

    def actualizar(self, pid, cambios):
        permitidos = {"pago", "metodo_pago", "motorizado", "delivery", "notas", "cliente_telefono", "direccion", "distrito"}
        cambios = {k: v for k, v in cambios.items() if k in permitidos and v is not None}
        if "pago" in cambios and cambios["pago"] not in PAGOS:
            raise ValueError("Pago inválido")
        if "metodo_pago" in cambios and cambios["metodo_pago"] not in METODOS:
            raise ValueError("Método de pago inválido")
        if not self.obtener(pid):
            raise KeyError(pid)
        if cambios:
            cambios["actualizado_en"] = ahora()
            cols = ", ".join(f"{k} = ?" for k in cambios)
            with self._lock, self.db:
                self.db.execute(f"UPDATE pedidos SET {cols} WHERE id = ?", (*cambios.values(), pid))
        return self.obtener(pid)

    # ---------- agente Analista (versión simple) y dataset
    def resumen(self, dia):
        ps = self.listar(dia=dia)
        validos = [p for p in ps if p["estado"] not in ("cancelado", "rechazado")]
        entregados = [p for p in ps if p["estado"] == "entregado"]
        por_cobrar = [p for p in entregados if p["pago"] != "repasado"]
        return {
            "dia": dia,
            "pedidos": len(ps),
            "entregados": len(entregados),
            "rechazados": sum(p["estado"] == "rechazado" for p in ps),
            "en_curso": sum(p["estado"] not in FINALES for p in ps),
            "ventas": round(sum(p["total_productos"] for p in entregados), 2),
            "ganancia": round(sum(p["ganancia"] for p in entregados), 2),
            "ventas_previstas": round(sum(p["total_productos"] for p in validos), 2),
            "por_repasar": round(sum(p["total_productos"] for p in por_cobrar), 2),
            "por_repasar_pedidos": [p["codigo"] for p in por_cobrar],
        }

    def csv(self):
        """Dataset para ML: una fila por pedido, con la etiqueta final (estado)."""
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["codigo", "creado_en", "dia_semana", "hora", "n_items", "unidades", "productos", "total_productos",
                    "costo_productos", "ganancia", "delivery", "distrito", "metodo_pago", "origen", "minutos_hasta_final", "estado_final"])
        for p in reversed(self.listar()):
            creado = datetime.fromisoformat(p["creado_en"])
            hist = self.historial(p["id"])
            fin = next((h["en"] for h in reversed(hist) if h["estado"] in FINALES), None)
            minutos = round((datetime.fromisoformat(fin) - creado).total_seconds() / 60) if fin else ""
            w.writerow([p["codigo"], p["creado_en"], creado.strftime("%a"), creado.hour, len(p["items"]),
                        sum(i["cantidad"] for i in p["items"]), " | ".join(i["nombre"] for i in p["items"]),
                        p["total_productos"], p["costo_productos"], p["ganancia"], p["delivery"],
                        p["distrito"],  # solo el distrito: nunca la dirección completa ni el teléfono
                        p["metodo_pago"], p["origen"], minutos, p["estado"]])
        return out.getvalue()
