import re
import csv
import json
import time
import os
from datetime import datetime
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# CONFIG

CSV_PATH = "formato(Sheet1).csv"
RESULTADOS_DIR = "resultados_ig"
MAX_INTENTOS_SIN_CAMBIO = 3
ESPERA_LOGIN = 15
ESPERA_CAPTION = 4


# UTILIDADES

def asegurar_directorio_resultados():
    os.makedirs(RESULTADOS_DIR, exist_ok=True)


def limpiar_nombre_archivo(texto):
    if not texto:
        return "sin_nombre"
    texto = str(texto).strip()
    texto = re.sub(r'[\\/*?:"<>|]', "_", texto)
    texto = re.sub(r"\s+", "_", texto)
    return texto


def pedir_rango_fechas():
    print("\nIngresa el rango de fechas que quieres extraer.")
    print("Formato: YYYY-MM-DD")
    print("Ejemplo: 2024-01-01")

    while True:
        try:
            fecha_inicio_str = input("Fecha inicio: ").strip()
            fecha_fin_str = input("Fecha fin: ").strip()

            fecha_inicio = datetime.strptime(fecha_inicio_str, "%Y-%m-%d")
            fecha_fin = datetime.strptime(fecha_fin_str, "%Y-%m-%d")

            if fecha_fin < fecha_inicio:
                print("La fecha fin no puede ser menor que la fecha inicio.\n")
                continue

            fecha_fin = fecha_fin.replace(hour=23, minute=59, second=59)

            return fecha_inicio, fecha_fin

        except ValueError:
            print("Formato inválido. Usa YYYY-MM-DD.\n")


def obtener_fecha_post(driver):
    try:
        time_element = driver.find_element(By.TAG_NAME, "time")
        fecha_iso = time_element.get_attribute("datetime")

        if fecha_iso:
            fecha_iso = fecha_iso.replace("Z", "+00:00")
            fecha_dt = datetime.fromisoformat(fecha_iso)
            return fecha_dt.replace(tzinfo=None)
    except Exception:
        pass

    return None


def fecha_en_rango(fecha_post, fecha_inicio, fecha_fin):
    if fecha_post is None:
        return False
    return fecha_inicio <= fecha_post <= fecha_fin


def construir_resultado_anonimo(resultado):
    posts_anonimos = []

    for post in resultado.get("posts_data", []):
        posts_anonimos.append({
            "fecha_post_iso": post.get("fecha_post_iso"),
            "likes_text": post.get("likes_text"),
            "comments_text": post.get("comments_text"),
            "fecha_text": post.get("fecha_text"),
            "caption": post.get("caption")
        })

    data_anonima = {
        "id": resultado.get("id"),
        "paciente": str(resultado.get("id")) if resultado.get("id") is not None else None,
        "followers": resultado.get("followers"),
        "following": resultado.get("following"),
        "posts": resultado.get("posts"),
        "rango_fechas": resultado.get("rango_fechas"),
        "posts_data": posts_anonimos
    }

    if resultado.get("error"):
        data_anonima["error"] = resultado.get("error")

    return data_anonima


# LOGIN

def iniciar_sesion(driver, wait):
    driver.get("https://www.instagram.com/accounts/login/")
    time.sleep(3)

    username_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
    password_input = wait.until(EC.presence_of_element_located((By.NAME, "pass")))

    username_input.send_keys("mindtrack_test")
    password_input.send_keys("Prueba26")
    password_input.send_keys(Keys.RETURN)

    time.sleep(5)

    try:
        ahora_no = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//*[text()='Ahora no']"))
        )
        ahora_no.click()
        print("Se cerró la ventana de guardar inicio de sesión.")
    except Exception as e:
        print("No apareció la ventana de guardar información:", e)


# CSV

def limpiar_usuario_instagram(valor):
    if valor is None:
        return None

    valor = str(valor).strip()

    if not valor:
        return None

    valor = valor.replace("https://www.instagram.com/", "")
    valor = valor.replace("http://www.instagram.com/", "")
    valor = valor.replace("https://instagram.com/", "")
    valor = valor.replace("http://instagram.com/", "")
    valor = valor.strip()

    if valor.startswith("@"):
        valor = valor[1:]

    valor = valor.strip("/")

    if not valor:
        return None

    return valor


def cargar_usuarios_instagram_desde_csv(ruta_csv):
    usuarios = []

    with open(ruta_csv, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for fila in reader:
            usuario = limpiar_usuario_instagram(fila.get("instagram"))
            if usuario:
                usuarios.append({
                    "id": fila.get("id"),
                    "usuario": usuario,
                    "url": f"https://www.instagram.com/{usuario}/"
                })

    return usuarios


# SCROLL DEL PERFIL

def hacer_scroll_completo(driver):
    last_height = driver.execute_script("return document.body.scrollHeight")
    intentos_sin_cambio = 0

    while intentos_sin_cambio < MAX_INTENTOS_SIN_CAMBIO:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2.5)

        new_height = driver.execute_script("return document.body.scrollHeight")

        if new_height == last_height:
            intentos_sin_cambio += 1
        else:
            intentos_sin_cambio = 0
            last_height = new_height

    print("Scroll terminado.")


# GUARDAR HTML

def guardar_html_perfil(driver, username_csv=None):
    asegurar_directorio_resultados()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    username_seguro = limpiar_nombre_archivo(username_csv)

    if username_csv:
        nombre_archivo = f"perfil_{username_seguro}_{timestamp}.html"
    else:
        nombre_archivo = f"perfil_{timestamp}.html"

    ruta_archivo = os.path.join(RESULTADOS_DIR, nombre_archivo)
    html_content = driver.page_source

    with open(ruta_archivo, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"HTML guardado en {ruta_archivo}")
    return ruta_archivo


# PARSEAR HTML DEL PERFIL

def parsear_html_perfil(archivo_html):
    with open(archivo_html, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")

    og_title_tag = soup.find("meta", attrs={"property": "og:title"})
    og_desc_tag = soup.find("meta", attrs={"property": "og:description"})
    og_image_tag = soup.find("meta", attrs={"property": "og:image"})

    og_title = og_title_tag.get("content") if og_title_tag else None
    og_desc = og_desc_tag.get("content") if og_desc_tag else None
    og_image = og_image_tag.get("content") if og_image_tag else None

    username = None
    nombre = None
    followers = None
    following = None
    posts = None

    if og_title:
        m_title = re.search(
            r"^(.*?)\s+\(@(.*?)\)\s+•",
            og_title,
            re.IGNORECASE
        )
        if m_title:
            nombre = m_title.group(1).strip()
            username = m_title.group(2).strip()

    if og_desc:
        m_desc = re.search(
            r"([^,]+)\s+seguidores,\s+([^,]+)\s+seguidos,\s+([^,]+)\s+publicaciones",
            og_desc,
            re.IGNORECASE
        )
        if m_desc:
            followers = m_desc.group(1).strip()
            following = m_desc.group(2).strip()
            posts = m_desc.group(3).strip()

    links_posts = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/p/" in href or "/reel/" in href:
            if href.startswith("/"):
                href = "https://www.instagram.com" + href
            href = href.split("?")[0]
            if href not in links_posts:
                links_posts.append(href)

    return {
        "username": username,
        "nombre": nombre,
        "followers": followers,
        "following": following,
        "posts": posts,
        "profile_pic": og_image,
        "links_posts": links_posts
    }


# PROCESAR META DESCRIPTION

def procesar_meta_description(texto):
    if not texto:
        return {
            "likes_text": None,
            "comments_text": None,
            "username_post": None,
            "fecha_text": None,
            "caption": None,
            "caption_raw": texto
        }

    texto = re.sub(r"\s+", " ", texto).strip()

    resultado = {
        "likes_text": None,
        "comments_text": None,
        "username_post": None,
        "fecha_text": None,
        "caption": None,
        "caption_raw": texto
    }

    patron = re.search(
        r"^(.*?)\,\s*(.*?)\s*-\s*(.*?)\s+el\s+(.*?):\s*\"(.*?)\"\.?\s*$",
        texto,
        re.IGNORECASE
    )

    if patron:
        resultado["likes_text"] = patron.group(1).strip()
        resultado["comments_text"] = patron.group(2).strip()
        resultado["username_post"] = patron.group(3).strip()
        resultado["fecha_text"] = patron.group(4).strip()
        resultado["caption"] = patron.group(5).strip()
        return resultado

    patron2 = re.search(
        r"^(.*?)\,\s*(.*?)\s*-\s*(.*?)\s+el\s+(.*?):\s*\"?(.*?)\"?\s*$",
        texto,
        re.IGNORECASE
    )

    if patron2:
        resultado["likes_text"] = patron2.group(1).strip()
        resultado["comments_text"] = patron2.group(2).strip()
        resultado["username_post"] = patron2.group(3).strip()
        resultado["fecha_text"] = patron2.group(4).strip()
        resultado["caption"] = patron2.group(5).strip().rstrip(".")
        return resultado

    m_caption = re.search(r'"(.*?)"', texto)
    if m_caption:
        resultado["caption"] = m_caption.group(1).strip()

    return resultado


# EXTRAER CAPTION DESDE POST

def extraer_caption_desde_post(driver):
    candidatos = []

    xpaths = [
        "//article//h1",
        "//article//ul//span",
        "//article//div//span",
    ]

    for xpath in xpaths:
        try:
            elementos = driver.find_elements(By.XPATH, xpath)
            for el in elementos:
                texto = el.text.strip()
                if texto and texto not in candidatos:
                    candidatos.append(texto)
        except Exception:
            pass

    candidatos_filtrados = []
    for texto in candidatos:
        texto_limpio = re.sub(r"\s+", " ", texto).strip()
        if len(texto_limpio) >= 15 and texto_limpio not in candidatos_filtrados:
            candidatos_filtrados.append(texto_limpio)

    if candidatos_filtrados:
        return {
            "likes_text": None,
            "comments_text": None,
            "username_post": None,
            "fecha_text": None,
            "caption": candidatos_filtrados[0],
            "caption_raw": candidatos_filtrados[0]
        }

    try:
        meta_desc = driver.find_element(By.XPATH, "//meta[@property='og:description']")
        texto_meta = meta_desc.get_attribute("content")
        return procesar_meta_description(texto_meta)
    except Exception:
        return {
            "likes_text": None,
            "comments_text": None,
            "username_post": None,
            "fecha_text": None,
            "caption": None,
            "caption_raw": None
        }


# VISITAR POSTS Y SACAR DATOS

def extraer_captions(driver, links_posts, fecha_inicio=None, fecha_fin=None):
    posts_con_caption = []

    for i, link in enumerate(links_posts, start=1):
        print(f"\n[{i}/{len(links_posts)}] Procesando: {link}")
        driver.get(link)
        time.sleep(ESPERA_CAPTION)

        fecha_post_dt = obtener_fecha_post(driver)

        if fecha_inicio and fecha_fin:
            if not fecha_en_rango(fecha_post_dt, fecha_inicio, fecha_fin):
                print(f"Post fuera de rango: {fecha_post_dt}")
                continue

        datos_post = extraer_caption_desde_post(driver)

        posts_con_caption.append({
            "url": link,
            "fecha_post_iso": fecha_post_dt.isoformat() if fecha_post_dt else None,
            "likes_text": datos_post["likes_text"],
            "comments_text": datos_post["comments_text"],
            "username_post": datos_post["username_post"],
            "fecha_text": datos_post["fecha_text"],
            "caption": datos_post["caption"],
            "caption_raw": datos_post["caption_raw"]
        })

        print("FECHA ISO:", fecha_post_dt.isoformat() if fecha_post_dt else None)
        print("CAPTION:", datos_post["caption"])
        print("FECHA TEXTO:", datos_post["fecha_text"])
        print("LIKES:", datos_post["likes_text"])
        print("COMMENTS:", datos_post["comments_text"])

    return posts_con_caption


# GUARDAR JSON FINAL

def guardar_resultado_final(data, username_csv=None):
    asegurar_directorio_resultados()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    username_seguro = limpiar_nombre_archivo(username_csv)

    if username_csv:
        nombre_json = f"perfil_y_captions_{username_seguro}_{timestamp}.json"
    else:
        nombre_json = f"perfil_y_captions_{timestamp}.json"

    ruta_json = os.path.join(RESULTADOS_DIR, nombre_json)

    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nResultados guardados en {ruta_json}")
    return ruta_json


def guardar_resultados_globales(resultados_totales, fecha_inicio, fecha_fin):
    asegurar_directorio_resultados()

    nombre_json_global = f"resultados_instagram_todos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    ruta_json_global = os.path.join(RESULTADOS_DIR, nombre_json_global)

    data_global = {
        "rango_fechas": {
            "inicio": fecha_inicio.strftime("%Y-%m-%d"),
            "fin": fecha_fin.strftime("%Y-%m-%d")
        },
        "resultados": resultados_totales
    }

    with open(ruta_json_global, "w", encoding="utf-8") as f:
        json.dump(data_global, f, ensure_ascii=False, indent=2)

    print(f"\nResultados globales guardados en {ruta_json_global}")
    return ruta_json_global


def guardar_resultados_globales_anonimos(resultados_totales, fecha_inicio, fecha_fin):
    asegurar_directorio_resultados()

    nombre_json_global = f"resultados_instagram_todos_anonimo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    ruta_json_global = os.path.join(RESULTADOS_DIR, nombre_json_global)

    resultados_anonimos = [construir_resultado_anonimo(r) for r in resultados_totales]

    data_global_anonimo = {
        "rango_fechas": {
            "inicio": fecha_inicio.strftime("%Y-%m-%d"),
            "fin": fecha_fin.strftime("%Y-%m-%d")
        },
        "resultados": resultados_anonimos
    }

    with open(ruta_json_global, "w", encoding="utf-8") as f:
        json.dump(data_global_anonimo, f, ensure_ascii=False, indent=2)

    print(f"\nResultados globales anónimos guardados en {ruta_json_global}")
    return ruta_json_global


# PROCESAR PERFIL

def procesar_perfil(driver, item, fecha_inicio, fecha_fin):
    perfil_url = item["url"]
    username_csv = item["usuario"]

    print("\n" + "=" * 60)
    print(f"Procesando perfil: {username_csv}")
    print(f"URL: {perfil_url}")
    print(f"Rango: {fecha_inicio.strftime('%Y-%m-%d')} a {fecha_fin.strftime('%Y-%m-%d')}")
    print("=" * 60)

    driver.get(perfil_url)
    time.sleep(5)

    hacer_scroll_completo(driver)

    archivo_html = guardar_html_perfil(driver, username_csv=username_csv)
    info_perfil = parsear_html_perfil(archivo_html)

    posts_con_caption = extraer_captions(
        driver,
        info_perfil["links_posts"],
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin
    )

    resultado_final = {
        "id": item["id"],
        "username_csv": username_csv,
        "url": perfil_url,
        "username": info_perfil["username"],
        "nombre": info_perfil["nombre"],
        "followers": info_perfil["followers"],
        "following": info_perfil["following"],
        "posts": info_perfil["posts"],
        "profile_pic": info_perfil["profile_pic"],
        "rango_fechas": {
            "inicio": fecha_inicio.strftime("%Y-%m-%d"),
            "fin": fecha_fin.strftime("%Y-%m-%d")
        },
        "posts_data": posts_con_caption
    }

    print("\n" + "=" * 60)
    print("PERFIL EXTRAÍDO")
    print("=" * 60)
    print("ID:", resultado_final["id"])
    print("USERNAME CSV:", resultado_final["username_csv"])
    print("URL:", resultado_final["url"])
    print("USERNAME:", resultado_final["username"])
    print("NOMBRE:", resultado_final["nombre"])
    print("FOLLOWERS:", resultado_final["followers"])
    print("FOLLOWING:", resultado_final["following"])
    print("POSTS:", resultado_final["posts"])
    print("PROFILE PIC:", resultado_final["profile_pic"])
    print("POSTS EN RANGO:", len(resultado_final["posts_data"]))

    for item_post in resultado_final["posts_data"]:
        print("-" * 60)
        print("LINK:", item_post["url"])
        print("FECHA ISO:", item_post["fecha_post_iso"])
        print("CAPTION:", item_post["caption"])
        print("FECHA:", item_post["fecha_text"])
        print("LIKES:", item_post["likes_text"])
        print("COMMENTS:", item_post["comments_text"])

    guardar_resultado_final(resultado_final, username_csv=username_csv)

    return resultado_final


# MAIN

def main():
    asegurar_directorio_resultados()

    usuarios = cargar_usuarios_instagram_desde_csv(CSV_PATH)

    if not usuarios:
        print("No se encontraron usuarios en la columna 'instagram'.")
        return

    fecha_inicio, fecha_fin = pedir_rango_fechas()

    print(f"\nUsuarios encontrados en CSV: {len(usuarios)}")
    print(f"Rango seleccionado: {fecha_inicio.strftime('%Y-%m-%d')} a {fecha_fin.strftime('%Y-%m-%d')}")
    for item in usuarios:
        print(f"- ID={item['id']} | usuario={item['usuario']} | url={item['url']}")

    driver = webdriver.Safari()
    wait = WebDriverWait(driver, ESPERA_LOGIN)

    resultados_totales = []

    try:
        iniciar_sesion(driver, wait)

        for item in usuarios:
            try:
                resultado = procesar_perfil(driver, item, fecha_inicio, fecha_fin)
                resultados_totales.append(resultado)
            except Exception as e:
                print(f"\nError procesando {item['usuario']}: {e}")
                resultados_totales.append({
                    "id": item["id"],
                    "username_csv": item["usuario"],
                    "url": item["url"],
                    "username": None,
                    "nombre": None,
                    "followers": None,
                    "following": None,
                    "posts": None,
                    "profile_pic": None,
                    "rango_fechas": {
                        "inicio": fecha_inicio.strftime("%Y-%m-%d"),
                        "fin": fecha_fin.strftime("%Y-%m-%d")
                    },
                    "posts_data": [],
                    "error": str(e)
                })

        guardar_resultados_globales(resultados_totales, fecha_inicio, fecha_fin)
        guardar_resultados_globales_anonimos(resultados_totales, fecha_inicio, fecha_fin)

        input("\nPresiona Enter para cerrar el navegador...")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()