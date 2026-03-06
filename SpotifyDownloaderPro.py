import os
import time
import json
import logging
import re
from difflib import SequenceMatcher
import sys
from pathlib import Path
import subprocess, shlex
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from mutagen.easyid3 import EasyID3
import unicodedata
from mutagen.id3 import ID3, TRCK, WOAS, TSRC
import mutagen

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_spotdl_error(stderr_output):
    """Extrae y formatea el error específico de SpotDL de manera más robusta"""
    if not stderr_output:
        return "Error desconocido (sin output de error)"
    
    lines = stderr_output.split('\n')
    error_lines = []
    
    # Buscar líneas de error específicas
    for line in lines:
        line_lower = line.lower()
        # Filtrar líneas de error relevantes pero excluir tracebacks completos
        if (any(keyword in line_lower for keyword in ['error', 'exception', 'failed', 'keyerror', 'timeout']) and
            'traceback' not in line_lower and 'file "' not in line_lower):
            if line.strip() and not line.startswith('  ') and not line.startswith('+--'):
                error_lines.append(line.strip())
    
    # Si no encontramos líneas de error específicas, buscar mensajes clave
    if not error_lines:
        for line in lines:
            if "unable to find" in line.lower() or "keyerror" in line.lower():
                error_lines.append(line.strip())
    
    # Si todavía no hay errores, tomar las últimas líneas
    if not error_lines and lines:
        # Tomar las últimas 3 líneas que tengan contenido
        error_lines = [line.strip() for line in lines[-3:] if line.strip()]
    
    return " | ".join(error_lines[:2])  # Devolver máximo 2 líneas de error

def check_spotdl_installation():
    """Verifica si spotdl está instalado correctamente"""
    try:
        result = subprocess.run(["spotdl", "--version"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ SpotDL versión: {result.stdout.strip()}")
            return True
        else:
            print("❌ SpotDL instalado pero no funciona correctamente")
            print(f"Error: {result.stderr}")
            return False
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        print("❌ SpotDL no está instalado")
        return False

def install_spotdl():
    """Instala o actualiza spotdl"""
    print("🔄 Instalando/actualizando SpotDL...")
    try:
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "--upgrade", "git+https://github.com/spotDL/spotify-downloader.git"
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            print("✅ SpotDL instalado/actualizado correctamente")
            return True
        else:
            print(f"❌ Error instalando SpotDL: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Timeout durante la instalación")
        return False

def get_song_info(spotify_url, spotdl_args=None):
    """Obtiene información de la canción usando spotdl search"""
    try:
        search_cmd = [
            "spotdl", "search", spotify_url,
            "--print", "json"
        ]
        
        if spotdl_args:
            search_cmd += spotdl_args
        
        result = subprocess.run(search_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and result.stdout.strip():
            try:
                song_info = json.loads(result.stdout)
                artist = song_info['artists'][0]['name'] if song_info.get('artists') else "Unknown"
                title = song_info.get('name', 'Unknown Track')
                return f"{artist} {title} audio"
            except json.JSONDecodeError:
                print("❌ No se pudo decodificar la información de la canción")
        return None
    except Exception as e:
        print(f"❌ Error obteniendo información: {e}")
        return None

def download_with_yt_dlp(spotify_url, output_path, spotdl_args=None):
    """
    Intenta descargar usando yt-dlp cuando SpotDL falla.
    Usa el nombre real de Spotify para buscar en YouTube y valida la descarga.
    """

    print("🔄 Intentando con yt-dlp como alternativa...")

    success = False
    video_url = None

    # Asegurar directorio
    output_dir = Path(output_path)
    output_dir.mkdir(exist_ok=True)

    # Inicializar cliente Spotify si no existe
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
        with open("spotify_client_data.txt") as f:
            lines = [line.strip() for line in f if line.strip()]
        client_id, client_secret = lines[:2]
        sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=client_id, client_secret=client_secret))
    except Exception as e:
        print(f"⚠️ No se pudo inicializar cliente Spotify: {e}")
        sp = None

    # Intentar obtener nombre correcto de la canción
    clean_query = "unknown track"
    if sp:
        try:
            track_info = sp.track(spotify_url)
            artist = track_info['artists'][0]['name']
            title = track_info['name']
            clean_query = f"{artist} - {title}"
            print(f"🎯 Nombre obtenido de Spotify: {clean_query}")
        except Exception as e:
            print(f"⚠️ No se pudo obtener información de Spotify: {e}")

    # Buscar en YouTube con el nombre real
    search_query = f"ytsearch5:{clean_query}"
    print(f"🔍 Buscando en YouTube: {search_query}")

    try:
        cmd_info = f'yt-dlp --dump-json --flat-playlist "{search_query}"'
        result = subprocess.run(shlex.split(cmd_info), capture_output=True, text=True)
        results = [json.loads(line) for line in result.stdout.strip().splitlines() if line.strip()]

        if not results:
            print("❌ No se encontraron resultados en YouTube.")
            return False

        # Elegir el primer resultado como más relevante
        best_match = results[0]
        video_url = f"https://www.youtube.com/watch?v={best_match['id']}"
        print(f"🏆 Mejor coincidencia: {best_match['title']}")
        print(f"🔗 URL seleccionada: {video_url}")

        # Descargar
        yt_dlp_cmd = [
            "yt-dlp", "-x", "--audio-format", "mp3",
            "-o", str(output_dir / "%(title)s.%(ext)s"),
            video_url
        ]
        print("⬇️ Descargando con yt-dlp...")
        download_proc = subprocess.run(yt_dlp_cmd, capture_output=True, text=True)

        # Verificar resultado
        if download_proc.returncode == 0:
            mp3_files = list(output_dir.glob("*.mp3"))
            if mp3_files:
                latest_file = max(mp3_files, key=lambda x: x.stat().st_mtime)
                size_mb = latest_file.stat().st_size / (1024 * 1024)
                if size_mb > 0.1:
                    print(f"✅ Descarga completada correctamente con yt-dlp: {latest_file.name} ({size_mb:.2f} MB)")
                    success = True
                else:
                    print("❌ El archivo descargado es demasiado pequeño, probablemente corrupto.")
            else:
                print("❌ yt-dlp no generó ningún archivo MP3.")
        else:
            print(f"❌ Error ejecutando yt-dlp: {download_proc.stderr.strip()}")

    except Exception as e:
        print(f"❌ Error en la descarga con yt-dlp: {e}")

    return success

def normalize_spotify_url(url):
    """Normaliza URLs de Spotify"""
    pattern = r'https://open\.spotify\.com/(?:intl-[a-z]{2}/)?track/([a-zA-Z0-9]+)'
    match = re.search(pattern, url)
    if match:
        track_id = match.group(1)
        return f"https://open.spotify.com/track/{track_id}"
    return url

def normalize_name(name: str) -> str:
    """
    Normaliza nombres para comparación:
    - sin mayúsculas
    - sin acentos
    - símbolos ilegales eliminados
    - espacios compactados
    """
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    name = name.lower()

    # quitar símbolos que Windows no permite
    name = re.sub(r'[<>:"/\\|?*]', "", name)

    # quitar paréntesis extra y contenido redundante
    name = re.sub(r"\([^)]*\)", "", name)

    # compactar espacios
    name = re.sub(r"\s+", " ", name).strip()
    return name

def load_full_id3_tags(mp3_path):
    """Carga etiquetas ID3 completas usando mutagen.ID3."""
    try:
        return ID3(mp3_path)
    except mutagen.id3.ID3NoHeaderError:
        tags = ID3()
        tags.save(mp3_path)
        return ID3(mp3_path)

def update_track_tags(mp3_path, track_number, isrc=None):
    """
    Actualiza SOLO:
      - TRCK (número de pista)
      - TSRC (ISRC)
    Sin tocar nada más.
    """
    tags = load_full_id3_tags(mp3_path)

    tags.setall("TRCK", [TRCK(encoding=3, text=str(track_number))])

    if isrc:
        tags.setall("TSRC", [TSRC(encoding=3, text=isrc)])

    tags.save(mp3_path)

def is_valid_spotify_track_url(url):
    """Verifica si una URL es de una canción de Spotify válida"""
    normalized_url = normalize_spotify_url(url.strip())
    return normalized_url.startswith('https://open.spotify.com/track/')

def load_credentials_from_file():
    """Carga las credenciales desde el archivo"""
    credentials_file = Path("spotify_client_data.txt")
    if credentials_file.exists():
        try:
            with open(credentials_file, 'r') as f:
                lines = f.readlines()
                client_id = lines[0].strip() if len(lines) > 0 else ""
                client_secret = lines[1].strip() if len(lines) > 1 else ""
                
                if client_id and client_secret:
                    return ["--client-id", client_id, "--client-secret", client_secret]
        except Exception as e:
            logger.error(f"Error leyendo archivo de credenciales: {e}")
    return []

def get_spotdl_credentials():
    """Pregunta al usuario qué credenciales usar"""
    print("\n" + "="*50)
    print("🔐 CONFIGURACIÓN DE CREDENCIALES")
    print("="*50)
    print("1. Usar credenciales del archivo 'spotify_client_data.txt'")
    print("2. Usar credenciales por defecto de spotdl")
    print("3. Ingresar credenciales manualmente")
    
    while True:
        opcion = input("\nElige una opción (1, 2 o 3): ").strip()
        
        if opcion == "1":
            creds = load_credentials_from_file()
            if creds:
                print("✅ Usando credenciales del archivo")
                return creds
            else:
                print("❌ No se encontraron credenciales válidas en el archivo")
        elif opcion == "2":
            print("✅ Usando credenciales por defecto de spotdl")
            return []
        elif opcion == "3":
            client_id = input("Introduce tu Spotify Client ID: ").strip()
            client_secret = input("Introduce tu Spotify Client Secret: ").strip()
            if client_id and client_secret:
                print("✅ Usando credenciales manuales")
                return ["--client-id", client_id, "--client-secret", client_secret]
            else:
                print("❌ Credenciales inválidas")
        else:
            print("❌ Opción no válida")

def get_expected_filename(url, output_path, spotdl_args=None):
    """Intenta predecir el nombre del archivo que debería generarse"""
    try:
        # Primero intentar obtener información de la canción para predecir el nombre
        search_cmd = ["spotdl", "search", url, "--print", "json"]
        if spotdl_args:
            search_cmd += spotdl_args
        
        result = subprocess.run(search_cmd, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0 and result.stdout.strip():
            song_info = json.loads(result.stdout)
            artist = song_info['artists'][0]['name'] if song_info.get('artists') else "Unknown"
            title = song_info.get('name', 'Unknown Track')
            expected_filename = f"{artist} - {title}.mp3"
            # Limpiar caracteres inválidos para nombres de archivo
            expected_filename = re.sub(r'[<>:"/\\|?*]', '', expected_filename)
            return expected_filename
    except:
        pass
    
    # Si no se puede obtener info, no devolver un nombre de archivo existente
    # ya que podría ser de una canción anterior
    return None

def verify_download_completion(output_path, expected_filename=None, existing_files=None):
    """Verifica que la descarga se completó correctamente y el archivo existe"""
    # Esperar un poco para que el sistema de archivos se actualice
    time.sleep(2)
    
    # Si existing_files no se proporciona, obtener todos los archivos actuales
    if existing_files is None:
        existing_files = set(output_path.glob("*.mp3")) if output_path.exists() else set()
    
    # Buscar todos los archivos MP3 en la carpeta
    current_files = set(output_path.glob("*.mp3")) if output_path.exists() else set()
    
    # Encontrar archivos nuevos (creados después de empezar la descarga)
    new_files = current_files - existing_files
    
    if not current_files:
        print("❌ VERIFICACIÓN: No se encontraron archivos MP3 después de la descarga")
        return False
    
    # Si tenemos un nombre esperado, buscar ese archivo específicamente
    if expected_filename:
        for mp3_file in current_files:
            if mp3_file.name == expected_filename:
                file_size = mp3_file.stat().st_size / (1024 * 1024)
                if file_size > 0.1:
                    # VERIFICAR CRÍTICAMENTE que el archivo es NUEVO, no preexistente
                    if mp3_file in new_files:
                        print(f"✅ VERIFICACIÓN: Archivo esperado encontrado - {mp3_file.name} ({file_size:.2f} MB)")
                        return True
                    else:
                        print(f"⚠️  VERIFICACIÓN: Archivo esperado encontrado pero NO ES NUEVO - {mp3_file.name} ({file_size:.2f} MB)")
                        return False
        
        print(f"❌ VERIFICACIÓN: No se encontró el archivo esperado '{expected_filename}'")
        print(f"   Archivos encontrados: {[f.name for f in current_files]}")
        return False
    
    # Si no tenemos nombre esperado, buscar entre los archivos nuevos
    if new_files:
        # Tomar el archivo más reciente de los nuevos
        latest_new_file = max(new_files, key=lambda x: x.stat().st_mtime)
        file_size = latest_new_file.stat().st_size / (1024 * 1024)
        if file_size > 0.1:
            print(f"✅ VERIFICACIÓN: Nuevo archivo encontrado - {latest_new_file.name} ({file_size:.2f} MB)")
            return True
        else:
            print(f"❌ VERIFICACIÓN: Nuevo archivo encontrado pero demasiado pequeño - {latest_new_file.name} ({file_size:.2f} MB)")
            return False
    
    # Si no hay archivos nuevos, verificar el más reciente en general
    latest_file = max(current_files, key=lambda x: x.stat().st_mtime)
    file_size = latest_file.stat().st_size / (1024 * 1024)
    if file_size > 0.1:
        print(f"⚠️  VERIFICACIÓN: No hay archivos nuevos, usando el más reciente - {latest_file.name} ({file_size:.2f} MB)")
        # Añadir verificación adicional para asegurar que es el archivo correcto
        return True
    
    print("❌ VERIFICACIÓN: Los archivos MP3 encontrados son demasiado pequeños o están corruptos")
    print(f"   Archivos: {[f.name for f in current_files]}")
    return False

def fetch_playlist_urls(playlist_url, spotdl_args=None):
    """Obtiene todas las URLs de una playlist de Spotify usando la API de Spotify"""
    import re
    
    # Extract playlist_id from URL
    match = re.search(r'/playlist/([a-zA-Z0-9]+)', playlist_url)
    if not match:
        error_msg = "Invalid playlist URL"
        print(f"❌ {error_msg}")
        return None, error_msg
    playlist_id = match.group(1)
    
    # Get credentials from spotdl_args
    client_id = None
    client_secret = None
    if spotdl_args:
        i = 0
        while i < len(spotdl_args):
            if spotdl_args[i] == '--client-id' and i + 1 < len(spotdl_args):
                client_id = spotdl_args[i + 1]
                i += 2
            elif spotdl_args[i] == '--client-secret' and i + 1 < len(spotdl_args):
                client_secret = spotdl_args[i + 1]
                i += 2
            else:
                i += 1
    
    if not client_id or not client_secret:
        error_msg = "Spotify credentials not provided in spotdl_args"
        print(f"❌ {error_msg}")
        return None, error_msg
    
    # Authenticate with Spotify
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=client_id, client_secret=client_secret))
    
    try:
        # Get playlist tracks (handle pagination)
        song_urls = []
        results = sp.playlist_tracks(playlist_id)
        while results:
            for item in results['items']:
                if item['track']:  # Some items might be None
                    uri = item['track']['uri']
                    url = uri.replace('spotify:track:', 'https://open.spotify.com/track/')
                    song_urls.append(url)
            if results['next']:
                results = sp.next(results)
            else:
                break
        
        print(f"✅ Se encontraron {len(song_urls)} canciones en la playlist")
        return song_urls, None
    
    except Exception as e:
        error_msg = f"Error obteniendo playlist: {str(e)}"
        print(f"❌ {error_msg}")
        return None, error_msg

def save_urls_to_file(urls, file_path):
    """Guarda las URLs en el archivo, preguntando antes si ya existe contenido"""
    try:
        # Verificar si el archivo ya tiene contenido
        file_exists = file_path.exists()
        has_content = False
        
        if file_exists:
            with open(file_path, 'r', encoding='utf-8') as f:
                existing_content = f.read().strip()
                has_content = bool(existing_content)
        
        # Preguntar al usuario si quiere sobrescribir
        if has_content:
            print(f"\n⚠️ El archivo {file_path.name} ya contiene {len(existing_content.splitlines())} URLs")
            print("¿Qué deseas hacer?")
            print("1. Sobrescribir el archivo (eliminar todo el contenido anterior)")
            print("2. Añadir al final del archivo")
            print("3. Cancelar")
            
            while True:
                choice = input("\nElige una opción (1, 2 o 3): ").strip()
                if choice == "1":
                    mode = 'w'
                    action = "sobrescrito"
                    break
                elif choice == "2":
                    mode = 'a'
                    action = "actualizado"
                    break
                elif choice == "3":
                    print("❌ Operación cancelada")
                    return False
                else:
                    print("❌ Opción no válida")
        else:
            mode = 'w'
            action = "creado"
        
        # Guardar las URLs
        with open(file_path, mode, encoding='utf-8') as f:
            if mode == 'a' and has_content:
                f.write('\n')  # Añadir línea en blanco antes de añadir
            for url in urls:
                f.write(url + '\n')
        
        print(f"✅ Archivo {action} con {len(urls)} URLs")
        return True
        
    except Exception as e:
        print(f"❌ Error guardando las URLs: {e}")
        return False

def export_playlist_to_file():
    """Exporta las canciones de una playlist al archivo songs-to-download.txt"""
    spotdl_args = get_spotdl_credentials()
    
    print("\n" + "="*50)
    print("📋 EXPORTAR PLAYLIST A ARCHIVO")
    print("="*50)
    playlist_url = input("Introduce la URL de la playlist de Spotify: ").strip()
    
    # Validar que es una URL de playlist
    if not playlist_url.startswith('https://open.spotify.com/playlist/'):
        print("❌ URL inválida. Debe ser una playlist de Spotify.")
        return
    
    print(f"🔗 URL de playlist: {playlist_url}")
    
    # Obtener URLs de la playlist usando el nuevo método
    song_urls, error = fetch_playlist_urls(playlist_url, spotdl_args)
    
    if error:
        print(f"\n❌ Error al obtener la playlist:")
        print(f"   {error}")
        return
    
    if not song_urls:
        print("❌ No se encontraron canciones en la playlist")
        return
    
    # Guardar en archivo
    songs_file = Path("songs-to-download.txt")
    if save_urls_to_file(song_urls, songs_file):
        print(f"\n🎉 ¡Playlist exportada correctamente!")
        print(f"📁 Archivo: {songs_file.name}")
        print(f"🎵 Canciones: {len(song_urls)}")
    else:
        print("❌ Error exportando la playlist")

def get_song_info_for_display(url, spotdl_args=None):
    """Obtiene información de la canción para mostrar antes de descargar"""
    try:
        search_cmd = ["spotdl", "search", url, "--print", "json"]
        if spotdl_args:
            search_cmd += spotdl_args
        
        result = subprocess.run(search_cmd, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0 and result.stdout.strip():
            song_info = json.loads(result.stdout)
            artist = song_info['artists'][0]['name'] if song_info.get('artists') else "Unknown"
            title = song_info.get('name', 'Unknown Track')
            return f"{artist} - {title}"
    except:
        pass
    
    return None

def download_song_with_detailed_errors(url, output_path, spotdl_args=None, timeout=300, fallback_list=None, track_number=None):
    """
    Descarga una canción mostrando errores detallados con reintentos y verificación.
    Si SpotDL falla, usa yt-dlp con el nombre real de Spotify y marca la canción como 'fallback'.
    """
    song_info = get_song_info_for_display(url, spotdl_args)
    if song_info:
        print(f"🎵 Intentando descargar: {song_info}")
    else:
        print(f"🎵 Intentando descargar URL: {url}")
    
    max_retries = 3
    retry_delay = 5
    expected_filename = get_expected_filename(url, output_path, spotdl_args)

    if expected_filename:
        print(f"📁 Archivo esperado: {expected_filename}")

    existing_files = set(output_path.glob("*.mp3")) if output_path.exists() else set()
    
    # --- 🔁 Intentar con SpotDL ---
    for attempt in range(max_retries):
        try:
            print(f"⏳ Ejecutando SpotDL (intento {attempt + 1}/{max_retries})...")
            cmd = [
                "spotdl", "download", url,
                "--output", str(output_path / "{artist} - {title}.{output-ext}"),
                "--format", "mp3", "--lyrics", "genius"
            ]
            if spotdl_args:
                cmd += spotdl_args

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.returncode == 0:
                time.sleep(3)
                current_files = set(output_path.glob("*.mp3"))
                new_files = current_files - existing_files
                if len(new_files) == 1:
                    new_file = next(iter(new_files))
                    size_mb = new_file.stat().st_size / (1024 * 1024)
                    if size_mb > 0.1:
                        print(f"✅ Descarga correcta con SpotDL: {new_file.name} ({size_mb:.2f} MB)")
                        if track_number:
                            try:
                                update_track_tags(str(new_file), track_number)
                                print(f"🏷️ Metadato TRCK actualizado a {track_number}")
                            except Exception as e:
                                print(f"⚠️ No se pudo actualizar TRCK: {e}")
                        return True
                print("⚠️ SpotDL reportó éxito pero la verificación falló, reintentando...")
            else:
                print(f"⚠️ Error SpotDL: {extract_spotdl_error(result.stderr)}")
            time.sleep(retry_delay)
        except subprocess.TimeoutExpired:
            print(f"⏰ Timeout (intento {attempt+1}), reintentando...")
            time.sleep(retry_delay)
        except Exception as e:
            print(f"⚠️ Error inesperado: {e}")
            time.sleep(retry_delay)

    # --- 🔄 Si SpotDL falla, probar con yt-dlp ---
    print("🔄 Todos los intentos con SpotDL fallaron, usando yt-dlp...")

    # Obtener nombre real desde Spotify (para renombrar)
    track_name = "Unknown"
    artist_name = "Unknown"
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
        with open("spotify_client_data.txt") as f:
            lines = [line.strip() for line in f if line.strip()]
        client_id, client_secret = lines[:2]
        sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=client_id, client_secret=client_secret))
        track_info = sp.track(url)
        artist_name = track_info['artists'][0]['name']
        track_name = track_info['name']
    except Exception as e:
        print(f"⚠️ No se pudo obtener info de Spotify: {e}")

    clean_query = f"{artist_name} - {track_name}"
    yt_success = download_with_yt_dlp(url, output_path, spotdl_args)

    if yt_success:
        mp3_files: list[Path] = list(output_path.glob("*.mp3"))
        if mp3_files:
            latest_file: Path = max(mp3_files, key=lambda x: x.stat().st_mtime)
            new_name = f"{clean_query}.mp3"
            safe_name = re.sub(r'[<>:"/\\|?*]', '', new_name)
            new_path = output_path / safe_name
            try:
                # Si el archivo final ya existe, borrar duplicado y NO fallar
                if new_path.exists():
                    print("ℹ️ El archivo correcto ya existe, se elimina el duplicado descargado.")
                    try:
                        latest_file.unlink()  # borrar el archivo nuevo duplicado
                    except:
                        pass

                    # Registrar como éxito igualmente
                    if fallback_list is not None:
                        fallback_list.append(clean_query)

                    print(f"👍 Se mantuvo el archivo existente: {new_path.name}")
                    return True

                # Si no existe, renombrar normalmente
                try:
                    latest_file.rename(new_path)
                    print(f"✅ Archivo renombrado a: {safe_name}")
                except Exception as e:
                    print(f"⚠️ No se pudo renombrar el archivo: {e}")
                    new_path = latest_file
            except Exception as e:
                print(f"⚠️ No se pudo renombrar el archivo: {e}")
                new_path = latest_file  # usar el nombre original si no se pudo renombrar

            # 🔸 Agregar a la lista de fallback ANTES de retornar
            if fallback_list is not None:
                fallback_list.append(clean_query)
                print(f"📋 Añadida a la lista de verificación manual: {clean_query}")

            print(f"✅ Descarga alternativa exitosa: {clean_query}")
            if track_number:
                try:
                    update_track_tags(str(new_path), track_number)
                    print(f"🏷️ Metadato TRCK actualizado a {track_number}")
                except Exception as e:
                    print(f"⚠️ No se pudo actualizar TRCK: {e}")
            return True


        print("❌ Falló incluso con yt-dlp")
        return False

def read_songs_from_file(file_path):
    """Lee y valida las URLs del archivo songs-to-download.txt"""
    try:
        if not file_path.exists():
            print(f"❌ El archivo {file_path} no existe")
            return None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Filtrar líneas vacías y comentarios
        urls = []
        invalid_urls = []
        seen_urls = set()  # Para detectar duplicados
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if is_valid_spotify_track_url(line):
                normalized_url = normalize_spotify_url(line)
                
                # Verificar si la URL ya fue procesada
                if normalized_url in seen_urls:
                    print(f"⚠️  URL duplicada en línea {line_num}: {normalized_url}")
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
        
        print(f"✅ Se encontraron {len(urls)} URLs válidas (se omitieron {len(lines) - len(urls) - len(invalid_urls)} duplicados)")
        return urls
        
    except Exception as e:
        print(f"❌ Error leyendo el archivo: {e}")
        return None

def download_multiple_songs(spotdl_args=None):
    file_path = Path("songs-to-download.txt")
    if not file_path.exists():
        print("❌ No se encontró el archivo 'songs-to-download.txt'")
        return

    output_dir = Path("downloads")
    output_dir.mkdir(exist_ok=True)

    with open(file_path, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    urls = list(dict.fromkeys(urls))
    print(f"📖 Leyendo canciones desde: {file_path.name}")
    print(f"✅ Se encontraron {len(urls)} URLs válidas (se omitieron duplicados)\n")

    print(f"🎵 Iniciando descarga de {len(urls)} canciones en la carpeta: {output_dir}")
    print("=" * 60)

    successful = 0
    failed = 0
    fallback_downloads = []  # 🔹 lista global persistente

    for idx, url in enumerate(urls, start=1):
        print(f"\n📥 [{idx}/{len(urls)}]")
        print("--------------------------------------------------")
        try:
            ok = download_song_with_detailed_errors(url, output_dir, spotdl_args=spotdl_args, fallback_list=fallback_downloads, track_number=idx)
            if ok:
                successful += 1
                print(f"✅ Canción {idx} descargada con éxito")
            else:
                failed += 1
                print(f"❌ Canción {idx} falló")
        except Exception as e:
            failed += 1
            print(f"💥 Error en la canción {idx}: {e}")

    print("\n" + "=" * 60)
    print("📊 RESUMEN DE DESCARGA")
    print("=" * 60)
    print(f"• Total de canciones: {len(urls)}")
    print(f"• Descargas exitosas: {successful}")
    print(f"• Descargas fallidas: {failed}")
    print(f"• Archivos nuevos descargados: {successful}")

    # 🔸 Mostrar lista de canciones descargadas con yt-dlp
    if fallback_downloads:
        print("\n⚠️ Canciones descargadas con yt-dlp (verifícalas manualmente):")
        for name in fallback_downloads:
            print(f"   - {name}")

def download_single_song():
    """Función principal para descargar una canción individual"""
    spotdl_args = get_spotdl_credentials()
    
    print("\n" + "="*50)
    print("🎵 DESCARGA DE CANCIÓN INDIVIDUAL")
    print("="*50)
    song_url = input("Introduce la URL de la canción de Spotify: ").strip()
    
    normalized_url = normalize_spotify_url(song_url)
    if normalized_url != song_url:
        print(f"🔧 URL normalizada: {normalized_url}")
    
    if not normalized_url.startswith('https://open.spotify.com/track/'):
        print("❌ URL inválida.")
        return
    
    # Obtener carpeta de descarga única
    output_dir = get_unique_download_folder()
    output_dir.mkdir(exist_ok=True)
    
    print(f"\n📥 Descargando: {normalized_url}")
    print(f"📁 Carpeta de destino: {output_dir}")
    print("-" * 50)
    
    fallback_downloads = []
    success = download_song_with_detailed_errors(normalized_url, output_dir, spotdl_args, fallback_list=fallback_downloads)
    
    if success:
        print("\n🎉 ¡Descarga completada con éxito!")
        mp3_files = list(output_dir.glob("*.mp3"))
        if mp3_files:
            for mp3_file in mp3_files:
                file_size = mp3_file.stat().st_size / (1024 * 1024)  # MB
                print(f"📁 {mp3_file.name} ({file_size:.2f} MB)")
        else:
            print("❌ La descarga reportó éxito pero no hay archivos MP3")
            print("💡 Revisa los permisos de la carpeta 'downloads'")
        
        if fallback_downloads:
            print("\n⚠️ Canción descargada con yt-dlp (verifícala manualmente):")
            for name in fallback_downloads:
                print(f"   - {name}")

    else:
        print("\n💥 La descarga falló")

def get_unique_download_folder(base_name="downloads"):
    """Obtiene un nombre único para la carpeta de descargas"""
    folder = Path(base_name)
    counter = 0
    # Si la carpeta base no existe, la usamos
    if not folder.exists():
        return folder
    
    # Si la carpeta base existe pero está vacía, la usamos
    if not any(folder.iterdir()):
        return folder
    
    # Buscar una carpeta que no exista o esté vacía
    while True:
        new_folder = Path(f"{base_name}{counter}")
        if not new_folder.exists():
            return new_folder
        if not any(new_folder.iterdir()):
            return new_folder
        counter += 1

def create_credentials_file():
    """Crea archivo de credenciales de ejemplo"""
    example_content = """TU_CLIENT_ID_AQUI
TU_CLIENT_SECRET_AQUI
"""
    cred_file = Path("spotify_client_data.txt")
    if not cred_file.exists():
        with open(cred_file, "w", encoding="utf-8") as f:
            f.write(example_content)
        print("📄 Archivo 'spotify_client_data.txt' creado")

def create_songs_template_file():
    """Crea archivo de canciones de ejemplo"""
    example_content = """# Archivo songs-to-download.txt
# Coloca una URL de Spotify por línea
# Las líneas que comienzan con # son comentarios

https://open.spotify.com/track/4vIQ62JoGRy7tDy24hiqrF
https://open.spotify.com/track/6T7FX1XaXoh1oGpt4QrP8l
https://open.spotify.com/track/0B7c7s1qumVfKVSJhQbq1L

# Más canciones...
"""
    songs_file = Path("songs-to-download.txt")
    if not songs_file.exists():
        with open(songs_file, "w", encoding="utf-8") as f:
            f.write(example_content)
        print("📄 Archivo 'songs-to-download.txt' creado con ejemplo")

def find_best_match(artist, title, mp3_files, assigned_files):
    target = normalize_song_name(f"{artist} {title}")

    exact_matches = []
    title_matches = []
    fuzzy_candidates = []

    for mp3 in mp3_files:
        if mp3 in assigned_files:
            continue

        name_norm = normalize_song_name(mp3.stem)

        # 1) Coincidencia exacta artista+título
        if name_norm == target:
            exact_matches.append(mp3)
            continue

        # 2) Coincidencia exacta por título
        if normalize_song_name(title) in name_norm:
            title_matches.append(mp3)
            continue

        # 3) Coincidencia fuzzy (muy estricta)
        ratio = SequenceMatcher(None, name_norm, target).ratio()
        fuzzy_candidates.append((ratio, mp3))

    # 1) Exact artist-title match
    if exact_matches:
        return exact_matches[0]

    # 2) Exact title match
    if len(title_matches) == 1:
        return title_matches[0]
    elif len(title_matches) > 1:
        print(f"⚠️ Duplicados detectados para: {artist} - {title}:")
        for f in title_matches:
            print("   -", f.name)
        return None

    # 3) Fuzzy matching
    if fuzzy_candidates:
        best_ratio, best_file = max(fuzzy_candidates)
        if best_ratio >= 0.93:
            return best_file

    return None

def match_local_file_to_track(mp3_file, artist, title):
    """
    Asocia un archivo MP3 con una canción usando SOLO el nombre,
    nunca el WOAS ni tracknumber (para no liar el orden).
    """
    file_norm = normalize_song_name(mp3_file.stem)
    target_norm = normalize_song_name(f"{artist} {title}")

    # Coincidencia exacta "artist title"
    if file_norm == target_norm:
        return True

    # Coincidencia por título
    title_norm = normalize_song_name(title)
    if title_norm and title_norm in file_norm:
        return True

    # Fuzzy match fuerte
    ratio = SequenceMatcher(None, file_norm, target_norm).ratio()
    if ratio >= 0.85:  # Bajé el umbral para ser más flexible
        return True

    return False

def sync_spotify_playlist(spotdl_args=None):
    """Sincroniza una carpeta local con una playlist de Spotify (detección primero, luego actualización)."""
    print("\n" + "="*50)
    print("🔄 SINCRONIZAR PLAYLIST DE SPOTIFY")
    print("="*50)

    playlist_url = input("Introduce la URL de la playlist de Spotify: ").strip()
    local_folder = Path(input("Introduce la ruta de la carpeta local de la playlist: ").strip())

    if not local_folder.exists():
        print(f"❌ La carpeta {local_folder} no existe.")
        return

    # --- Autenticación con Spotify ---
    try:
        with open("spotify_client_data.txt") as f:
            lines = [line.strip() for line in f if line.strip()]
        client_id, client_secret = lines[:2]
        sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=client_id, client_secret=client_secret))
    except Exception as e:
        print(f"❌ Error inicializando cliente Spotify: {e}")
        return

    # --- Obtener información de la playlist ---
    print("📡 Obteniendo información de la playlist...")
    playlist_id = playlist_url.split("/")[-1].split("?")[0]

    try:
        results = sp.playlist_tracks(playlist_id)
    except Exception as e:
        print(f"❌ Error obteniendo tracks de la playlist: {e}")
        return

    tracks = results["items"]
    while results.get("next"):
        results = sp.next(results)
        tracks.extend(results["items"])

    total_tracks = len(tracks)
    print(f"🎧 Playlist con {total_tracks} canciones encontradas\n")

    # ================================
    # 🔍 VERIFICAR NOMBRE DE CARPETA
    # ================================
    playlist_name = sp.playlist(playlist_id)["name"]
    norm_playlist = normalize_folder_name(playlist_name)
    norm_folder = normalize_folder_name(local_folder.name)

    if norm_playlist != norm_folder:
        print("⚠️ El nombre de la carpeta NO coincide con el nombre de la playlist.")
        print(f"   Carpeta actual : {local_folder.name}")
        print(f"   Playlist nombre: {playlist_name}\n")

        resp = input("¿Quieres renombrar la carpeta automáticamente? (s/n): ").strip().lower()

        if resp == "s":
            try:
                new_path = local_folder.parent / playlist_name
                local_folder.rename(new_path)
                local_folder = new_path
                print(f"✅ Carpeta renombrada a: {playlist_name}\n")
            except Exception as e:
                print(f"❌ Error renombrando carpeta: {e}")
                return

        else:
            resp2 = input(
                "¿Quieres crear una carpeta nueva para esta playlist y usarla? (s/n): "
            ).strip().lower()

            if resp2 == "s":
                try:
                    new_path = local_folder.parent / playlist_name
                    new_path.mkdir(exist_ok=True)
                    print(f"📁 Carpeta creada: {new_path}")
                    local_folder = new_path
                except Exception as e:
                    print(f"❌ No se pudo crear la carpeta: {e}")
                    return

            else:
                print("↩️ Operación cancelada. Volviendo al menú principal.")
                return

    # --- FASE 1: DETECCIÓN ---
    mp3_files = list(local_folder.glob("*.mp3"))
    assigned_files = set()
    found_matches = []
    all_tracks = []
    corrupt_files_seen = set()

    # Recopilar todas las pistas
    for i, item in enumerate(tracks, start=1):
        track = item["track"]
        if not track:
            continue
        artist = track["artists"][0]["name"]
        title = track["name"]
        url = track["external_urls"]["spotify"]
        all_tracks.append({
            "index": i,
            "artist": artist,
            "title": title,
            "url": url
        })

    print("🔎 Buscando coincidencias en la carpeta local (fase de detección)...")

    # Crear diccionario de archivos con sus números de pista actuales
    files_with_tracknum = {}
    for mp3_file in mp3_files:
        try:
            tags = EasyID3(mp3_file)
            current_num = tags.get("tracknumber", ["0"])[0]
            current_clean = str(current_num).split('/')[0] if current_num else "0"
            track_num_int = int(current_clean) if current_clean.isdigit() else 0
            files_with_tracknum[mp3_file] = track_num_int
        except:
            files_with_tracknum[mp3_file] = 0

    # PRIMERO: asignar archivos que tengan TRCK coincidente con posición y nombre
    for mp3_file in mp3_files:
        if mp3_file in assigned_files:
            continue
        trck = files_with_tracknum.get(mp3_file, 0)
        if trck > 0 and trck <= len(all_tracks):
            track_info = all_tracks[trck - 1]
            artist = track_info["artist"]
            title = track_info["title"]
            if match_local_file_to_track(mp3_file, artist, title):
                found_matches.append((mp3_file, trck, artist, title))
                assigned_files.add(mp3_file)

                # OPCIONAL: corregir WOAS si no coincide
                has_woas = False
                stored_url = None
                try:
                    tags = ID3(mp3_file)
                    woas = tags.get("WOAS")
                    if woas:
                        has_woas = True
                        stored_url = woas.url.strip()
                except:
                    pass

                if has_woas:
                    stored_id = extract_track_id(stored_url)
                    expected_id = extract_track_id(track_info["url"])
                    if stored_id != expected_id:
                        try:
                            tags = ID3(mp3_file)
                            tags.delall("WOAS")
                            normalized_url = normalize_spotify_url(track_info["url"])
                            tags.add(WOAS(encoding=3, url=normalized_url))
                            tags.save()
                            print(f"🔧 WOAS actualizado en {mp3_file.name}")
                        except:
                            pass

    # SEGUNDO: asignar pistas restantes por coincidencia de nombre
    for track_info in all_tracks:
        track_num = track_info["index"]
        artist = track_info["artist"]
        title = track_info["title"]
        url = track_info["url"]

        matched = False

        for mp3_file in mp3_files:
            if mp3_file in assigned_files:
                continue

            # === SOLO COINCIDENCIA POR NOMBRE ===
            if match_local_file_to_track(mp3_file, artist, title):
                found_matches.append((mp3_file, track_num, artist, title))
                assigned_files.add(mp3_file)
                matched = True

                # OPCIONAL: corregir WOAS si no coincide
                has_woas = False
                stored_url = None
                try:
                    tags = ID3(mp3_file)
                    woas = tags.get("WOAS")
                    if woas:
                        has_woas = True
                        stored_url = woas.url.strip()
                except:
                    pass

                if has_woas:
                    stored_id = extract_track_id(stored_url)
                    expected_id = extract_track_id(url)
                    if stored_id != expected_id:
                        try:
                            tags = ID3(mp3_file)
                            tags.delall("WOAS")
                            normalized_url = normalize_spotify_url(url)
                            tags.add(WOAS(encoding=3, url=normalized_url))
                            tags.save()
                            print(f"🔧 WOAS actualizado en {mp3_file.name}")
                        except:
                            pass

                break

    # Calcular pistas faltantes
    assigned_track_nums = {track_num for _, track_num, _, _ in found_matches}
    missing_tracks = [t for t in all_tracks if t["index"] not in assigned_track_nums]

    # --- FASE 2: ACTUALIZACIÓN DE METADATOS ---
    print("\n🛠️ Actualizando metadatos (fase de actualización)...")
    updated_metadata = 0
    correct_track_numbers = 0
    changes_log = []

    for mp3_file, track_num, artist, title in found_matches:

        # Leer TRCK actual
        try:
            tags = EasyID3(mp3_file)
            current_num = tags.get("tracknumber", ["0"])[0]
        except:
            current_num = "0"

        current_clean = str(current_num).split('/')[0] if current_num else "0"

        # ISRC desde Spotify
        isrc = None
        if track_num <= len(tracks):
            trk = tracks[track_num - 1]["track"]
            if trk:
                isrc = trk.get("external_ids", {}).get("isrc")

        # Ya correcto
        if current_clean == str(track_num):
            correct_track_numbers += 1
            print(f"✅ {mp3_file.name} → pista #{track_num} (ya correcta)")
            continue

        # Actualizar TRCK + TSRC
        try:
            old = current_clean
            update_track_tags(
                mp3_file,
                track_number=track_num,
                isrc=isrc
            )
            updated_metadata += 1
            changes_log.append(f"{mp3_file.name}: {old} → {track_num}")
            print(f"🛠️ {mp3_file.name} → pista actualizada {old} → {track_num}")

        except Exception as e:
            print(f"⚠️ No se pudo actualizar metadatos en {mp3_file.name}: {e}")

    found_tracks = len(found_matches)

    # --- RESUMEN ---
    print("\n" + "="*50)
    print("📊 RESULTADO DE DETECCIÓN / ACTUALIZACIÓN")
    print("="*50)
    print(f"• Canciones en playlist: {total_tracks}")
    print(f"• Canciones encontradas en carpeta: {found_tracks}")
    print(f"• Números de pista correctos: {correct_track_numbers}")
    print(f"• Números de pista actualizados: {updated_metadata}")
    print(f"• Canciones faltantes: {len(missing_tracks)}")

    if changes_log:
        print("\n📝 Cambios realizados:")
        for c in changes_log:
            print(f"   - {c}")

    # =========================================
    # 🗑️ BORRAR ARCHIVOS QUE NO SON DE PLAYLIST
    # =========================================

    print("\n🔎 Buscando archivos que no pertenecen a la playlist...")

    matched_files = {f for (f, _, _, _) in found_matches}
    playlist_files = set(local_folder.glob("*.mp3"))

    extra_files = playlist_files - matched_files

    if extra_files:
        print(f"⚠️ Se encontraron {len(extra_files)} archivos no pertenecientes a la playlist:")
        for ef in extra_files:
            print(f"   - {ef.name}")

        resp = input("¿Deseas BORRAR estos archivos extra? (s/n): ").strip().lower()
        if resp == "s":
            for ef in extra_files:
                try:
                    ef.unlink()
                    print(f"🗑️ Borrado: {ef.name}")
                except Exception as e:
                    print(f"❌ No se pudo borrar {ef.name}: {e}")
        else:
            print("ℹ️ No se borraron archivos extra.")
    else:
        print("✅ No hay archivos extra.")

    # --- DESCARGAS ---
    if missing_tracks:
        print("\n🎵 Canciones faltantes:")
        for m in missing_tracks:
            if m.get("force_redownload") and m.get("bad_file"):
                try:
                    print(f"🗑️ Borrando archivo incorrecto: {m['bad_file'].name}")
                    m["bad_file"].unlink()
                except Exception as e:
                    print(f"❌ No se pudo borrar {m['bad_file'].name}: {e}")

            print(f"   [{m['index']:02}] {m['artist']} - {m['title']}")

        resp = input("\n¿Deseas descargar las canciones faltantes? (s/n): ").strip().lower()
        if resp == "s":
            print("\n⬇️ Descargando canciones faltantes...\n")
            output_dir = local_folder

            existing_before = set(output_dir.glob("*.mp3"))

            for m in missing_tracks:
                print(f"🎵 [{m['index']:02}] {m['artist']} - {m['title']}")
                ok = False
                if m.get("url"):
                    ok = download_song_with_detailed_errors(m["url"], output_dir, spotdl_args, fallback_list=None)
                else:
                    print("⚠️ No hay URL de Spotify para esta pista, se omite descarga.")

                if ok:
                    current_files = set(output_dir.glob("*.mp3"))
                    new_files = list(current_files - existing_before)

                    chosen_file = None
                    if new_files:
                        best_ratio = 0.0
                        target_norm = normalize_song_name(f"{m['artist']} {m['title']}")
                        for nf in new_files:
                            ratio = SequenceMatcher(None, normalize_song_name(nf.stem), target_norm).ratio()
                            if ratio > best_ratio:
                                best_ratio = ratio
                                chosen_file = nf

                        if chosen_file is None:
                            chosen_file = max(new_files, key=lambda x: x.stat().st_mtime)
                    else:
                        # Si no hay archivos nuevos, buscar el archivo existente que coincida
                        target_norm = normalize_song_name(f"{m['artist']} {m['title']}")
                        best_ratio = 0.0
                        for cf in current_files:
                            ratio = SequenceMatcher(None, normalize_song_name(cf.stem), target_norm).ratio()
                            if ratio > best_ratio:
                                best_ratio = ratio
                                chosen_file = cf

                    if chosen_file:
                        try:
                            tags = EasyID3(chosen_file)
                        except:
                            tags = EasyID3()

                        try:
                            tags["tracknumber"] = str(m['index'])
                            tags.save(chosen_file)
                            print(f"✅ Metadato de pista actualizado para {chosen_file.name}")
                        except Exception as e:
                            print(f"⚠️ No se pudo escribir tag en {chosen_file.name}: {e}")

                    existing_before = set(current_files)

            print("\n🎉 Sincronización completada (descargas procesadas).")

        else:
            print("\nℹ️ Descargas omitidas por el usuario.")

    else:
        print("\n✅ Todas las canciones están sincronizadas.")

    return

def extract_track_id(url: str) -> str:
    if not url:
        return ""

    # Normalizar unicode (importante por caracteres invisibles)
    url = unicodedata.normalize("NFKC", url)

    # Pasar a minúsculas
    url = url.lower().strip()

    # Quitar parámetros ?si=...
    url = url.split("?")[0]

    # Quitar /intl-es/ o variantes regionales
    url = url.replace("/intl-es/", "/")
    url = url.replace("/intl/", "/")
    url = url.replace("/es/", "/")

    # Quitar barra final
    url = url.rstrip("/")

    # Extraer ID por regex (24 caracteres)
    match = re.search(r"track/([a-z0-9]{22})", url)
    if match:
        return match.group(1)

    return url  # fallback en caso raro

def normalize_song_name(name: str) -> str:
    """
    Limpia y normaliza nombres de canciones o archivos:
    - Elimina caracteres ilegales o especiales
    - Convierte a minúsculas
    - Reemplaza guiones, paréntesis y símbolos por espacios
    - Elimina palabras vacías comunes (feat, remix, official, etc.)
    - Elimina "feat" y lo que sigue
    """
    name = re.sub(r'[<>:"/\\|?*]', '', name)  # eliminar caracteres ilegales
    name = re.sub(r'[\(\)\[\]\{\}_\-\+]', ' ', name)  # reemplazar separadores
    name = re.sub(r'\s+', ' ', name).strip().lower()  # espacios y minúsculas
    
    # eliminar "feat" y lo que sigue
    name = re.sub(r'\b(?:feat|ft|with)\b.*', '', name, flags=re.IGNORECASE)
    
    # eliminar palabras accesorias típicas
    stopwords = ['feat', 'ft', 'remix', 'version', 'official', 'audio', 'video', 'explicit']
    for w in stopwords:
        name = re.sub(rf'\b{w}\b', '', name)
    return re.sub(r'\s+', ' ', name).strip()

def normalize_string(s: str) -> str:
    """Normaliza cadenas quitando símbolos, espacios y pasando a minúsculas"""
    return re.sub(r'[^a-z0-9]+', '', s.lower())

def normalize_folder_name(name: str):
    """Normaliza nombre para compararlo con carpetas."""
    return re.sub(r'[^a-z0-9]', '', name.lower())

def is_matching_song(filename_stem, artist, title, threshold=0.82):
    """
    Compara el nombre del archivo con artista y título.
    Usa similitud fuzzy pero exige coincidencia fuerte del título completo
    para evitar confundir 'Firestone' con 'First Time'.
    """
    # Normalizar
    name_norm = normalize_string(filename_stem)
    artist_norm = normalize_string(artist)
    title_norm = normalize_string(title)

    # Evita falsos positivos cuando el título contiene el otro parcialmente
    if title_norm in name_norm or name_norm in title_norm:
        title_score = 1.0
    else:
        title_score = SequenceMatcher(None, title_norm, name_norm).ratio()

    # Bonus si el artista coincide en parte
    artist_score = SequenceMatcher(None, artist_norm, name_norm).ratio()

    # Peso: título 80%, artista 20%
    similarity = title_score * 0.8 + artist_score * 0.2

    # Coincidencia solo si el título coincide muy bien
    return similarity >= threshold and title_score > 0.9
    """
    Comprueba si un nombre de archivo coincide con un artista/título dados,
    usando coincidencia flexible y ratio de similitud.
    """
    normalized_file = normalize_song_name(file_stem)
    normalized_target = normalize_song_name(f"{artist} {title}")

    ratio = SequenceMatcher(None, normalized_file, normalized_target).ratio()
    return ratio >= threshold

def match_by_tracknumber_and_artist(mp3_file, track_num, artist):
    """
    Coincidencia secundaria para archivos descargados SIN WOAS.
    Si el MP3 contiene WOAS, esta función SIEMPRE devuelve False.
    """
    # Si el archivo tiene WOAS → NO usar esta coincidencia
    try:
        id3 = ID3(mp3_file)
        if id3.get("WOAS"):
            return False
    except:
        pass

    # Procesar como coincidencia secundaria
    try:
        tags = EasyID3(mp3_file)
    except:
        return False

    # 1) Coincidencia de tracknumber
    trck = tags.get("tracknumber", ["0"])[0]
    clean = trck.split("/")[0]

    if clean != str(track_num):
        return False

    # 2) Coincidencia aproximada de artista en el filename
    filename = mp3_file.stem.lower()
    artist_clean = artist.lower()

    return artist_clean in filename

def check_and_update_libraries():
    """Comprueba si spotdl y yt-dlp están actualizados y ofrece actualizarlos"""
    print("\n🔍 Comprobando versiones de librerías...")
    
    # Comprobar versiones instaladas
    try:
        spotdl_result = subprocess.run(["spotdl", "--version"], capture_output=True, text=True, timeout=10)
        if spotdl_result.returncode == 0:
            spotdl_version = spotdl_result.stdout.strip()
            print(f"✅ SpotDL versión instalada: {spotdl_version}")
        else:
            print("❌ Error obteniendo versión de SpotDL")
            spotdl_version = None
    except Exception as e:
        print(f"❌ Error obteniendo versión de SpotDL: {e}")
        spotdl_version = None
    
    try:
        ytdlp_result = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True, timeout=10)
        if ytdlp_result.returncode == 0:
            ytdlp_version = ytdlp_result.stdout.strip()
            print(f"✅ yt-dlp versión instalada: {ytdlp_version}")
        else:
            print("❌ Error obteniendo versión de yt-dlp")
            ytdlp_version = None
    except Exception as e:
        print(f"❌ Error obteniendo versión de yt-dlp: {e}")
        ytdlp_version = None
    
    # Comprobar si hay actualizaciones disponibles
    try:
        outdated_result = subprocess.run([sys.executable, "-m", "pip", "list", "--outdated"], capture_output=True, text=True, timeout=30)
        outdated_packages = outdated_result.stdout
        spotdl_outdated = "spotdl" in outdated_packages.lower()
        ytdlp_outdated = "yt-dlp" in outdated_packages.lower()
    except Exception as e:
        print(f"❌ Error comprobando actualizaciones: {e}")
        spotdl_outdated = False
        ytdlp_outdated = False
    
    if spotdl_outdated:
        print("⚠️ SpotDL tiene una versión más reciente disponible.")
    else:
        print("✅ SpotDL está actualizado.")
    
    if ytdlp_outdated:
        print("⚠️ yt-dlp tiene una versión más reciente disponible.")
    else:
        print("✅ yt-dlp está actualizado.")
    
    # Preguntar si actualizar
    if spotdl_outdated or ytdlp_outdated:
        while True:
            respuesta = input("\n¿Quieres actualizar las librerías desactualizadas? (s/n): ").strip().lower()
            if respuesta == "s" or respuesta == "si":
                print("\n🔄 Actualizando librerías...")
                if spotdl_outdated:
                    print("Actualizando SpotDL...")
                    try:
                        update_result = subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "git+https://github.com/spotDL/spotify-downloader.git"], timeout=300)
                        if update_result.returncode == 0:
                            print("✅ SpotDL actualizado correctamente.")
                        else:
                            print("❌ Error actualizando SpotDL.")
                    except Exception as e:
                        print(f"❌ Error actualizando SpotDL: {e}")
                
                if ytdlp_outdated:
                    print("Actualizando yt-dlp...")
                    try:
                        update_result = subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"], timeout=300)
                        if update_result.returncode == 0:
                            print("✅ yt-dlp actualizado correctamente.")
                        else:
                            print("❌ Error actualizando yt-dlp.")
                    except Exception as e:
                        print(f"❌ Error actualizando yt-dlp: {e}")
                break
            elif respuesta == "n" or respuesta == "no":
                print("Actualización cancelada.")
                break
            else:
                print("Por favor, responde 's' o 'n'.")
    else:
        print("\n🎉 Todas las librerías están actualizadas.")

def main_menu():
    """Menú principal de la aplicación"""
    create_credentials_file()
    create_songs_template_file()
    
    while True:
        print("\n" + "="*50)
        print("🎵 SPOTIFY DOWNLOADER")
        print("="*50)
        print("1. Descargar una canción individual")
        print("2. Descargar múltiples canciones desde archivo")
        print("3. Exportar playlist a archivo")
        print("4. Sincronizar playlist local con Spotify")
        print("5. Comprobar y actualizar librerías")
        print("6. Salir")
        
        opcion = input("\nElige una opción (1, 2, 3, 4, 5 o 6): ").strip()
        
        if opcion == "1":
            download_single_song()
        elif opcion == "2":
            spotdl_args = get_spotdl_credentials()
            download_multiple_songs(spotdl_args)
        elif opcion == "3":
            export_playlist_to_file()
        elif opcion == "4":
            spotdl_args = get_spotdl_credentials()
            sync_spotify_playlist(spotdl_args)
        elif opcion == "5":
            check_and_update_libraries()
        elif opcion == "6":
            print("👋 ¡Hasta luego!")
            break
        else:
            print("❌ Opción no válida")
        
        input("\nPresiona Enter para continuar...")

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n⏹️ Programa cancelado por el usuario")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        print("\nPrograma terminado")