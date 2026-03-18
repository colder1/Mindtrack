import re
import json
import html
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# CONFIG

PERFIL_URL = "https://www.facebook.com/otis.mermil"
PERFIL_SLUG = "otis.mermil"
ESPERA_LOGIN = 20
MAX_INTENTOS_SIN_CAMBIO = 4
SCROLL_PAUSA = 2.5


# HELPERS

def limpiar_texto(texto):
    if not texto:
        return None
    return re.sub(r"\s+", " ", texto).strip()


def guardar_html_debug(driver):
    nombre = f"facebook_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(nombre, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print("HTML debug guardado en", nombre)
    return nombre


def guardar_resultado_final(data):
    nombre_json = f"facebook_perfil_y_posts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(nombre_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nResultados guardados en {nombre_json}")
    return nombre_json


# LOGIN

def iniciar_sesion(driver, wait):
    driver.get("https://www.facebook.com/")
    time.sleep(3)

    email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
    pass_input = wait.until(EC.presence_of_element_located((By.NAME, "pass")))

    email_input.send_keys("mindtrack_test@outlook.com")
    pass_input.send_keys("Prueba26")
    pass_input.send_keys(Keys.RETURN)

    time.sleep(6)

    posibles_botones = [
        "Ahora no",
        "Not Now",
        "Aceptar",
        "Allow essential and optional cookies",
        "Permitir solo las cookies esenciales",
    ]

    for texto in posibles_botones:
        try:
            boton = driver.find_element(By.XPATH, f"//*[text()='{texto}']")
            boton.click()
            time.sleep(2)
            print(f"Se cerró popup: {texto}")
            break
        except Exception:
            pass


# ABRIR PERFIL Y SCROLL

def abrir_perfil(driver):
    driver.get(PERFIL_URL)
    time.sleep(6)
    print("URL actual:", driver.current_url)


def hacer_scroll_completo(driver):
    last_height = driver.execute_script("return document.body.scrollHeight")
    intentos_sin_cambio = 0

    while intentos_sin_cambio < MAX_INTENTOS_SIN_CAMBIO:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSA)

        new_height = driver.execute_script("return document.body.scrollHeight")

        if new_height == last_height:
            intentos_sin_cambio += 1
        else:
            intentos_sin_cambio = 0
            last_height = new_height

    print("Scroll terminado.")


# EXTRACCIÓN DESDE HTML/JSON DE FACEBOOK

def extraer_info_desde_html(html_text):
    resultado = {
        "username": PERFIL_SLUG,
        "nombre": None,
        "friends_text": None,
        "profile_pic": None,
        "profile_description": None,
        "posts_data": []
    }

    texto = html.unescape(html_text)

    # PERFIL
    if '"name":"Otis Mermil"' in texto:
        resultado["nombre"] = "Otis Mermil"

    m_pic = re.search(
        r'"profilePic(?:160|Small|Medium)?":\{"uri":"(https:\\/\\/[^"]+)"\}',
        texto
    )
    if m_pic:
        resultado["profile_pic"] = m_pic.group(1).replace("\\/", "/")

    m_friends = re.search(
        r'"profile_social_context".*?"text":"([^"]*amigo[^"]*)"',
        texto
    )
    if m_friends:
        resultado["friends_text"] = m_friends.group(1)

    m_desc = re.search(r'"profile_owner_bio_text":"([^"]+)"', texto)
    if m_desc:
        resultado["profile_description"] = m_desc.group(1)
    else:
        m_desc2 = re.search(r'"mentions_tab_tooltip_nux_text":"([^"]+)"', texto)
        if m_desc2:
            resultado["profile_description"] = m_desc2.group(1)

    # URLS DE POSTS
    urls_raw = re.findall(
        r'https:\\/\\/www\.facebook\.com\\/otis\.mermil\\/posts\\/[^"&]+',
        texto
    )

    urls = []
    vistos = set()
    for u in urls_raw:
        u = u.replace("\\/", "/")
        u = u.split("&__")[0]
        u = u.split("?__")[0]
        if u not in vistos:
            vistos.add(u)
            urls.append(u)

    # MENSAJES DE POSTS
    mensajes_raw = re.findall(
        r'"message":\{"(?:[^{}]*?)"text":"([^"]+)"',
        texto
    )

    mensajes = []
    vistos_msg = set()
    for msg in mensajes_raw:
        try:
            msg = msg.encode("utf-8").decode("unicode_escape")
        except Exception:
            pass

        msg = limpiar_texto(msg)
        if not msg:
            continue

        low = msg.lower()
        if any(x in low for x in [
            "escribe algo a otis",
            "consulta lo que sus amigos",
            "personas que quizá conozcas",
            "suggested for you"
        ]):
            continue

        if msg not in vistos_msg:
            vistos_msg.add(msg)
            mensajes.append(msg)

    total = min(len(urls), len(mensajes))

    for i in range(total):
        resultado["posts_data"].append({
            "url": urls[i],
            "autor_detectado": "Otis Mermil",
            "fecha_text": None,
            "caption": mensajes[i],
            "caption_raw": mensajes[i]
        })

    if not resultado["posts_data"] and urls:
        for u in urls:
            resultado["posts_data"].append({
                "url": u,
                "autor_detectado": "Otis Mermil",
                "fecha_text": None,
                "caption": None,
                "caption_raw": None
            })

    return resultado


# POSTS VISIBLES DESDE DOM

def extraer_posts_visibles_desde_dom(driver):
    posts = []
    vistos = set()

    articulos = driver.find_elements(By.XPATH, "//div[@role='article']")
    print("Artículos visibles encontrados:", len(articulos))

    for articulo in articulos:
        try:
            texto_completo = limpiar_texto(articulo.text)
            if not texto_completo:
                continue

            lineas = [limpiar_texto(x) for x in articulo.text.split("\n") if limpiar_texto(x)]
            if len(lineas) < 2:
                continue

            autor = None
            caption = None
            fecha_text = None

            for linea in lineas[:4]:
                if linea and len(linea) <= 80:
                    autor = linea
                    break

            for linea in lineas[:8]:
                low = linea.lower()
                if re.search(r"\b(\d+\s*min|\d+\s*h|ayer|justo ahora|ahora)\b", low):
                    fecha_text = linea
                    break

            basura = {
                "me gusta", "comentar", "compartir", "escribe un comentario...",
                "publicaciones", "filtros"
            }

            for linea in lineas:
                low = linea.lower()
                if linea == autor:
                    continue
                if fecha_text and linea == fecha_text:
                    continue
                if low in basura:
                    continue
                if any(x in low for x in ["me gusta", "comentar", "compartir", "escribe un comentario"]):
                    continue
                if len(linea) >= 8:
                    caption = linea
                    break

            url_post = None
            enlaces = articulo.find_elements(By.XPATH, ".//a[@href]")
            for a in enlaces:
                href = a.get_attribute("href")
                if href and "/posts/" in href and "facebook.com" in href:
                    url_post = href.split("&__")[0].split("?__")[0]
                    break

            clave = (autor, caption)
            if not caption or clave in vistos:
                continue

            vistos.add(clave)

            if autor and "otis mermil" not in autor.lower():
                continue

            posts.append({
                "url": url_post,
                "autor_detectado": autor,
                "fecha_text": fecha_text,
                "caption": caption,
                "caption_raw": texto_completo
            })

        except Exception:
            continue

    return posts


# COMBINAR POSTS

def combinar_posts(posts_html, posts_dom):
    combinados = []
    vistos = set()

    for post in posts_html + posts_dom:
        clave = (
            (post.get("url") or "").strip(),
            (post.get("caption") or "").strip().lower()
        )

        if clave in vistos:
            continue
        vistos.add(clave)
        combinados.append(post)

    return combinados


# MAIN

def main():
    driver = webdriver.Safari()
    wait = WebDriverWait(driver, ESPERA_LOGIN)

    try:
        iniciar_sesion(driver, wait)
        abrir_perfil(driver)
        hacer_scroll_completo(driver)

        archivo_html = guardar_html_debug(driver)

        with open(archivo_html, "r", encoding="utf-8") as f:
            html_text = f.read()

        resultado = extraer_info_desde_html(html_text)

        posts_dom = extraer_posts_visibles_desde_dom(driver)
        resultado["posts_data"] = combinar_posts(resultado["posts_data"], posts_dom)

        print("\n" + "=" * 60)
        print("PERFIL EXTRAÍDO")
        print("=" * 60)
        print(json.dumps(resultado, ensure_ascii=False, indent=2))

        guardar_resultado_final(resultado)

        input("\nPresiona Enter para cerrar el navegador...")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()