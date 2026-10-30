import csv
import io

import pytest

from app.pedidos import Pedidos, leer_mensaje, link_whatsapp, mensaje_cliente

MENSAJE_CATALOGO = """¡Hola! Vi su catálogo y quiero pedir:
• 2 × Mesa auxiliar con divisiones — S/ 190
• 1 × Espejo de mesa con orejitas (gato) (consultar precio)
*Total productos: S/ 190*
Nombre: Ana Torres
Entrega en: La Esperanza, Mz B Lt 4
¿Cuánto sería el delivery?"""


def nuevo(tmp_path, **extra):
    db = Pedidos(tmp_path)
    datos = {"cliente_nombre": "Ana Torres", "cliente_telefono": "987 654 321", "direccion": "Mz B Lt 4",
             "distrito": "La Esperanza", "delivery": 7,
             "items": [{"nombre": "Mesa auxiliar", "cantidad": 2, "precio": 95, "costo": 70}]}
    datos.update(extra)
    return db, db.crear(datos)


def test_leer_mensaje_del_catalogo():
    d = leer_mensaje(MENSAJE_CATALOGO)
    assert d["cliente_nombre"] == "Ana Torres"
    assert d["direccion"] == "La Esperanza, Mz B Lt 4"
    assert d["items"][0] == {"nombre": "Mesa auxiliar con divisiones", "cantidad": 2, "precio": 95.0, "costo": 0}
    assert d["items"][1]["nombre"] == "Espejo de mesa con orejitas (gato)" and d["items"][1]["precio"] == 0


def test_crear_calcula_totales_y_ganancia(tmp_path):
    _, p = nuevo(tmp_path)
    assert p["total_productos"] == 190 and p["costo_productos"] == 140
    assert p["ganancia"] == 50 and p["total_cliente"] == 197
    assert p["estado"] == "nuevo" and p["pago"] == "pendiente" and len(p["codigo"]) == 6


def test_crear_sin_productos_falla(tmp_path):
    with pytest.raises(ValueError):
        Pedidos(tmp_path).crear({"cliente_nombre": "x", "items": []})


def test_flujo_de_estados_y_historial(tmp_path):
    db, p = nuevo(tmp_path)
    for e in ["confirmado", "recogido", "en_camino", "entregado"]:
        p = db.cambiar_estado(p["id"], e)
    assert [h["estado"] for h in db.historial(p["id"])] == ["nuevo", "confirmado", "recogido", "en_camino", "entregado"]
    with pytest.raises(ValueError):  # un pedido entregado ya no cambia
        db.cambiar_estado(p["id"], "cancelado")


def test_resumen_del_dia_y_por_repasar(tmp_path):
    db, p = nuevo(tmp_path)
    db.cambiar_estado(p["id"], "entregado")
    _, otro = None, db.crear({"cliente_nombre": "Luis", "items": [{"nombre": "Zapatero", "cantidad": 1, "precio": 85, "costo": 60}]})
    db.cambiar_estado(otro["id"], "rechazado")
    dia = p["creado_en"][:10]
    r = db.resumen(dia)
    assert r["pedidos"] == 2 and r["entregados"] == 1 and r["rechazados"] == 1
    assert r["ventas"] == 190 and r["ganancia"] == 50 and r["por_repasar"] == 190
    db.actualizar(p["id"], {"pago": "repasado", "metodo_pago": "yape"})
    assert db.resumen(dia)["por_repasar"] == 0


def test_dataset_csv_sin_datos_personales(tmp_path):
    db, p = nuevo(tmp_path)
    db.cambiar_estado(p["id"], "rechazado")
    filas = list(csv.DictReader(io.StringIO(db.csv())))
    assert filas[0]["estado_final"] == "rechazado" and filas[0]["distrito"] == "La Esperanza"
    texto = db.csv()
    assert "987" not in texto and "Mz B" not in texto and "Ana" not in texto


def test_mensaje_y_link_whatsapp(tmp_path):
    _, p = nuevo(tmp_path)
    msg = mensaje_cliente(p, "en_camino", "S/")
    assert "Ana" in msg and "S/ 197" in msg and "Síguelo" not in msg
    assert "Síguelo aquí: https://x/?c=" in mensaje_cliente(p, "en_camino", "S/", "https://x/?c=")
    assert link_whatsapp("987 654 321", "hola").startswith("https://wa.me/51987654321?text=hola")
    assert link_whatsapp("", "hola") == ""
