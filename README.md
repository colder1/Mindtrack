# MindTrack - Instagram Scraper

Herramienta de automatización para la extracción de publicaciones y comentarios de Instagram dentro de rangos de fechas específicos.

## Requisitos
- Python 3
- Google Chrome y ChromeDriver
- Dependencias:
  ```bash
  pip install selenium beautifulsoup4
  ```

## Configuración de Entrada
El archivo `formato(Sheet1).csv` debe contener las siguientes columnas:
- **id**: Identificador único.
- **instagram**: Nombre de usuario o URL del perfil.
- **F. Inicio**: Fecha de inicio (AAAA-MM-DD).
- **F. Fin**: Fecha de fin (AAAA-MM-DD).

## Procesos Principales
1. **Autenticación**: Inicio de sesión automático mediante Selenium.
2. **Escaneo**: Scroll en el perfil para recopilar enlaces de posts y reels.
3. **Filtrado**: Validación de la fecha de cada publicación según el rango del CSV.
4. **Limpieza**: Uso de expresiones regulares para eliminar ruido de la interfaz (botones de respuesta, marcas de tiempo, contadores de likes y captions duplicados).

## Salida de Datos
Los resultados se guardan en la carpeta `resultados_ig/`:
- **JSON por perfil**: Datos detallados de cada usuario.
- **Global**: Resumen de toda la ejecución.
- **Anónimo**: Versión filtrada para análisis de datos.