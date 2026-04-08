import re, csv, json, time, os
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# CONFIG
CSV_PATH, RESULTADOS_DIR = "formato(Sheet1).csv", "resultados_ig"
MAX_INTENTOS_SIN_CAMBIO, ESPERA_LOGIN, ESPERA_CAPTION = 3, 15, 4

# UTILIDADES
def save_json(data, filename):
    os.makedirs(RESULTADOS_DIR, exist_ok=True)
    ruta = os.path.join(RESULTADOS_DIR, f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Guardado: {ruta}")
    return ruta

def limpiar_nombre_archivo(t):
    return re.sub(r'[\\/*?:"<>|\s]', "_", str(t).strip()) if t else "sin_nombre"

def obtener_fecha_post(driver):
    try:
        f_iso = driver.find_element(By.TAG_NAME, "time").get_attribute("datetime")
        return datetime.fromisoformat(f_iso.replace("Z", "+00:00")).replace(tzinfo=None) if f_iso else None
    except: return None

def construir_resultado_anonimo(res):
    return {
        "id": res.get("id"), "paciente": str(res.get("id")),
        "followers": res.get("followers"), "following": res.get("following"),
        "posts": res.get("posts"), "rango_fechas": res.get("rango_fechas"),
        "posts_data": [{k: p.get(k) for k in ["fecha_post_iso", "likes_text", "comments_text", "fecha_text", "caption"]} for p in res.get("posts_data", [])],
        **({"error": res["error"]} if "error" in res else {})
    }

# LOGIN / CSV
def iniciar_sesion(driver, wait):
    driver.get("https://www.instagram.com/accounts/login/")
    wait.until(EC.presence_of_element_located((By.NAME, "email"))).send_keys("mindtrack_test")
    pw = wait.until(EC.presence_of_element_located((By.NAME, "pass")))
    pw.send_keys("Prueba26" + Keys.RETURN)
    time.sleep(5)
    try: wait.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='Ahora no']"))).click()
    except: pass

def limpiar_usuario(v):
    if not v: return None
    v = re.sub(r'https?://(www\.)?instagram\.com/|@', '', str(v).strip()).strip('/')
    return v if v else None

def cargar_usuarios(ruta):
    usuarios = []
    with open(ruta, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            u = limpiar_usuario(r.get("instagram"))
            if not u: continue
            
            try:
                f_i = datetime.strptime(r.get("F. Inicio", "").strip(), "%Y-%m-%d")
                f_f = datetime.strptime(r.get("F. Fin", "").strip(), "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                
                usuarios.append({
                    "id": r.get("id"), 
                    "usuario": u, 
                    "url": f"https://www.instagram.com/{u}/",
                    "f_inicio": f_i,
                    "f_fin": f_f
                })
            except:
                print(f"Error en formato de fecha para usuario: {u}")
    return usuarios

# SCRAPING LOGIC
def hacer_scroll(driver):
    last_h, attempts = driver.execute_script("return document.body.scrollHeight"), 0
    while attempts < MAX_INTENTOS_SIN_CAMBIO:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2.5)
        new_h = driver.execute_script("return document.body.scrollHeight")
        attempts, last_h = (attempts + 1, new_h) if new_h == last_h else (0, new_h)

def parsear_html_perfil(html_path):
    with open(html_path, "r", encoding="utf-8") as f: soup = BeautifulSoup(f.read(), "html.parser")
    get_meta = lambda p: (tag.get("content") if (tag := soup.find("meta", attrs={"property": p})) else None)
    title, desc = get_meta("og:title"), get_meta("og:description")
    
    m_t = re.search(r"^(.*?)\s+\(@(.*?)\)", title) if title else None
    m_d = re.search(r"([^,]+) seguidores, ([^,]+) seguidos, ([^,]+) pub", desc) if desc else None
    
    links = list(set("https://www.instagram.com" + a["href"].split("?")[0] if a["href"].startswith("/") else a["href"].split("?")[0]
                 for a in soup.find_all("a", href=True) if "/p/" in a["href"] or "/reel/" in a["href"]))
    
    return {
        "username": m_t.group(2) if m_t else None, "nombre": m_t.group(1) if m_t else None,
        "followers": m_d.group(1) if m_d else None, "following": m_d.group(2) if m_d else None,
        "posts": m_d.group(3) if m_d else None, "profile_pic": get_meta("og:image"), "links_posts": links
    }

def extraer_caption_post(driver):
    for xpath in ["//article//h1", "//article//ul//span", "//article//div//span"]:
        try:
            texts = [el.text.strip() for el in driver.find_elements(By.XPATH, xpath) if len(el.text.strip()) >= 15]
            if texts: return {k: (texts[0] if k in ["caption", "caption_raw"] else None) for k in ["likes_text", "comments_text", "username_post", "fecha_text", "caption", "caption_raw"]}
        except: pass
    
    try:
        desc = driver.find_element(By.XPATH, "//meta[@property='og:description']").get_attribute("content")
        m = re.search(r"^(.*?),\s*(.*?)\s*-\s*(.*?)\s+el\s+(.*?):\s*\"?(.*?)\"?\.?\s*$", re.sub(r"\s+", " ", desc))
        return {
            "likes_text": m.group(1) if m else None, "comments_text": m.group(2) if m else None,
            "username_post": m.group(3) if m else None, "fecha_text": m.group(4) if m else None,
            "caption": m.group(5) if m else re.search(r'"(.*?)"', desc).group(1) if re.search(r'"(.*?)"', desc) else None,
            "caption_raw": desc
        }
    except: return {k: None for k in ["likes_text", "comments_text", "username_post", "fecha_text", "caption", "caption_raw"]}

def procesar_perfil(driver, item):
    f_i, f_f = item["f_inicio"], item["f_fin"]
    print(f"\nProcesando: {item['usuario']} (Rango: {f_i.date()} a {f_f.date()})")
    
    driver.get(item["url"])
    time.sleep(5)
    hacer_scroll(driver)
    
    h_path = os.path.join(RESULTADOS_DIR, f"perfil_{limpiar_nombre_archivo(item['usuario'])}_{datetime.now().strftime('%H%M%S')}.html")
    os.makedirs(RESULTADOS_DIR, exist_ok=True)
    with open(h_path, "w", encoding="utf-8") as f: f.write(driver.page_source)
    
    info = parsear_html_perfil(h_path)
    posts_data = []
    for i, link in enumerate(info["links_posts"], 1):
        driver.get(link)
        time.sleep(ESPERA_CAPTION)
        f_p = obtener_fecha_post(driver)
        if f_p and f_i <= f_p <= f_f:
            cap = extraer_caption_post(driver)
            posts_data.append({"url": link, "fecha_post_iso": f_p.isoformat(), **cap})
            print(f"[{i}] Post capturado: {f_p.date()}")
        else: print(f"[{i}] Fuera de rango u omitido.")

    res = {
        **item, 
        **info, 
        "rango_fechas": {"inicio": f_i.strftime("%Y-%m-%d"), "fin": f_f.strftime("%Y-%m-%d")}, 
        "posts_data": posts_data,
        "f_inicio": f_i.isoformat(), 
        "f_fin": f_f.isoformat()
    }
    save_json(res, f"perfil_{limpiar_nombre_archivo(item['usuario'])}")
    return res

def main():
    usuarios = cargar_usuarios(CSV_PATH)
    if not usuarios: return print("No hay usuarios.")
    
    driver = webdriver.Chrome() 
    wait = WebDriverWait(driver, ESPERA_LOGIN)
    resultados_totales = []
    
    try:
        iniciar_sesion(driver, wait)
        for item in usuarios:
            try: resultados_totales.append(procesar_perfil(driver, item))
            except Exception as e:
                print(f"Error en {item['usuario']}: {e}")
                resultados_totales.append({**item, "error": str(e), "posts_data": []})
        
        # Guardados finales
        save_json({"resultados": resultados_totales}, "global")
        save_json({"resultados": [construir_resultado_anonimo(r) for r in resultados_totales]}, "global_anonimo")
        input("Terminado. Enter para cerrar...")
    finally: driver.quit()

if __name__ == "__main__": main()