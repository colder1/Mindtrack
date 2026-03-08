from bs4 import BeautifulSoup
import json

# Ruta al archivo HTML
archivo_html = '/Users/marcialbecerrarodriguez/Documents/TEC/MindTrack/profile2.html'  # Cambia esto por la ruta de tu archivo HTML

# Leer el contenido del archivo HTML
with open(archivo_html, 'r', encoding='utf-8') as file:
    html_content = file.read()

# Usar BeautifulSoup para parsear el HTML
soup = BeautifulSoup(html_content, 'html.parser')

# Extraer el JSON incrustado en el HTML
json_data = soup.find('script', type='text/javascript', text=lambda t: t and 'window._sharedData' in t).text
json_data = json_data.split('= ', 1)[1][:-1]  # Limpiar el contenido para obtener el JSON puro

# Convertir el JSON a un diccionario de Python
data = json.loads(json_data)

# Acceder a los datos del perfil
user_info = data['entry_data']['ProfilePage'][0]['graphql']['user']

# Extraer información del perfil
username = user_info['username']
followers = user_info['edge_followed_by']['count']
following = user_info['edge_follow']['count']
posts = user_info['edge_owner_to_timeline_media']['count']

# Mostrar la información extraída
print(f"Usuario: {username}")
print(f"Seguidores: {followers}")
print(f"Siguiendo: {following}")
print(f"Publicaciones: {posts}")
