import re
import csv
import json
import html
import time
import os
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# CONFIGURACIÓN GENERAL
CSV_PATH = "formato(Sheet1).csv"
RESULTADOS_DIR = "resultados_fb"
ESPERA_LOGIN = 20
MAX_INTENTOS_SIN_CAMBIO = 4
SCROLL_PAUSA = 2.5

# HELPERS
def limpiar_texto(texto):
    if not texto: return None
    return re.sub(r"\s+", " ", texto).strip()

def guardar_html_debug(driver, usuario):
    os.makedirs(RESULTADOS_DIR, exist_ok=True)
    nombre = os.path.join(RESULTADOS_DIR, f"fb_debug_{usuario}_{datetime.now().strftime('%H%M%S')}.html")
    with open(nombre, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    return nombre

def guardar_resultado_final(data, filename):
    os.makedirs(RESULTADOS_DIR, exist_ok=True)
    ruta = os.path.join(RESULTADOS_DIR, f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Guardado: {ruta}")
    return ruta

# LÓGICA DE ANONIMIZACIÓN
def construir_resultado_anonimo(res):
    mapa_anonimos = {}
    contador_anon = 1
    
    res_anonimo = res.copy()
    posts_anonimizados = []

    for p in res.get("posts_data", []):
        comentarios_originales = p.get("comments", [])
        comentarios_anonimos = []

        for c in comentarios_originales:
            user_real = c.get("usuario_real")
            if user_real not in mapa_anonimos:
                mapa_anonimos[user_real] = f"Anónimo {contador_anon}"
                contador_anon += 1
            
            comentarios_anonimos.append({
                "usuario": mapa_anonimos[user_real],
                "texto": c.get("texto")
            })

        p_anon = p.copy()
        p_anon["comments"] = comentarios_anonimos
        posts_anonimizados.append(p_anon)

    res_anonimo["posts_data"] = posts_anonimizados
    return res_anonimo

# CSV / CARGA DE USUARIOS
def limpiar_usuario(v):
    if not v: return None
    v = re.sub(r'https?://(www\.)?facebook\.com/', '', str(v).strip()).strip('/')
    return v if v else None

def cargar_usuarios(ruta):
    usuarios = []
    with open(ruta, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            # Ahora leemos la columna 'facebook'
            u = limpiar_usuario(r.get("facebook"))
            if not u: continue # Si está vacío (como loop_itc o senado.gda), lo saltamos
            
            try:
                f_i = datetime.strptime(r.get("F. Inicio", "").strip(), "%Y-%m-%d")
                f_f = datetime.strptime(r.get("F. Fin", "").strip(), "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                
                usuarios.append({
                    "id": r.get("id"), 
                    "paciente": str(r.get("id")),
                    "usuario": u, 
                    "url": f"https://www.facebook.com/{u}",
                    "f_inicio": f_i,
                    "f_fin": f_f
                })
            except Exception as e:
                print(f"Error en formato de fecha para usuario: {u}. Detalles: {e}")
    return usuarios

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
        "Ahora no", "Not Now", "Aceptar",
        "Allow essential and optional cookies",
        "Permitir solo las cookies esenciales",
    ]

    for texto in posibles_botones:
        try:
            boton = driver.find_element(By.XPATH, f"//*[text()='{texto}']")
            boton.click()
            time.sleep(2)
            break
        except Exception:
            pass

# NAVEGACIÓN Y SCROLL
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

# EXTRACCIÓN DESDE HTML/JSON DE FACEBOOK
def extraer_info_desde_html(html_text, item):
    slug = item["usuario"]
    resultado = {
        **item,
        "username": slug,
        "nombre": None,
        "friends_text": None,
        "profile_pic": None,
        "profile_description": None,
        "rango_fechas": {"inicio": item["f_inicio"].strftime("%Y-%m-%d"), "fin": item["f_fin"].strftime("%Y-%m-%d")},
        "posts_data": []
    }
    
    # Limpiamos los objetos datetime para que el JSON final sea serializable
    resultado.pop("f_inicio")
    resultado.pop("f_fin")

    texto = html.unescape(html_text)

    # Extracción dinámica del nombre real del usuario en FB
    m_name = re.search(r'"__isProfile":"User","name":"([^"]+)"', texto)
    if not m_name: m_name = re.search(r'"title":"([^"]+)"', texto)
    if m_name: resultado["nombre"] = m_name.group(1)

    m_pic = re.search(r'"profilePic(?:160|Small|Medium)?":\{"uri":"(https:\\/\\/[^"]+)"\}', texto)
    if m_pic: resultado["profile_pic"] = m_pic.group(1).replace("\\/", "/")

    m_friends = re.search(r'"profile_social_context".*?"text":"([^"]*amigo[^"]*)"', texto)
    if m_friends: resultado["friends_text"] = m_friends.group(1)

    m_desc = re.search(r'"profile_owner_bio_text":"([^"]+)"', texto)
    if m_desc:
        resultado["profile_description"] = m_desc.group(1)
    else:
        m_desc2 = re.search(r'"mentions_tab_tooltip_nux_text":"([^"]+)"', texto)
        if m_desc2: resultado["profile_description"] = m_desc2.group(1)

    # Búsqueda dinámica de URLs de posts usando el slug del usuario
    patron_urls = r'https:\\/\\/www\.facebook\.com\\/' + re.escape(slug) + r'\\/posts\\/[^"&]+'
    urls_raw = re.findall(patron_urls, texto)
    
    urls = []
    vistos = set()
    for u in urls_raw:
        u = u.replace("\\/", "/").split("&__")[0].split("?__")[0]
        if u not in vistos:
            vistos.add(u)
            urls.append(u)

    mensajes_raw = re.findall(r'"message":\{"(?:[^{}]*?)"text":"([^"]+)"', texto)
    mensajes = []
    vistos_msg = set()
    for msg in mensajes_raw:
        try: msg = msg.encode("utf-8").decode("unicode_escape")
        except Exception: pass

        msg = limpiar_texto(msg)
        if not msg: continue

        low = msg.lower()
        # Filtros de UI
        if any(x in low for x in ["escribe algo a", "consulta lo que sus amigos", "personas que quizá conozcas", "suggested for you"]):
            continue

        if msg not in vistos_msg:
            vistos_msg.add(msg)
            mensajes.append(msg)

    total = min(len(urls), len(mensajes))
    nombre_autor = resultado["nombre"] or slug

    for i in range(total):
        resultado["posts_data"].append({
            "url": urls[i],
            "autor_detectado": nombre_autor,
            "fecha_text": None,
            "caption": mensajes[i],
            "caption_raw": mensajes[i],
            "comments": [] 
        })

    if not resultado["posts_data"] and urls:
        for u in urls:
            resultado["posts_data"].append({
                "url": u, "autor_detectado": nombre_autor, "fecha_text": None,
                "caption": None, "caption_raw": None, "comments": []
            })

    return resultado

# POSTS VISIBLES DESDE DOM
def extraer_posts_visibles_desde_dom(driver, nombre_perfil):
    posts = []
    vistos = set()
    articulos = driver.find_elements(By.XPATH, "//div[@role='article']")

    for articulo in articulos:
        try:
            texto_completo = limpiar_texto(articulo.text)
            if not texto_completo: continue

            lineas = [limpiar_texto(x) for x in articulo.text.split("\n") if limpiar_texto(x)]
            if len(lineas) < 2: continue

            autor, caption, fecha_text = None, None, None
            comentarios_extraidos = []

            for linea in lineas[:4]:
                if linea and len(linea) <= 80:
                    autor = linea
                    break

            for linea in lineas[:8]:
                low = linea.lower()
                if re.search(r"\b(\d+\s*min|\d+\s*h|ayer|justo ahora|ahora)\b", low):
                    fecha_text = linea
                    break

            basura_post = {"me gusta", "comentar", "compartir", "escribe un comentario...", "publicaciones", "filtros", "enviar"}
            zona_comentarios = False
            user_temp = None

            for linea in lineas:
                low = linea.lower()
                
                if low in ["comentar", "escribe un comentario...", "ver más comentarios"]:
                    zona_comentarios = True
                    continue

                if zona_comentarios:
                    if low in ["me gusta", "responder", "compartir", "ocultar", "ver traducción", "editado", "top fan", "fan destacado"] or re.match(r"^\d+\s+(h|min|d|sem)$", low):
                        continue
                    
                    if not user_temp:
                        user_temp = linea
                    else:
                        comentarios_extraidos.append({
                            "usuario_real": user_temp,
                            "texto": linea
                        })
                        user_temp = None
                else:
                    if linea == autor or (fecha_text and linea == fecha_text) or low in basura_post:
                        continue
                    if any(x in low for x in ["me gusta", "comentar", "compartir", "escribe un comentario"]):
                        continue
                    if len(linea) >= 8 and not caption:
                        caption = linea

            url_post = None
            enlaces = articulo.find_elements(By.XPATH, ".//a[@href]")
            for a in enlaces:
                href = a.get_attribute("href")
                if href and "/posts/" in href and "facebook.com" in href:
                    url_post = href.split("&__")[0].split("?__")[0]
                    break

            clave = (autor, caption)
            if not caption or clave in vistos: continue
            vistos.add(clave)

            # Verificación flexible del autor para evitar saltar posts por diferencias de mayúsculas o tildes
            if autor and nombre_perfil and nombre_perfil.lower() not in autor.lower(): 
                continue

            posts.append({
                "url": url_post,
                "autor_detectado": autor,
                "fecha_text": fecha_text,
                "caption": caption,
                "caption_raw": texto_completo,
                "comments": comentarios_extraidos
            })

        except Exception:
            continue

    return posts

# COMBINAR POSTS
def combinar_posts(posts_html, posts_dom):
    combinados = []
    vistos = set()

    for post in posts_dom + posts_html:
        clave = ((post.get("url") or "").strip(), (post.get("caption") or "").strip().lower())
        if clave in vistos: continue
        vistos.add(clave)
        combinados.append(post)

    return combinados

# MAIN
def main():
    usuarios = cargar_usuarios(CSV_PATH)
    if not usuarios: 
        print("No hay perfiles de Facebook para procesar en el CSV.")
        return

    driver = webdriver.Chrome() 
    wait = WebDriverWait(driver, ESPERA_LOGIN)
    resultados_totales = []

    try:
        iniciar_sesion(driver, wait)

        for item in usuarios:
            print(f"\nProcesando FB: {item['usuario']} (Rango: {item['f_inicio'].date()} a {item['f_fin'].date()})")
            try:
                driver.get(item["url"])
                time.sleep(6)
                hacer_scroll_completo(driver)

                archivo_html = guardar_html_debug(driver, item["usuario"])

                with open(archivo_html, "r", encoding="utf-8") as f:
                    html_text = f.read()

                resultado_base = extraer_info_desde_html(html_text, item)
                posts_dom = extraer_posts_visibles_desde_dom(driver, resultado_base.get("nombre"))
                
                resultado_base["posts_data"] = combinar_posts(resultado_base["posts_data"], posts_dom)
                resultados_totales.append(resultado_base)

            except Exception as e:
                print(f"Error procesando a {item['usuario']}: {e}")
                resultados_totales.append({**item, "error": str(e), "posts_data": []})

        # Generar versión anónima global
        resultados_anonimos = [construir_resultado_anonimo(r) for r in resultados_totales]

        # Guardar en la misma estructura global que Instagram
        guardar_resultado_final({"resultados": resultados_totales}, "fb_global")
        guardar_resultado_final({"resultados": resultados_anonimos}, "fb_global_anonimo")

        input("\nTerminado. Presiona Enter para cerrar el navegador...")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()