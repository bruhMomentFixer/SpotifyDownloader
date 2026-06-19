import builtins
import json
import logging
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional, Sequence

import mutagen
import spotipy
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, TRCK, TSRC, WOAS
from spotipy.oauth2 import SpotifyClientCredentials


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CREDENTIALS_FILE = Path("spotify_client_data.txt")
TRACK_LIST_FILE = Path("spotify-track-list.txt")
OUTPUT_DIR = Path("downloads")
MIN_VALID_FILE_SIZE_MB = 0.1

PLACEHOLDER_CREDENTIALS = {
    "TU_CLIENT_ID_AQUI",
    "TU_CLIENT_SECRET_AQUI",
    "YOUR_CLIENT_ID_HERE",
    "YOUR_CLIENT_SECRET_HERE",
}


# -----------------------------------------------------------------------------
# Internationalization
# -----------------------------------------------------------------------------

LANG = "es"

EN_TEXT = {
    "Error desconocido (sin salida de error)": "Unknown error (no error output)",
    "Error desconocido": "Unknown error",
    "🔐 CONFIGURACIÓN DE CREDENCIALES": "🔐 CREDENTIAL CONFIGURATION",
    "1. Usar credenciales del archivo 'spotify_client_data.txt'": "1. Use credentials from 'spotify_client_data.txt'",
    "2. Usar credenciales por defecto de spotdl": "2. Use spotdl default credentials",
    "3. Ingresar credenciales manualmente": "3. Enter credentials manually",
    "\nElige una opción (1, 2 o 3): ": "\nChoose an option (1, 2 or 3): ",
    "✅ Usando credenciales del archivo": "✅ Using credentials from file",
    "❌ No se encontraron credenciales válidas en el archivo": "❌ No valid credentials were found in the file",
    "✅ Usando credenciales por defecto de spotdl": "✅ Using spotdl default credentials",
    "Introduce tu Spotify Client ID: ": "Enter your Spotify Client ID: ",
    "Introduce tu Spotify Client Secret: ": "Enter your Spotify Client Secret: ",
    "✅ Usando credenciales manuales": "✅ Using manually entered credentials",
    "❌ Credenciales inválidas": "❌ Invalid credentials",
    "❌ Opción no válida": "❌ Invalid option",
    "🔐 CREDENCIALES DE SPOTIFY DEVELOPER": "🔐 SPOTIFY DEVELOPER CREDENTIALS",
    "Esta función requiere credenciales propias de Spotify Developer.": "This feature requires your own Spotify Developer credentials.",
    "2. Ingresar credenciales manualmente": "2. Enter credentials manually",
    "3. Cancelar": "3. Cancel",
    "❌ Operación cancelada": "❌ Operation cancelled",
    "🔄 Intentando con yt-dlp como alternativa...": "🔄 Trying yt-dlp as fallback...",
    "❌ No se encontraron resultados en YouTube.": "❌ No YouTube results were found.",
    "❌ yt-dlp no generó ningún archivo MP3.": "❌ yt-dlp did not generate any MP3 file.",
    "❌ El archivo generado es demasiado pequeño, probablemente corrupto.": "❌ The generated file is too small and probably corrupted.",
    "⚠️ spotDL reportó éxito pero la verificación falló, reintentando...": "⚠️ spotDL reported success, but verification failed. Retrying...",
    "🔄 Todos los intentos con spotDL fallaron, usando yt-dlp...": "🔄 All spotDL attempts failed. Using yt-dlp...",
    "❌ Falló incluso con yt-dlp": "❌ Failed even with yt-dlp",
    "🎵 PROCESAR CANCIÓN INDIVIDUAL": "🎵 PROCESS SINGLE TRACK",
    "Introduce la URL de la canción de Spotify: ": "Enter the Spotify track URL: ",
    "❌ URL inválida.": "❌ Invalid URL.",
    "\n🎉 Procesamiento completado con éxito": "\n🎉 Processing completed successfully",
    "\n⚠️ Pistas procesadas con yt-dlp; verifícalas manualmente:": "\n⚠️ Tracks processed with yt-dlp; verify them manually:",
    "\n💥 El procesamiento falló": "\n💥 Processing failed",
    "❌ URLs inválidas encontradas:": "❌ Invalid URLs found:",
    "❌ No se encontraron URLs válidas en el archivo": "❌ No valid URLs were found in the file",
    "📊 RESUMEN DE PROCESAMIENTO": "📊 PROCESSING SUMMARY",
    "🔎 Obteniendo metadata de playlist mediante spotDL...": "🔎 Getting playlist metadata using spotDL...",
    "¿Qué deseas hacer?": "What do you want to do?",
    "1. Sobrescribir el archivo": "1. Overwrite the file",
    "2. Añadir al final del archivo": "2. Append to the end of the file",
    "📋 EXPORTAR PLAYLIST A ARCHIVO": "📋 EXPORT PLAYLIST TO FILE",
    "Introduce la URL de la playlist de Spotify: ": "Enter the Spotify playlist URL: ",
    "❌ URL inválida. Debe ser una playlist de Spotify.": "❌ Invalid URL. It must be a Spotify playlist.",
    "\n❌ Error al obtener la playlist:": "\n❌ Error getting the playlist:",
    "❌ No se encontraron canciones en la playlist": "❌ No tracks were found in the playlist",
    "\n🎉 Playlist exportada correctamente": "\n🎉 Playlist exported successfully",
    "❌ Error exportando la playlist": "❌ Error exporting the playlist",
    "🔄 SINCRONIZAR PLAYLIST DE SPOTIFY": "🔄 SYNCHRONIZE SPOTIFY PLAYLIST",
    "Introduce la ruta de la carpeta local de la playlist: ": "Enter the local playlist folder path: ",
    "❌ No se pudo extraer el ID de la playlist.": "❌ Could not extract the playlist ID.",
    "📡 Obteniendo información de la playlist...": "📡 Getting playlist information...",
    "⚠️ El nombre de la carpeta no coincide con el nombre de la playlist.": "⚠️ The folder name does not match the playlist name.",
    "¿Quieres renombrar la carpeta automáticamente? (s/n): ": "Do you want to automatically rename the folder? (y/n): ",
    "¿Quieres crear una carpeta nueva para esta playlist y usarla? (s/n): ": "Do you want to create a new folder for this playlist and use it? (y/n): ",
    "↩️ Operación cancelada. Volviendo al menú principal.": "↩️ Operation cancelled. Returning to the main menu.",
    "🔎 Buscando coincidencias en la carpeta local...": "🔎 Searching for matches in the local folder...",
    "\n🛠️ Actualizando metadatos...": "\n🛠️ Updating metadata...",
    "📊 RESULTADO DE DETECCIÓN / ACTUALIZACIÓN": "📊 DETECTION / UPDATE RESULT",
    "\n📝 Cambios realizados:": "\n📝 Changes made:",
    "¿Deseas BORRAR estos archivos extra? (s/n): ": "Do you want to DELETE these extra files? (y/n): ",
    "ℹ️ No se borraron archivos extra.": "ℹ️ Extra files were not deleted.",
    "\n✅ No hay archivos extra.": "\n✅ There are no extra files.",
    "\n✅ Todas las canciones están sincronizadas.": "\n✅ All tracks are synchronized.",
    "\n🎵 Canciones faltantes:": "\n🎵 Missing tracks:",
    "\n¿Deseas procesar las canciones faltantes? (s/n): ": "\nDo you want to process the missing tracks? (y/n): ",
    "\nℹ️ Procesamiento omitido por el usuario.": "\nℹ️ Processing skipped by user.",
    "\n⬇️ Procesando canciones faltantes...\n": "\n⬇️ Processing missing tracks...\n",
    "\n🎉 Sincronización completada.": "\n🎉 Synchronization completed.",
    "\n🔍 Comprobando versiones de dependencias...": "\n🔍 Checking dependency versions...",
    "⚠️ spotDL tiene una versión más reciente disponible.": "⚠️ A newer version of spotDL is available.",
    "✅ spotDL está actualizado.": "✅ spotDL is up to date.",
    "⚠️ yt-dlp tiene una versión más reciente disponible.": "⚠️ A newer version of yt-dlp is available.",
    "✅ yt-dlp está actualizado.": "✅ yt-dlp is up to date.",
    "\n🎉 Todas las dependencias están actualizadas.": "\n🎉 All dependencies are up to date.",
    "\n¿Quieres actualizar las dependencias desactualizadas? (s/n): ": "\nDo you want to update outdated dependencies? (y/n): ",
    "Actualizando spotDL...": "Updating spotDL...",
    "Actualizando yt-dlp...": "Updating yt-dlp...",
    "Actualización cancelada.": "Update cancelled.",
    "Por favor, responde 's' o 'n'.": "Please answer 'y' or 'n'.",
    "1. Procesar una canción individual": "1. Process a single track",
    "2. Procesar múltiples canciones desde archivo": "2. Process multiple tracks from file",
    "3. Exportar playlist a archivo": "3. Export playlist to file",
    "4. Sincronizar playlist local con Spotify": "4. Synchronize local playlist with Spotify",
    "5. Comprobar y actualizar dependencias": "5. Check and update dependencies",
    "6. Salir": "6. Exit",
    "\nElige una opción (1, 2, 3, 4, 5 o 6): ": "\nChoose an option (1, 2, 3, 4, 5 or 6): ",
    "👋 Hasta luego": "👋 Goodbye",
    "\nPresiona Enter para continuar...": "\nPress Enter to continue...",
    "\n⏹️ Programa cancelado por el usuario": "\n⏹️ Program cancelled by user",
    "\nPrograma terminado": "\nProgram finished",
}


def translate_text(text: str) -> str:
    """Translates user-facing text at runtime when English mode is selected."""
    if LANG != "en":
        return text

    if text in EN_TEXT:
        return EN_TEXT[text]

    # Dynamic message patterns.
    replacements = [
        (r"^🔍 Buscando en YouTube: (.+)$", r"🔍 Searching on YouTube: \1"),
        (r"^🏆 Mejor coincidencia: (.+)$", r"🏆 Best match: \1"),
        (r"^🔗 URL seleccionada: (.+)$", r"🔗 Selected URL: \1"),
        (r"^❌ Error ejecutando yt-dlp: (.+)$", r"❌ Error running yt-dlp: \1"),
        (r"^✅ Procesamiento alternativo completado: (.+)$", r"✅ Fallback processing completed: \1"),
        (r"^❌ Error en el procesamiento con yt-dlp: (.+)$", r"❌ Error during yt-dlp processing: \1"),
        (r"^🎵 Procesando: (.+)$", r"🎵 Processing: \1"),
        (r"^🎵 Procesando URL: (.+)$", r"🎵 Processing URL: \1"),
        (r"^📁 Archivo esperado: (.+)$", r"📁 Expected file: \1"),
        (r"^⏳ Ejecutando spotDL \(intento (.+)\)$", r"⏳ Running spotDL (attempt \1)"),
        (r"^✅ Procesamiento correcto con spotDL: (.+)$", r"✅ Correctly processed with spotDL: \1"),
        (r"^🏷️ Metadato TRCK actualizado a (.+)$", r"🏷️ TRCK metadata updated to \1"),
        (r"^⚠️ No se pudo actualizar TRCK: (.+)$", r"⚠️ Could not update TRCK: \1"),
        (r"^⚠️ Error spotDL: (.+)$", r"⚠️ spotDL error: \1"),
        (r"^⏰ Timeout \(intento (.+)\), reintentando\.\.\.$", r"⏰ Timeout (attempt \1), retrying..."),
        (r"^⚠️ Error inesperado: (.+)$", r"⚠️ Unexpected error: \1"),
        (r"^ℹ️ El archivo correcto ya existe: (.+)$", r"ℹ️ The correct file already exists: \1"),
        (r"^✅ Archivo renombrado a: (.+)$", r"✅ File renamed to: \1"),
        (r"^⚠️ No se pudo renombrar el archivo: (.+)$", r"⚠️ Could not rename the file: \1"),
        (r"^📋 Añadida a la lista de verificación manual: (.+)$", r"📋 Added to the manual verification list: \1"),
        (r"^🔧 URL normalizada: (.+)$", r"🔧 Normalized URL: \1"),
        (r"^📥 Procesando: (.+)$", r"📥 Processing: \1"),
        (r"^📁 Carpeta de destino: (.+)$", r"📁 Destination folder: \1"),
        (r"^❌ El archivo (.+) no existe$", r"❌ The file \1 does not exist"),
        (r"^⚠️ URL duplicada en línea (.+)$", r"⚠️ Duplicate URL on line \1"),
        (r"^   Línea (.+)$", r"   Line \1"),
        (r"^✅ Se encontraron (\d+) URLs válidas$", r"✅ Found \1 valid URLs"),
        (r"^❌ Error leyendo el archivo: (.+)$", r"❌ Error reading the file: \1"),
        (r"^🎵 Iniciando procesamiento de (\d+) canciones en la carpeta: (.+)$", r"🎵 Starting processing of \1 tracks in folder: \2"),
        (r"^✅ Canción (\d+) procesada con éxito$", r"✅ Track \1 processed successfully"),
        (r"^❌ Canción (\d+) falló$", r"❌ Track \1 failed"),
        (r"^💥 Error en la canción (\d+): (.+)$", r"💥 Error on track \1: \2"),
        (r"^• Total de canciones: (.+)$", r"• Total tracks: \1"),
        (r"^• Procesadas correctamente: (.+)$", r"• Successfully processed: \1"),
        (r"^• Fallidas: (.+)$", r"• Failed: \1"),
        (r"^✅ Se encontraron (\d+) canciones en la playlist$", r"✅ Found \1 tracks in the playlist"),
        (r"^⚠️ El archivo (.+) ya contiene (\d+) líneas$", r"⚠️ The file \1 already contains \2 lines"),
        (r"^✅ Archivo (.+) con (\d+) URLs$", r"✅ File \1 with \2 URLs"),
        (r"^❌ Error guardando las URLs: (.+)$", r"❌ Error saving URLs: \1"),
        (r"^🔗 URL de playlist: (.+)$", r"🔗 Playlist URL: \1"),
        (r"^📁 Archivo: (.+)$", r"📁 File: \1"),
        (r"^🎵 Canciones: (.+)$", r"🎵 Tracks: \1"),
        (r"^🔧 WOAS actualizado en (.+)$", r"🔧 WOAS updated in \1"),
        (r"^❌ La carpeta (.+) no existe\.$", r"❌ The folder \1 does not exist."),
        (r"^❌ Error obteniendo información de la playlist: (.+)$", r"❌ Error getting playlist information: \1"),
        (r"^🎧 Playlist con (\d+) canciones encontradas$", r"🎧 Playlist with \1 tracks found"),
        (r"^   Carpeta actual : (.+)$", r"   Current folder: \1"),
        (r"^   Playlist nombre: (.+)$", r"   Playlist name: \1"),
        (r"^✅ Carpeta renombrada a: (.+)$", r"✅ Folder renamed to: \1"),
        (r"^❌ Error renombrando carpeta: (.+)$", r"❌ Error renaming folder: \1"),
        (r"^📁 Carpeta creada: (.+)$", r"📁 Folder created: \1"),
        (r"^❌ No se pudo crear la carpeta: (.+)$", r"❌ Could not create the folder: \1"),
        (r"^✅ (.+) → pista #(\d+) \(ya correcta\)$", r"✅ \1 → track #\2 (already correct)"),
        (r"^🛠️ (.+) → pista actualizada (.+) → (.+)$", r"🛠️ \1 → track updated \2 → \3"),
        (r"^⚠️ No se pudo actualizar metadatos en (.+): (.+)$", r"⚠️ Could not update metadata in \1: \2"),
        (r"^• Canciones en playlist: (.+)$", r"• Tracks in playlist: \1"),
        (r"^• Canciones encontradas en carpeta: (.+)$", r"• Tracks found in folder: \1"),
        (r"^• Números de pista correctos: (.+)$", r"• Correct track numbers: \1"),
        (r"^• Números de pista actualizados: (.+)$", r"• Updated track numbers: \1"),
        (r"^• Canciones faltantes: (.+)$", r"• Missing tracks: \1"),
        (r"^⚠️ Se encontraron (\d+) archivos no pertenecientes a la playlist:$", r"⚠️ Found \1 files that do not belong to the playlist:"),
        (r"^🗑️ Borrado: (.+)$", r"🗑️ Deleted: \1"),
        (r"^❌ No se pudo borrar (.+): (.+)$", r"❌ Could not delete \1: \2"),
        (r"^✅ Metadato de pista actualizado para (.+)$", r"✅ Track metadata updated for \1"),
        (r"^⚠️ No se pudo escribir tag en (.+): (.+)$", r"⚠️ Could not write tag in \1: \2"),
        (r"^📄 Archivo '(.+)' creado$", r"📄 File '\1' created"),
        (r"^📄 Archivo '(.+)' creado con ejemplo$", r"📄 File '\1' created with example content"),
        (r"^✅ (.+) versión instalada: (.+)$", r"✅ Installed \1 version: \2"),
        (r"^❌ Error obteniendo versión de (.+)$", r"❌ Error getting \1 version"),
        (r"^❌ Error obteniendo versión de (.+): (.+)$", r"❌ Error getting \1 version: \2"),
        (r"^❌ Error comprobando actualizaciones: (.+)$", r"❌ Error checking updates: \1"),
    ]

    for pattern, replacement in replacements:
        if re.search(pattern, text):
            return re.sub(pattern, replacement, text)

    return text


def print(*args, **kwargs):  # type: ignore[override]
    translated_args = [translate_text(arg) if isinstance(arg, str) else arg for arg in args]
    builtins.print(*translated_args, **kwargs)


def input(prompt: str = "") -> str:  # type: ignore[override]
    translated_prompt = translate_text(prompt)
    response = builtins.input(translated_prompt)

    if LANG == "en" and "(y/n)" in translated_prompt.lower():
        normalized = response.strip().lower()
        if normalized in {"y", "yes"}:
            return "s"
        if normalized in {"n", "no"}:
            return "n"

    return response


def select_language() -> None:
    """Lets the user select the interface language at startup."""
    global LANG

    if "--lang" in sys.argv:
        try:
            lang_arg = sys.argv[sys.argv.index("--lang") + 1].strip().lower()
            if lang_arg in {"es", "en"}:
                LANG = lang_arg
                return
        except (IndexError, ValueError):
            pass

    builtins.print("\n" + "=" * 50)
    builtins.print("🌐 Language / Idioma")
    builtins.print("=" * 50)
    builtins.print("1. Español")
    builtins.print("2. English")

    while True:
        choice = builtins.input("\nChoose language / Elige idioma (1 or 2): ").strip()
        if choice == "1":
            LANG = "es"
            return
        if choice == "2":
            LANG = "en"
            return
        builtins.print("❌ Invalid option / Opción no válida")


# -----------------------------------------------------------------------------
# Command helpers
# -----------------------------------------------------------------------------


def extract_spotdl_error(stderr_output: str) -> str:
    """Extracts the most useful error lines from spotDL stderr output."""
    if not stderr_output:
        return "Error desconocido (sin salida de error)"

    lines = stderr_output.splitlines()
    error_lines: list[str] = []

    for line in lines:
        line_lower = line.lower()
        if (
            any(keyword in line_lower for keyword in ["error", "exception", "failed", "keyerror", "timeout"])
            and "traceback" not in line_lower
            and 'file "' not in line_lower
        ):
            clean_line = line.strip()
            if clean_line and not clean_line.startswith("+"):
                error_lines.append(clean_line)

    if not error_lines:
        for line in lines:
            line_lower = line.lower()
            if "unable to find" in line_lower or "keyerror" in line_lower:
                error_lines.append(line.strip())

    if not error_lines:
        error_lines = [line.strip() for line in lines[-3:] if line.strip()]

    return " | ".join(error_lines[:2]) if error_lines else "Error desconocido"


def run_command(command: Sequence[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
    """Runs an external command using a safe argv list."""
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


# -----------------------------------------------------------------------------
# Spotify URL helpers
# -----------------------------------------------------------------------------


def normalize_spotify_track_url(url: str) -> str:
    """Normalizes Spotify track URLs, removing regional prefixes and query params."""
    pattern = r"https://open\.spotify\.com/(?:intl-[a-z]{2}/)?track/([a-zA-Z0-9]+)"
    match = re.search(pattern, url.strip())
    if match:
        return f"https://open.spotify.com/track/{match.group(1)}"
    return url.strip()


def normalize_spotify_playlist_url(url: str) -> str:
    """Normalizes Spotify playlist URLs, removing regional prefixes and query params."""
    pattern = r"https://open\.spotify\.com/(?:intl-[a-z]{2}/)?playlist/([a-zA-Z0-9]+)"
    match = re.search(pattern, url.strip())
    if match:
        return f"https://open.spotify.com/playlist/{match.group(1)}"
    return url.strip()


def is_valid_spotify_track_url(url: str) -> bool:
    return normalize_spotify_track_url(url).startswith("https://open.spotify.com/track/")


def extract_playlist_id(playlist_url: str) -> Optional[str]:
    normalized_url = normalize_spotify_playlist_url(playlist_url)
    match = re.search(r"/playlist/([a-zA-Z0-9]+)", normalized_url)
    return match.group(1) if match else None


def extract_track_id(url: str) -> str:
    if not url:
        return ""

    url = unicodedata.normalize("NFKC", url)
    url = url.lower().strip().split("?")[0].rstrip("/")
    url = url.replace("/intl-es/", "/").replace("/intl/", "/").replace("/es/", "/")

    match = re.search(r"track/([a-z0-9]{22})", url)
    return match.group(1) if match else url


def extract_track_urls_from_text(text: str) -> list[str]:
    """Extracts unique Spotify track URLs from arbitrary CLI output."""
    pattern = r"https://open\.spotify\.com/(?:intl-[a-z]{2}/)?track/[a-zA-Z0-9]+(?:\?[^\s|\]\)\"']*)?"
    urls: list[str] = []
    seen: set[str] = set()

    for raw_url in re.findall(pattern, text):
        normalized_url = normalize_spotify_track_url(raw_url)
        if normalized_url not in seen:
            urls.append(normalized_url)
            seen.add(normalized_url)

    return urls



def _add_track_url(track_id: str, urls: list[str], seen: set[str]) -> None:
    """Adds a normalized Spotify track URL from a raw 22-character track id."""
    if not re.fullmatch(r"[A-Za-z0-9]{22}", track_id):
        return

    url = f"https://open.spotify.com/track/{track_id}"
    if url not in seen:
        urls.append(url)
        seen.add(url)


def extract_track_urls_from_spotdl_metadata(data) -> list[str]:
    """
    Extracts Spotify track URLs from spotDL metadata files.

    spotDL .spotdl files are JSON-like metadata exports. Their exact structure can
    vary between versions, so this function recursively searches for Spotify track
    URLs, Spotify track URIs, and likely track-id fields.
    """
    urls: list[str] = []
    seen: set[str] = set()

    def visit(node):
        if isinstance(node, dict):
            for key, value in node.items():
                key_lower = str(key).lower()

                if isinstance(value, str):
                    # Full Spotify track URLs embedded in metadata.
                    for url in extract_track_urls_from_text(value):
                        if url not in seen:
                            urls.append(url)
                            seen.add(url)

                    # Spotify URI format: spotify:track:<id>
                    uri_match = re.fullmatch(r"spotify:track:([A-Za-z0-9]{22})", value.strip())
                    if uri_match:
                        _add_track_url(uri_match.group(1), urls, seen)

                    # Common metadata keys used for Spotify ids.
                    if key_lower in {"song_id", "track_id", "spotify_id", "spotify_track_id"}:
                        _add_track_url(value.strip(), urls, seen)

                    # Some spotDL versions may use a generic id field inside a song object.
                    if key_lower == "id" and any(k in node for k in ("name", "title", "artists", "artist")):
                        _add_track_url(value.strip(), urls, seen)
                else:
                    visit(value)

        elif isinstance(node, list):
            for item in node:
                visit(item)

        elif isinstance(node, str):
            for url in extract_track_urls_from_text(node):
                if url not in seen:
                    urls.append(url)
                    seen.add(url)

            uri_match = re.fullmatch(r"spotify:track:([A-Za-z0-9]{22})", node.strip())
            if uri_match:
                _add_track_url(uri_match.group(1), urls, seen)

    visit(data)
    return urls


# -----------------------------------------------------------------------------
# Credentials
# -----------------------------------------------------------------------------


def load_credentials_from_file() -> Optional[tuple[str, str]]:
    """Loads Spotify Developer credentials from spotify_client_data.txt."""
    if not CREDENTIALS_FILE.exists():
        return None

    try:
        lines = [line.strip() for line in CREDENTIALS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(lines) < 2:
            return None

        client_id, client_secret = lines[:2]
        if not client_id or not client_secret:
            return None

        if client_id in PLACEHOLDER_CREDENTIALS or client_secret in PLACEHOLDER_CREDENTIALS:
            return None

        return client_id, client_secret
    except Exception as exc:
        logger.error("Error leyendo archivo de credenciales: %s", exc)
        return None


def credentials_to_spotdl_args(credentials: tuple[str, str]) -> list[str]:
    client_id, client_secret = credentials
    return ["--client-id", client_id, "--client-secret", client_secret]


def credentials_from_spotdl_args(spotdl_args: Sequence[str]) -> Optional[tuple[str, str]]:
    client_id: Optional[str] = None
    client_secret: Optional[str] = None

    iterator = iter(range(len(spotdl_args)))
    for i in iterator:
        if spotdl_args[i] == "--client-id" and i + 1 < len(spotdl_args):
            client_id = spotdl_args[i + 1]
        elif spotdl_args[i] == "--client-secret" and i + 1 < len(spotdl_args):
            client_secret = spotdl_args[i + 1]

    if client_id and client_secret:
        return client_id, client_secret
    return None


def make_spotify_client(credentials: tuple[str, str]) -> spotipy.Spotify:
    client_id, client_secret = credentials
    return spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=client_id, client_secret=client_secret))


def get_spotdl_credentials() -> tuple[list[str], str]:
    """
    Gets credentials for spotDL-backed operations.

    Returns:
        (spotdl_args, source), where source is one of: file, default, manual.
    """
    print("\n" + "=" * 50)
    print("🔐 CONFIGURACIÓN DE CREDENCIALES")
    print("=" * 50)
    print("1. Usar credenciales del archivo 'spotify_client_data.txt'")
    print("2. Usar credenciales por defecto de spotdl")
    print("3. Ingresar credenciales manualmente")

    while True:
        option = input("\nElige una opción (1, 2 o 3): ").strip()

        if option == "1":
            credentials = load_credentials_from_file()
            if credentials:
                print("✅ Usando credenciales del archivo")
                return credentials_to_spotdl_args(credentials), "file"
            print("❌ No se encontraron credenciales válidas en el archivo")

        elif option == "2":
            print("✅ Usando credenciales por defecto de spotdl")
            return [], "default"

        elif option == "3":
            client_id = input("Introduce tu Spotify Client ID: ").strip()
            client_secret = input("Introduce tu Spotify Client Secret: ").strip()
            if client_id and client_secret:
                print("✅ Usando credenciales manuales")
                return ["--client-id", client_id, "--client-secret", client_secret], "manual"
            print("❌ Credenciales inválidas")

        else:
            print("❌ Opción no válida")


def get_spotify_api_credentials() -> Optional[tuple[tuple[str, str], list[str]]]:
    """Gets credentials for operations that require direct Spotify Web API access."""
    print("\n" + "=" * 50)
    print("🔐 CREDENCIALES DE SPOTIFY DEVELOPER")
    print("=" * 50)
    print("Esta función requiere credenciales propias de Spotify Developer.")
    print("1. Usar credenciales del archivo 'spotify_client_data.txt'")
    print("2. Ingresar credenciales manualmente")
    print("3. Cancelar")

    while True:
        option = input("\nElige una opción (1, 2 o 3): ").strip()

        if option == "1":
            credentials = load_credentials_from_file()
            if credentials:
                print("✅ Usando credenciales del archivo")
                return credentials, credentials_to_spotdl_args(credentials)
            print("❌ No se encontraron credenciales válidas en el archivo")

        elif option == "2":
            client_id = input("Introduce tu Spotify Client ID: ").strip()
            client_secret = input("Introduce tu Spotify Client Secret: ").strip()
            if client_id and client_secret:
                print("✅ Usando credenciales manuales")
                credentials = (client_id, client_secret)
                return credentials, credentials_to_spotdl_args(credentials)
            print("❌ Credenciales inválidas")

        elif option == "3":
            print("❌ Operación cancelada")
            return None

        else:
            print("❌ Opción no válida")


# -----------------------------------------------------------------------------
# Metadata and filename helpers
# -----------------------------------------------------------------------------


def normalize_song_name(name: str) -> str:
    """Normalizes song or file names for matching."""
    name = unicodedata.normalize("NFD", name)
    name = "".join(char for char in name if unicodedata.category(char) != "Mn")
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = re.sub(r"[\(\)\[\]\{\}_\-\+]", " ", name)
    name = re.sub(r"\b(?:feat|ft|with)\b.*", "", name, flags=re.IGNORECASE)

    stopwords = ["feat", "ft", "remix", "version", "official", "audio", "video", "explicit"]
    for word in stopwords:
        name = re.sub(rf"\b{word}\b", "", name, flags=re.IGNORECASE)

    return re.sub(r"\s+", " ", name).strip().lower()


def normalize_folder_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", name).strip()


def load_full_id3_tags(mp3_path: Path | str) -> ID3:
    try:
        return ID3(mp3_path)
    except mutagen.id3.ID3NoHeaderError:
        tags = ID3()
        tags.save(mp3_path)
        return ID3(mp3_path)


def update_track_tags(mp3_path: Path | str, track_number: int, isrc: Optional[str] = None) -> None:
    """Updates only TRCK and TSRC ID3 frames."""
    tags = load_full_id3_tags(mp3_path)
    tags.setall("TRCK", [TRCK(encoding=3, text=str(track_number))])

    if isrc:
        tags.setall("TSRC", [TSRC(encoding=3, text=isrc)])

    tags.save(mp3_path)


# -----------------------------------------------------------------------------
# spotDL metadata helpers
# -----------------------------------------------------------------------------


def get_track_info_for_display(url: str, spotdl_args: Optional[Sequence[str]] = None) -> Optional[dict]:
    """Gets track metadata using `spotdl search --print json`."""
    command = ["spotdl", "search", url, "--print", "json"]
    if spotdl_args:
        command.extend(spotdl_args)

    try:
        result = run_command(command, timeout=30)
        if result.returncode != 0 or not result.stdout.strip():
            return None

        data = json.loads(result.stdout)
        if isinstance(data, list):
            return data[0] if data else None
        if isinstance(data, dict):
            return data
        return None
    except Exception:
        return None


def track_info_to_display_name(track_info: Optional[dict]) -> Optional[str]:
    if not track_info:
        return None

    artists = track_info.get("artists") or []
    if artists and isinstance(artists[0], dict):
        artist = artists[0].get("name", "Unknown")
    elif artists:
        artist = str(artists[0])
    else:
        artist = "Unknown"

    title = track_info.get("name") or track_info.get("title") or "Unknown Track"
    return f"{artist} - {title}"


def get_expected_filename(url: str, output_path: Path, spotdl_args: Optional[Sequence[str]] = None) -> Optional[str]:
    track_info = get_track_info_for_display(url, spotdl_args)
    display_name = track_info_to_display_name(track_info)
    return f"{sanitize_filename(display_name)}.mp3" if display_name else None


# -----------------------------------------------------------------------------
# Track processing
# -----------------------------------------------------------------------------


def download_with_yt_dlp(spotify_url: str, output_path: Path, spotdl_args: Optional[Sequence[str]] = None) -> bool:
    """Fallback method using yt-dlp when spotDL fails."""
    print("🔄 Intentando con yt-dlp como alternativa...")
    output_path.mkdir(exist_ok=True)

    track_info = get_track_info_for_display(spotify_url, spotdl_args)
    clean_query = track_info_to_display_name(track_info) or "unknown track"
    search_query = f"ytsearch5:{clean_query}"
    print(f"🔍 Buscando en YouTube: {search_query}")

    try:
        info_result = run_command(["yt-dlp", "--dump-json", "--flat-playlist", search_query], timeout=60)
        results = [json.loads(line) for line in info_result.stdout.splitlines() if line.strip()]

        if not results:
            print("❌ No se encontraron resultados en YouTube.")
            return False

        best_match = results[0]
        video_url = f"https://www.youtube.com/watch?v={best_match['id']}"
        print(f"🏆 Mejor coincidencia: {best_match.get('title', 'Unknown')}")
        print(f"🔗 URL seleccionada: {video_url}")

        existing_files = set(output_path.glob("*.mp3"))
        download_result = run_command(
            ["yt-dlp", "-x", "--audio-format", "mp3", "-o", str(output_path / "%(title)s.%(ext)s"), video_url],
            timeout=300,
        )

        if download_result.returncode != 0:
            print(f"❌ Error ejecutando yt-dlp: {download_result.stderr.strip()}")
            return False

        new_files = set(output_path.glob("*.mp3")) - existing_files
        candidate_files = list(new_files) or list(output_path.glob("*.mp3"))
        if not candidate_files:
            print("❌ yt-dlp no generó ningún archivo MP3.")
            return False

        latest_file = max(candidate_files, key=lambda file: file.stat().st_mtime)
        size_mb = latest_file.stat().st_size / (1024 * 1024)
        if size_mb <= MIN_VALID_FILE_SIZE_MB:
            print("❌ El archivo generado es demasiado pequeño, probablemente corrupto.")
            return False

        print(f"✅ Procesamiento alternativo completado: {latest_file.name} ({size_mb:.2f} MB)")
        return True

    except Exception as exc:
        print(f"❌ Error en el procesamiento con yt-dlp: {exc}")
        return False


def process_track_with_retries(
    url: str,
    output_path: Path,
    spotdl_args: Optional[Sequence[str]] = None,
    timeout: int = 300,
    fallback_list: Optional[list[str]] = None,
    track_number: Optional[int] = None,
) -> bool:
    """Processes one Spotify track with spotDL and falls back to yt-dlp when needed."""
    track_info = get_track_info_for_display(url, spotdl_args)
    display_name = track_info_to_display_name(track_info)

    if display_name:
        print(f"🎵 Procesando: {display_name}")
    else:
        print(f"🎵 Procesando URL: {url}")

    expected_filename = get_expected_filename(url, output_path, spotdl_args)
    if expected_filename:
        print(f"📁 Archivo esperado: {expected_filename}")

    max_retries = 3
    retry_delay = 5
    existing_files = set(output_path.glob("*.mp3")) if output_path.exists() else set()

    for attempt in range(max_retries):
        try:
            print(f"⏳ Ejecutando spotDL (intento {attempt + 1}/{max_retries})...")
            command = [
                "spotdl",
                "download",
                url,
                "--output",
                str(output_path / "{artist} - {title}.{output-ext}"),
                "--format",
                "mp3",
                "--lyrics",
                "genius",
            ]
            if spotdl_args:
                command.extend(spotdl_args)

            result = run_command(command, timeout=timeout)
            if result.returncode == 0:
                time.sleep(2)
                new_files = set(output_path.glob("*.mp3")) - existing_files
                if len(new_files) == 1:
                    new_file = next(iter(new_files))
                    size_mb = new_file.stat().st_size / (1024 * 1024)
                    if size_mb > MIN_VALID_FILE_SIZE_MB:
                        print(f"✅ Procesamiento correcto con spotDL: {new_file.name} ({size_mb:.2f} MB)")
                        if track_number:
                            try:
                                update_track_tags(new_file, track_number)
                                print(f"🏷️ Metadato TRCK actualizado a {track_number}")
                            except Exception as exc:
                                print(f"⚠️ No se pudo actualizar TRCK: {exc}")
                        return True
                print("⚠️ spotDL reportó éxito pero la verificación falló, reintentando...")
            else:
                print(f"⚠️ Error spotDL: {extract_spotdl_error(result.stderr)}")

            time.sleep(retry_delay)

        except subprocess.TimeoutExpired:
            print(f"⏰ Timeout (intento {attempt + 1}), reintentando...")
            time.sleep(retry_delay)
        except Exception as exc:
            print(f"⚠️ Error inesperado: {exc}")
            time.sleep(retry_delay)

    print("🔄 Todos los intentos con spotDL fallaron, usando yt-dlp...")
    fallback_success = download_with_yt_dlp(url, output_path, spotdl_args)

    if not fallback_success:
        print("❌ Falló incluso con yt-dlp")
        return False

    display_name = display_name or "Unknown - Unknown Track"
    mp3_files = list(output_path.glob("*.mp3"))
    if not mp3_files:
        return False

    latest_file = max(mp3_files, key=lambda file: file.stat().st_mtime)
    final_name = sanitize_filename(f"{display_name}.mp3")
    final_path = output_path / final_name

    try:
        if final_path.exists() and final_path != latest_file:
            latest_file.unlink(missing_ok=True)
            print(f"ℹ️ El archivo correcto ya existe: {final_path.name}")
        elif final_path != latest_file:
            latest_file.rename(final_path)
            print(f"✅ Archivo renombrado a: {final_name}")
        else:
            final_path = latest_file
    except Exception as exc:
        print(f"⚠️ No se pudo renombrar el archivo: {exc}")
        final_path = latest_file

    if fallback_list is not None:
        fallback_list.append(display_name)
        print(f"📋 Añadida a la lista de verificación manual: {display_name}")

    if track_number:
        try:
            update_track_tags(final_path, track_number)
            print(f"🏷️ Metadato TRCK actualizado a {track_number}")
        except Exception as exc:
            print(f"⚠️ No se pudo actualizar TRCK: {exc}")

    return True


def get_unique_output_folder(base_name: str = "downloads") -> Path:
    folder = Path(base_name)
    if not folder.exists() or not any(folder.iterdir()):
        return folder

    counter = 0
    while True:
        new_folder = Path(f"{base_name}{counter}")
        if not new_folder.exists() or not any(new_folder.iterdir()):
            return new_folder
        counter += 1


def process_single_track() -> None:
    spotdl_args, _ = get_spotdl_credentials()

    print("\n" + "=" * 50)
    print("🎵 PROCESAR CANCIÓN INDIVIDUAL")
    print("=" * 50)
    track_url = input("Introduce la URL de la canción de Spotify: ").strip()

    normalized_url = normalize_spotify_track_url(track_url)
    if normalized_url != track_url:
        print(f"🔧 URL normalizada: {normalized_url}")

    if not is_valid_spotify_track_url(normalized_url):
        print("❌ URL inválida.")
        return

    output_dir = get_unique_output_folder()
    output_dir.mkdir(exist_ok=True)

    print(f"\n📥 Procesando: {normalized_url}")
    print(f"📁 Carpeta de destino: {output_dir}")
    print("-" * 50)

    fallback_downloads: list[str] = []
    success = process_track_with_retries(normalized_url, output_dir, spotdl_args, fallback_list=fallback_downloads)

    if success:
        print("\n🎉 Procesamiento completado con éxito")
        for mp3_file in output_dir.glob("*.mp3"):
            size_mb = mp3_file.stat().st_size / (1024 * 1024)
            print(f"📁 {mp3_file.name} ({size_mb:.2f} MB)")

        if fallback_downloads:
            print("\n⚠️ Pistas procesadas con yt-dlp; verifícalas manualmente:")
            for name in fallback_downloads:
                print(f"   - {name}")
    else:
        print("\n💥 El procesamiento falló")


def read_track_urls_from_file(file_path: Path) -> Optional[list[str]]:
    """Reads and validates Spotify track URLs from a text file."""
    if not file_path.exists():
        print(f"❌ El archivo {file_path} no existe")
        return None

    try:
        urls: list[str] = []
        invalid_urls: list[tuple[int, str]] = []
        seen_urls: set[str] = set()

        for line_num, raw_line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if is_valid_spotify_track_url(line):
                normalized_url = normalize_spotify_track_url(line)
                if normalized_url in seen_urls:
                    print(f"⚠️ URL duplicada en línea {line_num}: {normalized_url}")
                    continue

                seen_urls.add(normalized_url)
                urls.append(normalized_url)
            else:
                invalid_urls.append((line_num, line))

        if invalid_urls:
            print("❌ URLs inválidas encontradas:")
            for line_num, url in invalid_urls:
                print(f"   Línea {line_num}: {url}")
            return None

        if not urls:
            print("❌ No se encontraron URLs válidas en el archivo")
            return None

        print(f"✅ Se encontraron {len(urls)} URLs válidas")
        return urls

    except Exception as exc:
        print(f"❌ Error leyendo el archivo: {exc}")
        return None


def process_multiple_tracks(spotdl_args: Optional[Sequence[str]] = None) -> None:
    urls = read_track_urls_from_file(TRACK_LIST_FILE)
    if not urls:
        return

    OUTPUT_DIR.mkdir(exist_ok=True)

    print(f"\n🎵 Iniciando procesamiento de {len(urls)} canciones en la carpeta: {OUTPUT_DIR}")
    print("=" * 60)

    successful = 0
    failed = 0
    fallback_downloads: list[str] = []

    for idx, url in enumerate(urls, start=1):
        print(f"\n📥 [{idx}/{len(urls)}]")
        print("-" * 50)
        try:
            ok = process_track_with_retries(
                url,
                OUTPUT_DIR,
                spotdl_args=spotdl_args,
                fallback_list=fallback_downloads,
                track_number=idx,
            )
            if ok:
                successful += 1
                print(f"✅ Canción {idx} procesada con éxito")
            else:
                failed += 1
                print(f"❌ Canción {idx} falló")
        except Exception as exc:
            failed += 1
            print(f"💥 Error en la canción {idx}: {exc}")

    print("\n" + "=" * 60)
    print("📊 RESUMEN DE PROCESAMIENTO")
    print("=" * 60)
    print(f"• Total de canciones: {len(urls)}")
    print(f"• Procesadas correctamente: {successful}")
    print(f"• Fallidas: {failed}")

    if fallback_downloads:
        print("\n⚠️ Pistas procesadas con yt-dlp; verifícalas manualmente:")
        for name in fallback_downloads:
            print(f"   - {name}")


# -----------------------------------------------------------------------------
# Playlist export
# -----------------------------------------------------------------------------


def fetch_playlist_urls_with_spotify_api(playlist_url: str, credentials: tuple[str, str]) -> tuple[Optional[list[str]], Optional[str]]:
    playlist_id = extract_playlist_id(playlist_url)
    if not playlist_id:
        return None, "Invalid playlist URL"

    try:
        sp = make_spotify_client(credentials)
        track_urls: list[str] = []
        results = sp.playlist_tracks(playlist_id)

        while results:
            for item in results.get("items", []):
                track = item.get("track")
                if track and track.get("uri"):
                    track_urls.append(track["uri"].replace("spotify:track:", "https://open.spotify.com/track/"))

            next_url = results.get("next")
            results = sp.next(results) if next_url else None

        print(f"✅ Se encontraron {len(track_urls)} canciones en la playlist")
        return track_urls, None

    except Exception as exc:
        return None, f"Error obteniendo playlist mediante Spotify Web API: {exc}"


def fetch_playlist_urls_with_spotdl(playlist_url: str, spotdl_args: Optional[Sequence[str]] = None) -> tuple[Optional[list[str]], Optional[str]]:
    """Exports playlist track URLs using spotDL metadata, including default spotDL credentials."""
    try:
        print("🔎 Obteniendo metadata de playlist mediante spotDL...")

        with tempfile.TemporaryDirectory(prefix="spotpsync_") as temp_dir:
            metadata_file = Path(temp_dir) / "playlist.spotdl"
            command = ["spotdl", "save", playlist_url, "--save-file", str(metadata_file)]
            if spotdl_args:
                command.extend(spotdl_args)

            result = run_command(command, timeout=300)

            if result.returncode != 0:
                return None, extract_spotdl_error(result.stderr)

            if not metadata_file.exists():
                return None, "spotDL no generó el archivo de metadata .spotdl."

            raw_metadata = metadata_file.read_text(encoding="utf-8", errors="replace")

        track_urls = extract_track_urls_from_text(raw_metadata)

        if not track_urls:
            try:
                metadata = json.loads(raw_metadata)
                track_urls = extract_track_urls_from_spotdl_metadata(metadata)
            except json.JSONDecodeError as exc:
                return None, f"spotDL generó metadata, pero no se pudo parsear como JSON: {exc}"

        if not track_urls:
            return None, (
                "spotDL generó metadata, pero no se encontraron IDs/URLs de tracks de Spotify. "
                "Usa credenciales propias de Spotify Developer para esta función."
            )

        print(f"✅ Se encontraron {len(track_urls)} canciones en la playlist")
        return track_urls, None

    except FileNotFoundError:
        return None, "spotdl no está instalado o no está disponible en el PATH."
    except subprocess.TimeoutExpired:
        return None, "Timeout obteniendo la playlist mediante spotdl."
    except Exception as exc:
        return None, f"Error obteniendo playlist mediante spotdl: {exc}"


def save_urls_to_file(urls: list[str], file_path: Path) -> bool:
    """Saves Spotify track URLs to a text file."""
    try:
        has_content = file_path.exists() and bool(file_path.read_text(encoding="utf-8").strip())

        if has_content:
            existing_lines = file_path.read_text(encoding="utf-8").splitlines()
            print(f"\n⚠️ El archivo {file_path.name} ya contiene {len(existing_lines)} líneas")
            print("¿Qué deseas hacer?")
            print("1. Sobrescribir el archivo")
            print("2. Añadir al final del archivo")
            print("3. Cancelar")

            while True:
                choice = input("\nElige una opción (1, 2 o 3): ").strip()
                if choice == "1":
                    mode = "w"
                    action = "sobrescrito"
                    break
                if choice == "2":
                    mode = "a"
                    action = "actualizado"
                    break
                if choice == "3":
                    print("❌ Operación cancelada")
                    return False
                print("❌ Opción no válida")
        else:
            mode = "w"
            action = "creado"

        with file_path.open(mode, encoding="utf-8") as file:
            if mode == "a" and has_content:
                file.write("\n")
            for url in urls:
                file.write(f"{url}\n")

        print(f"✅ Archivo {action} con {len(urls)} URLs")
        return True

    except Exception as exc:
        print(f"❌ Error guardando las URLs: {exc}")
        return False


def export_playlist_to_file() -> None:
    spotdl_args, credential_source = get_spotdl_credentials()

    print("\n" + "=" * 50)
    print("📋 EXPORTAR PLAYLIST A ARCHIVO")
    print("=" * 50)
    playlist_url = normalize_spotify_playlist_url(input("Introduce la URL de la playlist de Spotify: ").strip())

    if not playlist_url.startswith("https://open.spotify.com/playlist/"):
        print("❌ URL inválida. Debe ser una playlist de Spotify.")
        return

    print(f"🔗 URL de playlist: {playlist_url}")

    credentials = credentials_from_spotdl_args(spotdl_args)
    if credential_source == "default" or credentials is None:
        track_urls, error = fetch_playlist_urls_with_spotdl(playlist_url, spotdl_args)
    else:
        track_urls, error = fetch_playlist_urls_with_spotify_api(playlist_url, credentials)

    if error:
        print("\n❌ Error al obtener la playlist:")
        print(f"   {error}")
        return

    if not track_urls:
        print("❌ No se encontraron canciones en la playlist")
        return

    if save_urls_to_file(track_urls, TRACK_LIST_FILE):
        print("\n🎉 Playlist exportada correctamente")
        print(f"📁 Archivo: {TRACK_LIST_FILE.name}")
        print(f"🎵 Canciones: {len(track_urls)}")
    else:
        print("❌ Error exportando la playlist")


# -----------------------------------------------------------------------------
# Playlist synchronization
# -----------------------------------------------------------------------------


def match_local_file_to_track(mp3_file: Path, artist: str, title: str) -> bool:
    file_norm = normalize_song_name(mp3_file.stem)
    target_norm = normalize_song_name(f"{artist} {title}")

    if file_norm == target_norm:
        return True

    title_norm = normalize_song_name(title)
    if title_norm and title_norm in file_norm:
        return True

    ratio = SequenceMatcher(None, file_norm, target_norm).ratio()
    return ratio >= 0.85


def update_woas_if_needed(mp3_file: Path, expected_url: str) -> None:
    try:
        tags = ID3(mp3_file)
        woas = tags.get("WOAS")
        if not woas:
            return

        stored_id = extract_track_id(woas.url.strip())
        expected_id = extract_track_id(expected_url)
        if stored_id == expected_id:
            return

        tags.delall("WOAS")
        tags.add(WOAS(encoding=3, url=normalize_spotify_track_url(expected_url)))
        tags.save()
        print(f"🔧 WOAS actualizado en {mp3_file.name}")
    except Exception:
        return


def sync_spotify_playlist() -> None:
    credentials_data = get_spotify_api_credentials()
    if not credentials_data:
        return

    credentials, spotdl_args = credentials_data
    sp = make_spotify_client(credentials)

    print("\n" + "=" * 50)
    print("🔄 SINCRONIZAR PLAYLIST DE SPOTIFY")
    print("=" * 50)

    playlist_url = normalize_spotify_playlist_url(input("Introduce la URL de la playlist de Spotify: ").strip())
    local_folder = Path(input("Introduce la ruta de la carpeta local de la playlist: ").strip())

    if not playlist_url.startswith("https://open.spotify.com/playlist/"):
        print("❌ URL inválida. Debe ser una playlist de Spotify.")
        return

    if not local_folder.exists():
        print(f"❌ La carpeta {local_folder} no existe.")
        return

    playlist_id = extract_playlist_id(playlist_url)
    if not playlist_id:
        print("❌ No se pudo extraer el ID de la playlist.")
        return

    try:
        print("📡 Obteniendo información de la playlist...")
        playlist = sp.playlist(playlist_id)
        playlist_name = playlist["name"]
        results = sp.playlist_tracks(playlist_id)
    except Exception as exc:
        print(f"❌ Error obteniendo información de la playlist: {exc}")
        return

    tracks = results.get("items", [])
    while results.get("next"):
        results = sp.next(results)
        tracks.extend(results.get("items", []))

    all_tracks: list[dict] = []
    for index, item in enumerate(tracks, start=1):
        track = item.get("track")
        if not track:
            continue

        all_tracks.append(
            {
                "index": index,
                "artist": track["artists"][0]["name"],
                "title": track["name"],
                "url": track["external_urls"]["spotify"],
                "isrc": track.get("external_ids", {}).get("isrc"),
            }
        )

    print(f"🎧 Playlist con {len(all_tracks)} canciones encontradas\n")

    if normalize_folder_name(playlist_name) != normalize_folder_name(local_folder.name):
        print("⚠️ El nombre de la carpeta no coincide con el nombre de la playlist.")
        print(f"   Carpeta actual : {local_folder.name}")
        print(f"   Playlist nombre: {playlist_name}\n")

        response = input("¿Quieres renombrar la carpeta automáticamente? (s/n): ").strip().lower()
        if response == "s":
            try:
                new_path = local_folder.parent / playlist_name
                local_folder.rename(new_path)
                local_folder = new_path
                print(f"✅ Carpeta renombrada a: {playlist_name}\n")
            except Exception as exc:
                print(f"❌ Error renombrando carpeta: {exc}")
                return
        else:
            response = input("¿Quieres crear una carpeta nueva para esta playlist y usarla? (s/n): ").strip().lower()
            if response == "s":
                try:
                    new_path = local_folder.parent / playlist_name
                    new_path.mkdir(exist_ok=True)
                    local_folder = new_path
                    print(f"📁 Carpeta creada: {new_path}")
                except Exception as exc:
                    print(f"❌ No se pudo crear la carpeta: {exc}")
                    return
            else:
                print("↩️ Operación cancelada. Volviendo al menú principal.")
                return

    mp3_files = list(local_folder.glob("*.mp3"))
    assigned_files: set[Path] = set()
    found_matches: list[tuple[Path, int, str, str, Optional[str]]] = []

    print("🔎 Buscando coincidencias en la carpeta local...")

    files_with_tracknum: dict[Path, int] = {}
    for mp3_file in mp3_files:
        try:
            tags = EasyID3(mp3_file)
            current_num = tags.get("tracknumber", ["0"])[0]
            current_clean = str(current_num).split("/")[0] if current_num else "0"
            files_with_tracknum[mp3_file] = int(current_clean) if current_clean.isdigit() else 0
        except Exception:
            files_with_tracknum[mp3_file] = 0

    for mp3_file in mp3_files:
        if mp3_file in assigned_files:
            continue

        track_number = files_with_tracknum.get(mp3_file, 0)
        if 0 < track_number <= len(all_tracks):
            track_info = all_tracks[track_number - 1]
            if match_local_file_to_track(mp3_file, track_info["artist"], track_info["title"]):
                found_matches.append((mp3_file, track_number, track_info["artist"], track_info["title"], track_info["isrc"]))
                assigned_files.add(mp3_file)
                update_woas_if_needed(mp3_file, track_info["url"])

    for track_info in all_tracks:
        if track_info["index"] in {track_number for _, track_number, _, _, _ in found_matches}:
            continue

        for mp3_file in mp3_files:
            if mp3_file in assigned_files:
                continue

            if match_local_file_to_track(mp3_file, track_info["artist"], track_info["title"]):
                found_matches.append(
                    (mp3_file, track_info["index"], track_info["artist"], track_info["title"], track_info["isrc"])
                )
                assigned_files.add(mp3_file)
                update_woas_if_needed(mp3_file, track_info["url"])
                break

    assigned_track_numbers = {track_number for _, track_number, _, _, _ in found_matches}
    missing_tracks = [track for track in all_tracks if track["index"] not in assigned_track_numbers]

    print("\n🛠️ Actualizando metadatos...")
    updated_metadata = 0
    correct_track_numbers = 0
    changes_log: list[str] = []

    for mp3_file, track_number, _, _, isrc in found_matches:
        try:
            tags = EasyID3(mp3_file)
            current_num = tags.get("tracknumber", ["0"])[0]
        except Exception:
            current_num = "0"

        current_clean = str(current_num).split("/")[0] if current_num else "0"
        if current_clean == str(track_number):
            correct_track_numbers += 1
            print(f"✅ {mp3_file.name} → pista #{track_number} (ya correcta)")
            continue

        try:
            update_track_tags(mp3_file, track_number, isrc=isrc)
            updated_metadata += 1
            changes_log.append(f"{mp3_file.name}: {current_clean} → {track_number}")
            print(f"🛠️ {mp3_file.name} → pista actualizada {current_clean} → {track_number}")
        except Exception as exc:
            print(f"⚠️ No se pudo actualizar metadatos en {mp3_file.name}: {exc}")

    print("\n" + "=" * 50)
    print("📊 RESULTADO DE DETECCIÓN / ACTUALIZACIÓN")
    print("=" * 50)
    print(f"• Canciones en playlist: {len(all_tracks)}")
    print(f"• Canciones encontradas en carpeta: {len(found_matches)}")
    print(f"• Números de pista correctos: {correct_track_numbers}")
    print(f"• Números de pista actualizados: {updated_metadata}")
    print(f"• Canciones faltantes: {len(missing_tracks)}")

    if changes_log:
        print("\n📝 Cambios realizados:")
        for change in changes_log:
            print(f"   - {change}")

    matched_files = {file for file, _, _, _, _ in found_matches}
    extra_files = set(local_folder.glob("*.mp3")) - matched_files

    if extra_files:
        print(f"\n⚠️ Se encontraron {len(extra_files)} archivos no pertenecientes a la playlist:")
        for extra_file in extra_files:
            print(f"   - {extra_file.name}")

        response = input("¿Deseas BORRAR estos archivos extra? (s/n): ").strip().lower()
        if response == "s":
            for extra_file in extra_files:
                try:
                    extra_file.unlink()
                    print(f"🗑️ Borrado: {extra_file.name}")
                except Exception as exc:
                    print(f"❌ No se pudo borrar {extra_file.name}: {exc}")
        else:
            print("ℹ️ No se borraron archivos extra.")
    else:
        print("\n✅ No hay archivos extra.")

    if not missing_tracks:
        print("\n✅ Todas las canciones están sincronizadas.")
        return

    print("\n🎵 Canciones faltantes:")
    for track in missing_tracks:
        print(f"   [{track['index']:02}] {track['artist']} - {track['title']}")

    response = input("\n¿Deseas procesar las canciones faltantes? (s/n): ").strip().lower()
    if response != "s":
        print("\nℹ️ Procesamiento omitido por el usuario.")
        return

    print("\n⬇️ Procesando canciones faltantes...\n")
    existing_before = set(local_folder.glob("*.mp3"))

    for track in missing_tracks:
        print(f"🎵 [{track['index']:02}] {track['artist']} - {track['title']}")
        ok = process_track_with_retries(track["url"], local_folder, spotdl_args, track_number=track["index"])

        if ok:
            current_files = set(local_folder.glob("*.mp3"))
            new_files = list(current_files - existing_before)
            chosen_file = None

            if new_files:
                target_norm = normalize_song_name(f"{track['artist']} {track['title']}")
                chosen_file = max(
                    new_files,
                    key=lambda file: SequenceMatcher(None, normalize_song_name(file.stem), target_norm).ratio(),
                )

            if chosen_file:
                try:
                    update_track_tags(chosen_file, track["index"], track.get("isrc"))
                    print(f"✅ Metadato de pista actualizado para {chosen_file.name}")
                except Exception as exc:
                    print(f"⚠️ No se pudo escribir tag en {chosen_file.name}: {exc}")

            existing_before = current_files

    print("\n🎉 Sincronización completada.")


# -----------------------------------------------------------------------------
# Setup and dependency management
# -----------------------------------------------------------------------------


def create_credentials_file() -> None:
    if CREDENTIALS_FILE.exists():
        return

    CREDENTIALS_FILE.write_text("YOUR_CLIENT_ID_HERE\nYOUR_CLIENT_SECRET_HERE\n", encoding="utf-8")
    print(f"📄 Archivo '{CREDENTIALS_FILE.name}' creado")


def create_track_list_template_file() -> None:
    if TRACK_LIST_FILE.exists():
        return

    if LANG == "en":
        example_content = """# spotify-track-list.txt
# Place one Spotify track URL per line.
# Lines starting with # are comments.

# https://open.spotify.com/track/<track_id>
# https://open.spotify.com/track/<track_id>
# https://open.spotify.com/track/<track_id>

# More tracks...
"""
    else:
        example_content = """# Archivo spotify-track-list.txt
# Coloca una URL de Spotify por línea.
# Las líneas que comienzan con # son comentarios.

# https://open.spotify.com/track/<track_id>
# https://open.spotify.com/track/<track_id>
# https://open.spotify.com/track/<track_id>

# Más canciones...
"""
    TRACK_LIST_FILE.write_text(example_content, encoding="utf-8")
    print(f"📄 Archivo '{TRACK_LIST_FILE.name}' creado con ejemplo")


def check_and_update_dependencies() -> None:
    print("\n🔍 Comprobando versiones de dependencias...")

    versions: dict[str, Optional[str]] = {}
    for package_command, display_name in [("spotdl", "spotDL"), ("yt-dlp", "yt-dlp")]:
        try:
            result = run_command([package_command, "--version"], timeout=10)
            if result.returncode == 0:
                versions[package_command] = result.stdout.strip()
                print(f"✅ {display_name} versión instalada: {versions[package_command]}")
            else:
                versions[package_command] = None
                print(f"❌ Error obteniendo versión de {display_name}")
        except Exception as exc:
            versions[package_command] = None
            print(f"❌ Error obteniendo versión de {display_name}: {exc}")

    try:
        outdated_result = run_command([sys.executable, "-m", "pip", "list", "--outdated"], timeout=30)
        outdated_packages = outdated_result.stdout.lower()
        spotdl_outdated = "spotdl" in outdated_packages
        ytdlp_outdated = "yt-dlp" in outdated_packages
    except Exception as exc:
        print(f"❌ Error comprobando actualizaciones: {exc}")
        spotdl_outdated = False
        ytdlp_outdated = False

    print("⚠️ spotDL tiene una versión más reciente disponible." if spotdl_outdated else "✅ spotDL está actualizado.")
    print("⚠️ yt-dlp tiene una versión más reciente disponible." if ytdlp_outdated else "✅ yt-dlp está actualizado.")

    if not spotdl_outdated and not ytdlp_outdated:
        print("\n🎉 Todas las dependencias están actualizadas.")
        return

    while True:
        response = input("\n¿Quieres actualizar las dependencias desactualizadas? (s/n): ").strip().lower()
        if response in {"s", "si", "sí"}:
            if spotdl_outdated:
                print("Actualizando spotDL...")
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--upgrade", "git+https://github.com/spotDL/spotify-downloader.git"],
                    timeout=300,
                )
            if ytdlp_outdated:
                print("Actualizando yt-dlp...")
                subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"], timeout=300)
            break
        if response in {"n", "no"}:
            print("Actualización cancelada.")
            break
        print("Por favor, responde 's' o 'n'.")


# -----------------------------------------------------------------------------
# Main menu
# -----------------------------------------------------------------------------


def main_menu() -> None:
    select_language()
    create_credentials_file()
    create_track_list_template_file()

    while True:
        print("\n" + "=" * 50)
        print("🎵 SpotPSync Tool")
        print("=" * 50)
        print("1. Procesar una canción individual")
        print("2. Procesar múltiples canciones desde archivo")
        print("3. Exportar playlist a archivo")
        print("4. Sincronizar playlist local con Spotify")
        print("5. Comprobar y actualizar dependencias")
        print("6. Salir")

        option = input("\nElige una opción (1, 2, 3, 4, 5 o 6): ").strip()

        if option == "1":
            process_single_track()
        elif option == "2":
            spotdl_args, _ = get_spotdl_credentials()
            process_multiple_tracks(spotdl_args)
        elif option == "3":
            export_playlist_to_file()
        elif option == "4":
            sync_spotify_playlist()
        elif option == "5":
            check_and_update_dependencies()
        elif option == "6":
            print("👋 Hasta luego")
            break
        else:
            print("❌ Opción no válida")

        input("\nPresiona Enter para continuar...")


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n⏹️ Programa cancelado por el usuario")
    except Exception as exc:
        logger.error("Error: %s", exc)
    finally:
        print("\nPrograma terminado")
