import re, csv, json, time, os, random
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# CONFIGURACION
CSV_PATH, RESULTADOS_DIR = "formato(Sheet1).csv", "resultados_tt"
ESPERA_CAPTCHA_INICIAL = 30 

# UTILS
def save_json(data, filename):
    os.makedirs(RESULTADOS_DIR, exist_ok=True)
    ruta = os.path.join(RESULTADOS_DIR, f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return ruta

def pedir_rango_fechas():
    while True:
        try:
            f_i = datetime.strptime(input("Fecha inicio (YYYY-MM-DD): ").strip(), "%Y-%m-%d")
            f_f = datetime.strptime(input("Fecha fin (YYYY-MM-DD): ").strip(), "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            if f_f >= f_i: return f_i, f_f
        except ValueError: print("Formato inválido.")

def normalizar_fecha_tt(texto_fecha):
    ahora = datetime.now()
    t = texto_fecha.lower()
    try:
        # Referencia: Limpieza de caracteres basura en fechas de TikTok
        t = re.sub(r'[^a-z0-9\s-]', '', t)
        if "hace" in t or "h" in t or "d" in t or "m" in t:
            n = int(re.search(r'\d+', t).group())
            if "d" in t: return ahora - timedelta(days=n)
            if "h" in t: return ahora - timedelta(hours=n)
            if "m" in t: return ahora - timedelta(minutes=n)
        
        nums = re.findall(r'\d+', t)
        if len(nums) == 2: return datetime.strptime(f"{ahora.year}-{nums[0]}-{nums[1]}", "%Y-%m-%d")
        if len(nums) == 3: return datetime.strptime(f"{nums[0]}-{nums[1]}-{nums[2]}", "%Y-%m-%d")
    except: pass
    return ahora

# EXTRACTION LOGIC
def extraer_datos_robustos(driver, wait):
    res = {"tipo": "video", "caption": "Sin descripción", "likes": "0", "comments": "0"}
    
    # Referencia: Intento de cierre de modales de login que bloquean la vista
    try:
        webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
    except: pass

    # Referencia: Búsqueda de caption usando múltiples selectores e2e
    for selector in ["browse-caption", "video-desc", "browse-video-desc"]:
        try:
            el = driver.find_element(By.DATA_E2E, selector)
            if el.text: 
                res["caption"] = el.text.strip()
                break
        except: continue

    # Referencia: Búsqueda de métricas
    try:
        res["likes"] = driver.find_element(By.DATA_E2E, "like-count").text
        res["comments"] = driver.find_element(By.DATA_E2E, "comment-count").text
    except: pass

    return res

def procesar_perfil_publico(driver, item, f_i, f_f):
    print(f"\nAccediendo a: https://www.tiktok.com/@{item['usuario']}")
    driver.get(f"https://www.tiktok.com/@{item['usuario']}")
    
    print(f"--- ESPERA: Tienes {ESPERA_CAPTCHA_INICIAL}s para el Captcha ---")
    time.sleep(ESPERA_CAPTCHA_INICIAL)
    
    # Referencia: Scroll dinámico para despertar el lazy loading
    driver.execute_script("window.scrollTo(0, 600);")
    time.sleep(2)
    
    video_els = driver.find_elements(By.XPATH, "//div[@data-e2e='user-post-item-list']//a")
    links = list(set([el.get_attribute("href") for el in video_els]))
    
    print(f"Encontrados: {len(links)} publicaciones.")
    posts_data = []
    wait = WebDriverWait(driver, 15)

    for link in links:
        print(f"Analizando: {link}")
        driver.get(link)
        time.sleep(random.uniform(4, 6))
        
        try:
            # Referencia: Forzar carga moviendo el mouse a un area neutral
            webdriver.ActionChains(driver).move_by_offset(10, 10).perform()
            
            # Referencia: Selector de fecha universal (busca el texto que acompaña al nickname)
            # TikTok anonimo suele poner la fecha en un span dentro del contenedor de info
            wait.until(EC.presence_of_element_located((By.DATA_E2E, "browser-nickname")))
            
            # Busqueda de fecha por proximidad al nickname
            try:
                # Buscamos el elemento que contiene la fecha, suele ser el último span en el bloque de info
                f_el = driver.find_element(By.XPATH, "//span[contains(@class, 'SpanOtherInfos')]//span[last()]")
                txt_fecha = f_el.text
            except:
                # Fallback si el anterior falla
                f_el = driver.find_element(By.CSS_SELECTOR, "[data-e2e='browser-nickname'] + span")
                txt_fecha = f_el.text

            f_p = normalizar_fecha_tt(txt_fecha)
            
            if f_i <= f_p <= f_f:
                data = extraer_datos_robustos(driver, wait)
                if "/photo/" in link: data["tipo"] = "photo_mode"
                
                posts_data.append({"url": link, "fecha_iso": f_p.isoformat(), **data})
                print(f"   [OK] {f_p.date()} | {data['tipo']} | Likes: {data['likes']}")
            else:
                print(f"   [SALTADO] Fecha {f_p.date()} fuera de rango.")
                
        except Exception as e:
            # Referencia: Debug visual opcional en caso de fallo
            print(f"   [ERROR] No se detectó info del post.")
            continue

    res = {**item, "posts_data": posts_data}
    save_json(res, f"perfil_tt_{item['usuario']}")
    return res

def main():
    # Referencia: Seleccion de perfil para prueba (puedes cambiar el indice para rich.correa)
    usuarios_tt = []
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            u = row.get("tiktok", "").strip().replace("@", "")
            if u: usuarios_tt.append({"id": row.get("id"), "usuario": u})

    if not usuarios_tt: return
    f_i, f_f = pedir_rango_fechas()
    
    options = webdriver.ChromeOptions()
    # Referencia: Argumentos para parecer un usuario real y evitar el bloqueo anonimo
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    driver = webdriver.Chrome(options=options)
    
    try:
        # Cambia el indice [0] por [1] si quieres probar con rich.correa directamente
        for i in range(len(usuarios_tt)):
            procesar_perfil_publico(driver, usuarios_tt[i], f_i, f_f)
            print("-" * 30)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()