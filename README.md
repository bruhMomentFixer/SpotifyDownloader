# 🎵 Spotify Downloader Pro (SDPro)

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/bruhMomentFixer/SpotifyDownloader?style=social)](https://github.com/bruhMomentFixer/SpotifyDownloader)

> **Descarga música de Spotify de forma fácil y organizada.** Un script Python avanzado que sincroniza playlists, descarga canciones individuales y mantiene tus metadatos ID3 actualizados. ¡Compatible con spotdl y yt-dlp para máxima fiabilidad!

<!-- ![Demo](https://via.placeholder.com/800x400?text=Demo+del+Programa)  Reemplaza con una imagen real si tienes -->

## 📋 Tabla de Contenidos

- [✨ Características](#-características)
- [🔧 Requisitos](#-requisitos)
- [🚀 Instalación](#-instalación)
- [⚙️ Configuración](#️-configuración)
- [📖 Uso](#-uso)
- [🎯 Ejemplos](#-ejemplos)
- [🔍 Solución de Problemas](#-solución-de-problemas)
- [🤝 Contribución](#-contribución)
- [📄 Licencia](#-licencia)

## ✨ Características

- 🎶 **Descarga individual**: Canciones, playlists o álbumes desde URLs de Spotify.
- 🔄 **Sincronización automática**: Mantén tu carpeta local sincronizada con playlists de Spotify.
- 🏷️ **Metadatos ID3**: Actualiza automáticamente números de pista, ISRC y URLs de Spotify.
- 🎚️ **Múltiples fuentes**: Usa spotdl o yt-dlp como respaldo para descargas fallidas.
- 📁 **Organización**: Crea carpetas automáticamente basadas en el nombre de la playlist.
- 🔍 **Detección inteligente**: Encuentra archivos existentes y evita duplicados.
- 🌐 **Soporte multiidioma**: Maneja acentos, símbolos y caracteres especiales.
- ⚡ **Rápido y eficiente**: Optimizado para grandes playlists.

## 🔧 Requisitos

- **Python**: Versión 3.8 o superior.
- **Librerías**: `spotipy`, `mutagen`, `yt-dlp`, `spotdl`.
- **Cuenta de Spotify**: Necesaria para acceder a la API (gratuita).
- **Sistema operativo**: Windows, macOS o Linux.

## 🚀 Instalación

### 1. Clona el repositorio
```bash
git clone https://github.com/yourusername/SpotifyDownloader.git
cd SpotifyDownloader
```

### 2. Instala Python
Descarga e instala Python desde [python.org](https://www.python.org/downloads/).

### 3. Instala las dependencias
```bash
pip install spotipy mutagen yt-dlp spotdl
```

### 4. Actualiza las librerías (opcional)
Ejecuta la opción 5 del programa para actualizar spotdl y yt-dlp automáticamente.

## ⚙️ Configuración

### Credenciales de Spotify
El programa requiere credenciales de Spotify para acceder a la API. **Se recomienda encarecidamente obtener tus propias credenciales** para evitar límites de uso y asegurar compatibilidad.

#### Cómo obtener tus credenciales:
1. Ve a [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Crea una nueva aplicación.
3. Copia el `Client ID` y `Client Secret`.
4. Crea un archivo `spotify_client_data.txt` en la misma carpeta que `SDPro.py`:
   ```
   TU_CLIENT_ID_AQUI
   TU_CLIENT_SECRET_AQUI
   ```

#### Opciones de credenciales en el programa:
Cuando ejecutes cualquier función que requiera Spotify, el programa te pedirá elegir:
- **Opción 1**: Usar credenciales del archivo `spotify_client_data.txt` (recomendado)
- **Opción 2**: Usar credenciales por defecto de spotdl (limitado, no recomendado)
- **Opción 3**: Ingresar credenciales manualmente

### Configuración inicial
Ejecuta el programa y selecciona la opción de credenciales. El programa te guiará.

## 📖 Uso

### Ejecutar el programa
```bash
python SDPro.py
```

### Menú principal
```
==================================================
🎵 SPOTIFY DOWNLOADER
==================================================
1. Descargar una canción individual
2. Descargar múltiples canciones desde archivo
3. Exportar playlist a archivo
4. Sincronizar playlist local con Spotify
5. Comprobar y actualizar librerías
6. Salir

Elige una opción (1, 2, 3, 4, 5 o 6):
```

## 🎯 Ejemplos

### 1. Descargar una canción individual
```
Elige una opción: 1
Introduce la URL de la canción de Spotify: https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC
```
Resultado: Descarga "Blinding Lights" de The Weeknd en la carpeta ".\downloads" (crea una si no existe o crea una nueva ".\downloads0" si existe una con contenido).

### 2. Descargar múltiples canciones desde archivo
```
Elige una opción: 2
```
Resultado: Lee el archivo 'songs-to-download.txt' y descarga todas las canciones listadas, guardando en la carpeta ".\downloads".

### 3. Exportar playlist a archivo
```
Elige una opción: 3
Introduce la URL de la playlist: https://open.spotify.com/playlist/4JrjRdPrU8SPl7YzG9KGPQ
```
Resultado: Crea automáticamente el archivo 'songs-to-download.txt' con todas las URLs de la playlist.

### 4. Sincronizar playlist local con Spotify
```
Elige una opción: 4
Introduce la URL de la playlist: https://open.spotify.com/playlist/4JrjRdPrU8SPl7YzG9KGPQ
Introduce la ruta de la carpeta local: C:\Music\Chill EDM
```
Resultado: Sincroniza la playlist, descarga faltantes y actualiza metadatos.

### 5. Comprobar y actualizar librerías
```
Elige una opción: 5
```
Resultado: Actualiza spotdl y yt-dlp a las versiones más recientes.

## 🔍 Solución de Problemas

### Error de autenticación
- Verifica que `spotify_client_data.txt` tenga las credenciales correctas.
- Asegúrate de que la aplicación de Spotify esté en modo "Development".

### Descargas fallidas
- El programa usa spotdl primero, luego yt-dlp como respaldo.
- Si falla, verifica tu conexión a internet y que las URLs sean válidas.

### Problemas con metadatos
- Asegúrate de que los archivos MP3 no estén bloqueados.
- Usa un editor de metadatos como Mp3tag para verificar.

### Playlist no sincroniza correctamente
- Verifica que la carpeta local tenga permisos de escritura.
- Si hay duplicados, el programa prioriza por número de pista (TRCK).

### Comandos comunes
```bash
# Ver logs detallados (redirigir salida a archivo)
python SDPro.py > log.txt

# El programa es interactivo y no requiere argumentos adicionales
# Todas las configuraciones se hacen desde el menú
```

## 🤝 Contribución

¡Las contribuciones son bienvenidas! Para contribuir:

1. Fork el proyecto.
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`).
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`).
4. Push a la rama (`git push origin feature/AmazingFeature`).
5. Abre un Pull Request.

### Guías de contribución
- Sigue el estilo de código PEP 8.
- Agrega tests para nuevas funcionalidades.
- Actualiza la documentación.

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo [LICENSE](LICENSE) para más detalles.

---

**⚠️ Nota importante**: Este programa es para uso personal y educativo. Respeta los derechos de autor y las leyes de tu país al descargar música. No promueve la piratería.

**Disclaimer**: Todo el código de este proyecto ha sido generado utilizando inteligencia artificial. Se recomienda revisar y probar el código antes de usarlo en producción.

¡Disfruta descargando tu música favorita! 🎶

Si te gusta el proyecto, ¡dale una ⭐ en GitHub!
