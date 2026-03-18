import re
import json
import time
from datetime import datetime
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# CONFIG

PERFIL_URL = "https://www.instagram.com/sweet_ricee/"
MAX_INTENTOS_SIN_CAMBIO = 3
ESPERA_LOGIN = 15
ESPERA_CAPTION = 4


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

def guardar_html_perfil(driver):
    html_content = driver.page_source
    nombre_archivo = f"perfil_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

    with open(nombre_archivo, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"HTML guardado en {nombre_archivo}")
    return nombre_archivo


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
            r"(\d+)\s+seguidores,\s+(\d+)\s+seguidos,\s+(\d+)\s+publicaciones",
            og_desc,
            re.IGNORECASE
        )
        if m_desc:
            followers = m_desc.group(1)
            following = m_desc.group(2)
            posts = m_desc.group(3)

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

def extraer_captions(driver, links_posts):
    posts_con_caption = []

    for i, link in enumerate(links_posts, start=1):
        print(f"\n[{i}/{len(links_posts)}] Procesando: {link}")
        driver.get(link)
        time.sleep(ESPERA_CAPTION)

        datos_post = extraer_caption_desde_post(driver)

        posts_con_caption.append({
            "url": link,
            "likes_text": datos_post["likes_text"],
            "comments_text": datos_post["comments_text"],
            "username_post": datos_post["username_post"],
            "fecha_text": datos_post["fecha_text"],
            "caption": datos_post["caption"],
            "caption_raw": datos_post["caption_raw"]
        })

        print("CAPTION:", datos_post["caption"])
        print("FECHA:", datos_post["fecha_text"])
        print("LIKES:", datos_post["likes_text"])
        print("COMMENTS:", datos_post["comments_text"])

    return posts_con_caption


# GUARDAR JSON FINAL

def guardar_resultado_final(data):
    nombre_json = f"perfil_y_captions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(nombre_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nResultados guardados en {nombre_json}")
    return nombre_json


# MAIN

def main():
    driver = webdriver.Safari()
    wait = WebDriverWait(driver, ESPERA_LOGIN)

    try:
        iniciar_sesion(driver, wait)

        driver.get(PERFIL_URL)
        time.sleep(5)

        hacer_scroll_completo(driver)

        archivo_html = guardar_html_perfil(driver)

        info_perfil = parsear_html_perfil(archivo_html)

        posts_con_caption = extraer_captions(driver, info_perfil["links_posts"])

        resultado_final = {
            "username": info_perfil["username"],
            "nombre": info_perfil["nombre"],
            "followers": info_perfil["followers"],
            "following": info_perfil["following"],
            "posts": info_perfil["posts"],
            "profile_pic": info_perfil["profile_pic"],
            "posts_data": posts_con_caption
        }

        print("\n" + "=" * 60)
        print("PERFIL EXTRAÍDO")
        print("=" * 60)
        print("USERNAME:", resultado_final["username"])
        print("NOMBRE:", resultado_final["nombre"])
        print("FOLLOWERS:", resultado_final["followers"])
        print("FOLLOWING:", resultado_final["following"])
        print("POSTS:", resultado_final["posts"])
        print("PROFILE PIC:", resultado_final["profile_pic"])

        print("\nPOST LINKS ENCONTRADOS:", len(info_perfil["links_posts"]))
        for item in resultado_final["posts_data"]:
            print("-" * 60)
            print("LINK:", item["url"])
            print("CAPTION:", item["caption"])
            print("FECHA:", item["fecha_text"])
            print("LIKES:", item["likes_text"])
            print("COMMENTS:", item["comments_text"])

        guardar_resultado_final(resultado_final)

        input("\nPresiona Enter para cerrar el navegador...")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()