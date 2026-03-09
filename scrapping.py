from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import time

driver = webdriver.Safari()
wait = WebDriverWait(driver, 15)

# Ir al login
driver.get("https://www.instagram.com/accounts/login/")
time.sleep(3)

# Llenar login
username_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
password_input = wait.until(EC.presence_of_element_located((By.NAME, "pass")))

username_input.send_keys("mindtrack_test")
password_input.send_keys("Prueba26")
password_input.send_keys(Keys.RETURN)

# Esperar a que entre
time.sleep(5)

# Cerrar ventana de guardar inicio de sesión
try:
    ahora_no = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//*[text()='Ahora no']"))
    )
    ahora_no.click()
    print("Se cerró la ventana de guardar inicio de sesión.")
except Exception as e:
    print("No apareció la ventana de guardar información:", e)

# Ir al perfil
driver.get("https://www.instagram.com/sweet_ricee/")
time.sleep(5)

# Scroll progresivo hasta que ya no cargue más
last_height = driver.execute_script("return document.body.scrollHeight")
intentos_sin_cambio = 0
max_intentos_sin_cambio = 3

while intentos_sin_cambio < max_intentos_sin_cambio:
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2.5)

    new_height = driver.execute_script("return document.body.scrollHeight")

    if new_height == last_height:
        intentos_sin_cambio += 1
    else:
        intentos_sin_cambio = 0
        last_height = new_height

print("Scroll terminado.")

# Guardar HTML con nombre único
html_content = driver.page_source
nombre_archivo = f"perfil_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

with open(nombre_archivo, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"HTML guardado en {nombre_archivo}")

# Mantener abierto para revisar
input("Presiona Enter para cerrar el navegador...")
driver.quit()