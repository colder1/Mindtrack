from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Inicializa el navegador Safari
driver = webdriver.Safari()

# Abre la página de inicio de sesión de Instagram
driver.get('https://www.instagram.com/accounts/login/')

# Espera explícita: espera hasta que el campo de nombre de usuario esté presente
wait = WebDriverWait(driver, 10)  # Espera hasta 10 segundos

# Encuentra los campos de nombre de usuario y contraseña de manera más robusta
username_input = wait.until(EC.presence_of_element_located((By.NAME, 'email')))  # Cambié 'username' a 'email'
password_input = wait.until(EC.presence_of_element_located((By.NAME, 'pass')))  # Cambié 'password' a 'pass'

# Escribe tus credenciales (reemplaza con tus datos)
username_input.send_keys('')  # Cambia esto por tu usuario
password_input.send_keys('')  # Cambia esto por tu contraseña

# Envía el formulario para iniciar sesión
password_input.send_keys(Keys.RETURN)

# Espera unos segundos para asegurarte de que el inicio de sesión sea exitoso
time.sleep(5)

# Cerrar ventana emergente de "guardar información de inicio de sesión"
try:
    # Esperar y encontrar el botón para cerrar la ventana emergente de "guardar información"
    save_info_button = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Guardar información')]")))
    save_info_button.click()
    print("Ventana emergente cerrada exitosamente.")
except:
    print("No apareció la ventana emergente de guardar información.")

# Si la página de inicio de sesión se cierra, ahora deberías estar en tu página de inicio o perfil
print("Inicio de sesión exitoso!")

# Aquí podrías seguir con el scraping del perfil

# Opcional: Cierra el navegador
# driver.quit()