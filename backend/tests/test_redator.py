import json

import pytest

from app.redator import Redator, interpretar, precio_sugerido, slug

TEXTO_MESA = """MESA AUXILIAR CON DIVISIONES
⚡ Práctica, elegante y multifuncional
⚡ Altura ajustable. 2 divisiones. 4 ruedas giratorias
⚡ Medidas: Tablero 60 x 40 cm
⚡ PRECIO: 70 SOLES"""


def ia_falsa(resposta):
    prompts = []

    def chat(prompt):
        prompts.append(prompt)
        return resposta
    chat.prompts = prompts
    return chat


RESPOSTA_OK = "Claro:\n" + json.dumps({
    "titulo": "*Mesa auxiliar con divisiones*",
    "descripcion": "Tu espacio más ordenado.\n✅ Altura ajustable\n✅ 4 ruedas\nEscríbenos por WhatsApp",
    "descripcion_corta": "Mesa con altura ajustable y ruedas.",
    "categoria": "Hogar",
})


def test_precio_redondea_a_multiplo_de_5():
    assert precio_sugerido(70, 20) == 90
    assert precio_sugerido(70, 23) == 95
    assert precio_sugerido(0, 20) == 0


def test_slug():
    assert slug("ESPEJO OVALADO CON LUZ LED TÁCTIL") == "espejo-ovalado-con-luz-led"


def test_interpretar_limpia_titulo_y_categoria():
    d = interpretar(json.dumps({"titulo": "*zapatero*", "descripcion": "x", "categoria": "Inventada"}))
    assert d["titulo"] == "ZAPATERO"
    assert d["categoria"] == "Otros"


def test_interpretar_sin_json_falla():
    with pytest.raises(ValueError):
        interpretar("no sé")


def test_redator_calcula_precio_y_no_lo_pide_a_la_ia():
    chat = ia_falsa(RESPOSTA_OK)
    d = Redator(chat).escrever(TEXTO_MESA, costo=70, ganancia=25)
    assert d["precio"] == 95 and d["ganancia"] == 25
    assert d["id"] == "mesa-auxiliar-con-divisiones"
    assert d["anuncio"].startswith("*MESA AUXILIAR CON DIVISIONES*\n💰 S/ 95")
    assert "NO menciones al proveedor" in chat.prompts[0]


def test_redator_sin_ia():
    with pytest.raises(RuntimeError):
        Redator(None).escrever(TEXTO_MESA)
