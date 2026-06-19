# 🎵 Spotify Playlist Synchronization Tool (SpotPSync Tool)

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-PolyForm%20Noncommercial-blue.svg)](LICENSE)

🌐 Idioma: [English](README.md) | Español

> Herramienta en Python para gestionar playlists de Spotify, sincronizar carpetas locales de música y mantener la consistencia de metadatos ID3.

> El programa soporta español e inglés. Puedes seleccionar el idioma de la interfaz al iniciar la herramienta.

## 📋 Tabla de Contenidos

- [✨ Características](#-características)
- [🔧 Requisitos](#-requisitos)
- [🧠 Aspectos técnicos](#-aspectos-técnicos)
- [🚀 Instalación](#-instalación)
- [⚙️ Configuración](#️-configuración)
- [🌐 Selección de idioma](#-selección-de-idioma)
- [📖 Uso](#-uso)
- [🎯 Ejemplos](#-ejemplos)
- [🔍 Solución de Problemas](#-solución-de-problemas)
- [🤝 Contribución](#-contribución)
- [📄 Licencia](#-licencia)

## ✨ Características

- 🎶 **Procesamiento de canciones**: Procesa URLs individuales de canciones de Spotify.
- 🔄 **Sincronización automática**: Mantén tu carpeta local sincronizada con playlists de Spotify.
- 🏷️ **Metadatos ID3**: Actualiza automáticamente números de pista, ISRC y URLs de Spotify.
- 🎚️ **Mecanismo de respaldo**: Integra `spotdl` y `yt-dlp` como alternativas cuando el procesamiento principal falla.
- 📁 **Organización**: Crea carpetas automáticamente basadas en el nombre de la playlist.
- 🔍 **Detección inteligente**: Encuentra archivos existentes y evita duplicados.
- 🌐 **Soporte multiidioma**: Maneja acentos, símbolos y caracteres especiales.
- ⚡ **Procesamiento de playlists grandes**: Diseñado para trabajar con playlists extensas y evitar duplicados.

## 🔧 Requisitos

- **Python**: Versión 3.8 o superior.
- **Dependencias**: `spotipy`, `mutagen`, `yt-dlp`, `spotdl`.
- **Credenciales de Spotify Developer**: opcionales, pero recomendadas para evitar limitaciones de uso y mejorar la compatibilidad con la Spotify Web API.
- **Sistema operativo**: Windows, Linux o macOS.

## 🧠 Aspectos técnicos

- Integración con Spotify Web API mediante `spotipy`.
- Gestión de metadatos ID3 mediante `mutagen`.
- Sincronización entre playlists de Spotify y carpetas locales.
- Normalización de nombres de archivo, acentos y caracteres especiales.
- Detección de duplicados y archivos no pertenecientes a la playlist.
- Lógica de reintentos, verificación de resultados y manejo de errores.
- Gestión de rutas multiplataforma mediante `pathlib`.
- Integración con herramientas externas como `spotdl` y `yt-dlp`.

## 🚀 Instalación

### 1. Clona el repositorio
```bash
git clone https://github.com/bruhMomentFixer/spotpsync-tool.git
cd spotpsync-tool
```

### 2. Instala Python
Descarga e instala Python desde [python.org](https://www.python.org/downloads/).

### 3. Instala las dependencias
```bash
pip install -r requirements.txt
```

### 4. Actualiza las dependencias (opcional)
Ejecuta la opción 5 del programa para actualizar `spotdl` y `yt-dlp` automáticamente.

## ⚙️ Configuración

### Credenciales de Spotify
El programa puede utilizar credenciales propias de Spotify Developer o las credenciales por defecto de `spotdl`. **Se recomienda utilizar credenciales propias** para evitar límites de uso y asegurar compatibilidad.

#### Cómo obtener tus credenciales:
1. Ve a [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Crea una nueva aplicación.
3. Copia el `Client ID` y `Client Secret`.
4. Crea un archivo `spotify_client_data.txt` en la misma carpeta que `spotpsync.py`:
   ```
   TU_CLIENT_ID_AQUI
   TU_CLIENT_SECRET_AQUI
   ```

   **Importante**: no subas el archivo `spotify_client_data.txt` al repositorio. Añádelo al `.gitignore` para evitar publicar tus credenciales de Spotify Developer.

#### Opciones de credenciales en el programa:
Cuando ejecutes cualquier función que requiera Spotify, el programa te pedirá elegir:
- **Opción 1**: Usar credenciales del archivo `spotify_client_data.txt` (recomendado)
- **Opción 2**: Usar credenciales por defecto de `spotdl` (limitado, no recomendado)
- **Opción 3**: Ingresar credenciales manualmente

### Configuración inicial
Ejecuta el programa y selecciona la opción de credenciales. El programa te guiará.

## 🌐 Selección de idioma

SpotPSync Tool soporta español e inglés.

Al iniciar el programa, se solicita elegir el idioma de la interfaz:

```text
==================================================
🌐 Language / Idioma
==================================================
1. Español
2. English

Choose language / Elige idioma (1 or 2):
```

Después de seleccionar el idioma, los menús principales, mensajes de estado e indicaciones se mostrarán en el idioma elegido.

## 📖 Uso

### Ejecutar el programa
```bash
python spotpsync.py
```

Al ejecutar el programa, primero se solicita seleccionar el idioma de la interfaz. Después se muestra el menú principal.

### Menú principal
```
==================================================
🎵 SpotPSync Tool
==================================================
1. Procesar una canción individual
2. Procesar múltiples canciones desde archivo
3. Exportar playlist a archivo
4. Sincronizar carpeta local con playlist de Spotify
5. Comprobar y actualizar dependencias
6. Salir

Elige una opción (1, 2, 3, 4, 5 o 6):
```

## 🎯 Ejemplos

### 1. Procesar una canción individual
```
Elige una opción: 1
Introduce la URL de la canción de Spotify: https://open.spotify.com/track/<track_id>
```
Resultado: procesa la URL indicada y almacena el archivo resultante en la carpeta `./downloads`. (crea una si no existe o crea una nueva `./downloads0` si existe una con contenido).

### 2. Procesar múltiples canciones desde archivo
```
Elige una opción: 2
```
Resultado: lee el archivo `spotify-track-list.txt`, procesa las URLs listadas y almacena los archivos resultantes en la carpeta `./downloads`.

### 3. Exportar playlist a archivo
```
Elige una opción: 3
Introduce la URL de la playlist: https://open.spotify.com/playlist/<playlist_id>
```
Resultado: crea automáticamente el archivo `spotify-track-list.txt` con todas las URLs de la playlist.

### 4. Sincronizar carpeta local con playlist de Spotify
```
Elige una opción: 4
Introduce la URL de la playlist: https://open.spotify.com/playlist/<playlist_id>
Introduce la ruta de la carpeta local: C:\Music\Chill EDM
```
Resultado: compara la playlist con la carpeta local, procesa las pistas faltantes y actualiza los metadatos ID3.

### 5. Comprobar y actualizar dependencias
```
Elige una opción: 5
```
Resultado: actualiza `spotdl` y `yt-dlp` a las versiones más recientes.

## 🔍 Solución de Problemas

### Error de autenticación
- Verifica que `spotify_client_data.txt` tenga las credenciales correctas.
- Asegúrate de que la aplicación de Spotify Developer esté correctamente configurada y que las credenciales sean válidas.

### Procesamiento fallido de pistas
- El programa utiliza `spotdl` como método principal y `yt-dlp` como mecanismo de respaldo.
- Si falla, verifica tu conexión a internet y que las URLs sean válidas.

### Problemas con metadatos
- Asegúrate de que los archivos MP3 no estén bloqueados.
- Usa un editor de metadatos como Mp3tag o una herramienta equivalente para verificar.

### Playlist no sincroniza correctamente
- Verifica que la carpeta local tenga permisos de escritura.
- Si hay duplicados, el programa prioriza por número de pista (TRCK).

### Comandos comunes
```bash
# Ver logs detallados (redirigir salida a archivo)
python spotpsync.py > log.txt

# El programa es interactivo y no requiere argumentos adicionales
# Todas las configuraciones se hacen desde el menú
```

## 🤝 Contribución

Las sugerencias, informes de errores y propuestas de mejora son bienvenidas mediante Issues.

## 📄 Licencia

Este proyecto está licenciado bajo la PolyForm Noncommercial License 1.0.0.

Puedes usar, copiar, modificar y compartir este software para fines personales, educativos y otros fines no comerciales.

No se permite el uso comercial sin una licencia comercial separada. Para licencias comerciales, contacta con el autor a través del perfil de GitHub asociado a este repositorio.

Las dependencias de terceros se distribuyen bajo sus respectivas licencias.

---

**⚠️ Nota importante**: Este proyecto está destinado únicamente a uso personal, educativo y no comercial. Los usuarios son responsables de asegurarse de que el uso de esta herramienta cumple con la legislación aplicable, los términos de servicio de las plataformas utilizadas y la normativa sobre derechos de autor.
