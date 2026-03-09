import re
import json
from bs4 import BeautifulSoup

ARCHIVO = "perfil_20260308_205248.html"
PERFIL_OBJETIVO = "sweet_ricee"

with open(ARCHIVO, "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")


def limpiar_texto(txt):
    if not txt:
        return None
    return " ".join(txt.split())


def extraer_meta(prop=None, name=None):
    if prop:
        tag = soup.find("meta", attrs={"property": prop})
    else:
        tag = soup.find("meta", attrs={"name": name})
    return tag.get("content") if tag else None


def buscar_jsons_embebidos(html_text):
    patrones = [
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        r'<script[^>]*>\s*window\.__additionalDataLoaded\s*\((.*?)\)\s*;\s*</script>',
        r'<script[^>]*>\s*window\._sharedData\s*=\s*(.*?);\s*</script>',
    ]
    resultados = []
    for patron in patrones:
        encontrados = re.findall(patron, html_text, re.DOTALL)
        resultados.extend(encontrados)
    return resultados


def extraer_links_posts():
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/p/" in href or "/reel/" in href:
            if href.startswith("/"):
                href = "https://www.instagram.com" + href
            links.add(href)
    return sorted(links)


def extraer_fragmento_alrededor(texto, objetivo, antes=1200, despues=2500):
    idx = texto.find(objetivo)
    if idx == -1:
        return None
    inicio = max(0, idx - antes)
    fin = min(len(texto), idx + despues)
    return texto[inicio:fin]


print("=" * 60)
print("METADATOS GENERALES")
print("=" * 60)

og_title = extraer_meta(prop="og:title")
og_desc = extraer_meta(prop="og:description")
og_image = extraer_meta(prop="og:image")
description = extraer_meta(name="description")
title = soup.title.string if soup.title else None

print("TITLE:", limpiar_texto(title))
print("OG TITLE:", og_title)
print("OG DESCRIPTION:", og_desc)
print("META DESCRIPTION:", description)
print("OG IMAGE:", og_image)

print("\n" + "=" * 60)
print("BÚSQUEDA DEL PERFIL OBJETIVO")
print("=" * 60)

if PERFIL_OBJETIVO in html:
    print(f"Sí aparece el perfil objetivo: {PERFIL_OBJETIVO}")
else:
    print(f"No aparece el perfil objetivo: {PERFIL_OBJETIVO}")

fragmento = extraer_fragmento_alrededor(html, PERFIL_OBJETIVO)
if fragmento:
    print("\nFRAGMENTO ALREDEDOR DEL PERFIL OBJETIVO:\n")
    print(fragmento[:3500])
else:
    print("\nNo se pudo sacar fragmento del perfil objetivo.")


print("\n" + "=" * 60)
print("INTENTO DE EXTRAER DATOS DESDE OG TAGS")
print("=" * 60)

username = None
nombre = None
followers = None
following = None
posts = None

# Sacar nombre y username desde og:title
if og_title:
    m_title = re.search(
        r'^(.*?)\s+\(@(.*?)\)\s+•',
        og_title,
        re.IGNORECASE
    )
    if m_title:
        nombre = m_title.group(1).strip()
        username = m_title.group(2).strip()

# Sacar followers/following/posts desde og:description
if og_desc:
    m_desc = re.search(
        r'(\d+)\s+seguidores,\s+(\d+)\s+seguidos,\s+(\d+)\s+publicaciones',
        og_desc,
        re.IGNORECASE
    )
    if m_desc:
        followers = m_desc.group(1)
        following = m_desc.group(2)
        posts = m_desc.group(3)

        print("USERNAME:", username)
        print("NOMBRE:", nombre)
        print("FOLLOWERS:", followers)
        print("FOLLOWING:", following)
        print("POSTS:", posts)

    else:
        print("No se pudo parsear og:description con el patrón en español.")
        print("Contenido:", og_desc)
else:
    print("No existe og:description.")

print("\n" + "=" * 60)
print("LINKS DE POSTS/REELS EN EL HTML")
print("=" * 60)

links_posts = extraer_links_posts()
if links_posts:
    for link in links_posts:
        print(link)
else:
    print("No se encontraron links de posts o reels en el HTML.")

print("\n" + "=" * 60)
print("SCRIPTS/JSON EMBEBIDOS")
print("=" * 60)

jsons = buscar_jsons_embebidos(html)
print("Cantidad de bloques potenciales encontrados:", len(jsons))

for i, bloque in enumerate(jsons[:5], start=1):
    print(f"\n--- BLOQUE {i} ---\n")
    print(bloque[:2000])

print("\n" + "=" * 60)
print("BÚSQUEDA DE PALABRAS CLAVE")
print("=" * 60)

palabras = [
    PERFIL_OBJETIVO,
    "followers",
    "following",
    "profile_pic_url",
    "full_name",
    "biography",
    "edge_owner_to_timeline_media",
    "is_private",
    "og:image",
]

for p in palabras:
    print(f"{p}: {'Sí' if p in html else 'No'}")