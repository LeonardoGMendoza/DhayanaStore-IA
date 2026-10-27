"""Agente Redator: transforma o texto do fornecedor num anúncio pronto para o Marketplace.

Regra de ouro (igual às Leis do Enxame): a IA só ESCREVE. O preço é calculado pelo código,
nunca pela IA, e a vendedora revisa antes de publicar.
"""
import json
import logging
import math
import re
import unicodedata

log = logging.getLogger("dhayana.redator")

CATEGORIAS = ["Hogar", "Belleza", "Tecnología", "Deporte", "Motos", "Cocina", "Niños", "Otros"]

PROMPT = """Eres el Redactor de "{tienda}", una tienda pequeña de {ciudad} (Perú) que vende por Facebook Marketplace y WhatsApp.
Recibes el texto que publicó el proveedor en su grupo y escribes el anuncio de la tienda, en español de Perú, cálido y claro.

Reglas:
- Usa SOLO las características que están en el texto del proveedor. NO inventes medidas, materiales, colores, garantía ni marca.
- NO menciones al proveedor, otra tienda, ni ningún precio (el precio lo pone el sistema).
- Título: el nombre del producto en MAYÚSCULAS, máximo 50 caracteres, sin emojis ni asteriscos.
- Descripción para Marketplace: 1 frase de gancho + de 3 a 6 viñetas que empiecen con "✅ " (una característica por viñeta) + 1 línea final que invite a escribir por WhatsApp. Separa cada parte con un salto de línea (\\n). Máximo 600 caracteres.
- Descripción corta para el catálogo web: 1 o 2 frases, máximo 180 caracteres, sin emojis.
- Categoría: exactamente una de {categorias}.

Texto del proveedor:
\"\"\"{texto}\"\"\"

Responde SOLO con un JSON válido, sin texto fuera de él:
{{"titulo": "...", "descripcion": "...", "descripcion_corta": "...", "categoria": "..."}}"""


def slug(texto):
    """'Espejo ovalado LED' -> 'espejo-ovalado-led' (sirve de id y nombre de la foto)."""
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return "-".join(t.split("-")[:5]) or "producto"


def precio_sugerido(costo, ganancia):
    """Costo + ganancia, redondeado hacia arriba a múltiplo de 5 (precios 'bonitos' tipo 85, 90, 95)."""
    if costo <= 0:
        return 0
    return int(math.ceil((costo + max(ganancia, 0)) / 5.0) * 5)


def formatear(desc):
    """Cada ✅ en su propia línea y la invitación final separada (la IA a veces lo junta todo)."""
    desc = re.sub(r"[ \t]+", " ", desc.replace("\\n", "\n")).strip()
    desc = re.sub(r"\s*✅\s*", "\n✅ ", desc).strip()
    partes = desc.rsplit("\n✅ ", 1)
    if len(partes) == 2:  # separa la frase final ("¡Escríbenos por WhatsApp!") de la última viñeta
        ultima = re.sub(r"([.!])\s+(?=[¡📲👉]|Escr|Pide|Haz|Cont|Pregunt)", r"\1\n", partes[1], count=1)
        desc = partes[0] + "\n✅ " + ultima
    return re.sub(r"\n{3,}", "\n\n", desc)


def interpretar(texto):
    """Extrae y valida el JSON que devolvió la IA."""
    bloco = re.search(r"\{.*\}", texto or "", re.S)
    if not bloco:
        raise ValueError("La IA no devolvió JSON")
    d = json.loads(bloco.group(0))
    titulo = re.sub(r"[*_]", "", str(d.get("titulo") or "")).strip().upper()[:60]
    descripcion = formatear(str(d.get("descripcion") or ""))
    corta = str(d.get("descripcion_corta") or "").strip()[:220]
    categoria = str(d.get("categoria") or "").strip()
    if categoria not in CATEGORIAS:
        categoria = "Otros"
    if not titulo or not descripcion:
        raise ValueError("Faltan título o descripción")
    return {"titulo": titulo, "descripcion": descripcion, "descripcion_corta": corta or descripcion[:180], "categoria": categoria}


class Redator:
    def __init__(self, chat, tienda="Dhayana Store", ciudad="Trujillo", moneda="S/"):
        self.chat, self.tienda, self.ciudad, self.moneda = chat, tienda, ciudad, moneda

    def escrever(self, texto, costo=0.0, ganancia=20.0):
        texto = (texto or "").strip()[:2500]
        if not texto:
            raise ValueError("Pega el texto del proveedor")
        if self.chat is None:
            raise RuntimeError("La IA todavía no está configurada (.env)")
        prompt = PROMPT.format(tienda=self.tienda, ciudad=self.ciudad, categorias=", ".join(CATEGORIAS), texto=texto)
        dados = interpretar(self.chat(prompt))
        precio = precio_sugerido(costo, ganancia)
        titulo_bonito = dados["titulo"].capitalize()
        precio_txt = f"{self.moneda} {precio}" if precio else ""
        dados.update({
            "id": slug(dados["titulo"]),
            "precio": precio,
            "costo": costo,
            "ganancia": precio - costo if precio else 0,
            # Texto listo para copiar en el Marketplace, con el mismo estilo que ella usa (*TÍTULO*)
            "anuncio": f"*{dados['titulo']}*\n" + (f"💰 {precio_txt}\n" if precio_txt else "") + f"\n{dados['descripcion']}",
            "nombre": titulo_bonito,
        })
        return dados
