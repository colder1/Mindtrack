import re, csv, json, time, os, random, html
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURACIÓN ---
CSV_PATH = "formato(Sheet1).csv"
FOLDER_NAME = "resultados_facebook"
MAX_SCROLLS = 10  # Aumentado para asegurar que cargue suficientes posts

def pausa_humana(min_s=2, max_s=4):
    time.sleep(random.uniform(min_s, max_s))

def parse_fb_date(date_text):
    """Convierte formatos complejos de FB (ej: '17 de marzo a las 9:39 p. m.') a datetime."""
    if not date_text: return None
    now = datetime.now()
    # Limpiar caracteres especiales y normalizar
    t = date_text.lower().replace(' a las', '').replace('.', '').strip()
    
    try:
        # 1. Relativos (2 h, ayer, etc.)
        if any(x in t for x in ['min', 'h', 'ahora', 'justo']): return now
        if 'ayer' in t: return now - timedelta(days=1)
        
        # 2. Formato: '17 de marzo' o '17 de marzo de 2024'
        meses = {
            'enero':1, 'febrero':2, 'marzo':3, 'abril':4, 'mayo':5, 'junio':6, 
            'julio':7, 'agosto':8, 'septiembre':9, 'octubre':10, 'noviembre':11, 'diciembre':12
        }
        
        # Extraer números y palabras
        parts = re.findall(r'\d+|[a-z]+', t)
        if len(parts) >= 2:
            dia = int(parts[0])
            mes_str = next((m for m in meses if m in t), None)
            if not mes_str: return None
            mes = meses[mes_str]
            
            # Si tiene año (ej: de 2024), lo usamos. Si no, asumimos el año actual.
            anio = now.year
            for p in parts:
                if len(p) == 4 and p.isdigit():
                    anio = int(p)
                    break
            
            return datetime(anio, mes, dia)
    except Exception as e:
        pass
    return None

def iniciar_sesion_con_pausa(driver, wait):
    driver.get("https://www.facebook.com/")
    pausa_humana(2, 3)
    print("\n[1/3] Introduciendo credenciales...")
    try:
        wait.until(EC.presence_of_element_located((By.NAME, "email"))).send_keys("mindtrack_test@outlook.com")
        wait.until(EC.presence_of_element_located((By.NAME, "pass"))).send_keys("Prueba26" + Keys.RETURN)
    except:
        print("[!] No se pudo meter login automático, hazlo manual.")
    
    print("\n[!] PASO MANUAL: Resuelve Captcha/2FA en Chrome.")
    input(">>> PRESIONA ENTER AQUÍ CUANDO YA ESTÉS EN EL INICIO DE FACEBOOK <<<")

def extraer_info_perfil_completa(driver, slug, f_inicio, f_fin):
    # Usamos execute_script para limpiar el texto de caracteres invisibles como \u00a0
    source = driver.execute_script("return document.body.innerText")
    source_html = html.unescape(driver.page_source)
    
    info = {"amigos": "0", "bio": "Sin biografía", "posts_data": []}

    # Extraer Amigos y Bio con Regex mejorado
    m_friends = re.search(r'(\d+[\d\.,]*)\s+(?:mil\s+)?amigos', source)
    if m_friends: info["amigos"] = m_friends.group(0).replace('\u00a0', ' ')
    
    m_desc = re.search(r'"profile_owner_bio_text":"([^"]+)"', source_html)
    if m_desc: info["bio"] = m_desc.group(1)

    # Buscar posts
    articulos = driver.find_elements(By.XPATH, "//div[@role='article']")
    vistos = set()

    for art in articulos:
        try:
            # Facebook separa la fecha a veces en un span específico
            texto_post = art.text
            lineas = [l.strip() for l in texto_post.split("\n") if len(l.strip()) > 1]
            
            # Buscamos una línea que parezca fecha (contenga meses o indicadores de tiempo)
            fecha_dt = None
            for l in lineas[:10]:
                dt = parse_fb_date(l)
                if dt:
                    fecha_dt = dt
                    break
            
            if fecha_dt and f_inicio <= fecha_dt <= f_fin:
                # El caption suele ser la parte más larga del post
                caption = max(lineas[1:15], key=len) if len(lineas) > 1 else "Sin texto"
                
                if caption not in vistos and len(caption) > 5:
                    vistos.add(caption)
                    info["posts_data"].append({
                        "fecha": fecha_dt.strftime("%Y-%m-%d"),
                        "caption": caption
                    })
        except: continue
    return info

def main():
    os.makedirs(FOLDER_NAME, exist_ok=True)
    print("\n--- CONFIGURACIÓN DE RANGO DE FECHAS ---")
    f_inicio_str = input("Fecha de INICIO [AAAA-MM-DD]: ") or "2024-01-01"
    f_fin_str = input("Fecha de FIN [AAAA-MM-DD]: ") or datetime.now().strftime("%Y-%m-%d")
    
    f_inicio = datetime.strptime(f_inicio_str, "%Y-%m-%d")
    f_fin = datetime.strptime(f_fin_str, "%Y-%m-%d")

    options = Options()
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 20)
    
    try:
        iniciar_sesion_con_pausa(driver, wait)

        with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
            usuarios = list(csv.DictReader(f))

        for row in usuarios:
            user_input = row.get("facebook")
            if not user_input or user_input == "": continue
            slug = re.sub(r'https?://(www\.)?facebook\.com/|@', '', user_input).strip('/')
            
            print(f"\n--- Analizando: {slug} ---")
            driver.get(f"https://www.facebook.com/{slug}/")
            pausa_humana(5, 8)
            
            # Scroll agresivo para que FB suelte las fechas largas
            for _ in range(MAX_SCROLLS):
                driver.execute_script("window.scrollBy(0, 1000);")
                time.sleep(1.5)

            datos = extraer_info_perfil_completa(driver, slug, f_inicio, f_fin)
            
            resultado = {
                "id_paciente": row.get("id"),
                "usuario_facebook": slug,
                "bio": datos["bio"],
                "numero_amigos": datos["amigos"],
                "total_posts_encontrados": len(datos["posts_data"]),
                "posts": datos["posts_data"]
            }
            
            with open(os.path.join(FOLDER_NAME, f"fb_{slug}.json"), "w", encoding="utf-8") as out:
                json.dump(resultado, out, ensure_ascii=False, indent=2)
            
            print(f"Hecho. Amigos: {datos['amigos']} | Posts en rango: {len(datos['posts_data'])}")
            pausa_humana(5, 10)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()