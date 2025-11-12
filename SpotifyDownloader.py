import os
import time
import json
import logging
import re
import sys
from pathlib import Path
import subprocess, shlex

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


    # 🔄 Intentando con yt-dlp como alternativa...
    print("🔄 Intentando con yt-dlp como alternativa...")

    # Inicializar valores por defecto
    track_name = None
    artist_name = None
    clean_query = None

    # Asegurarse de que existe output_dir
    if 'output_dir' not in locals():
        output_dir = os.path.join(os.getcwd(), "downloads_fallback")
        os.makedirs(output_dir, exist_ok=True)

    # Asegurarse de que existe sp (cliente Spotify)
    try:
        if 'sp' not in locals():
            import spotipy
            from spotipy.oauth2 import SpotifyClientCredentials
            with open("spotify_client_data.txt") as f:
                lines = [line.strip() for line in f if line.strip()]
            client_id, client_secret = lines[:2]
            sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=client_id, client_secret=client_secret))
    except Exception as e:
        print(f"⚠️ No se pudo inicializar cliente Spotify: {e}")

    # Asegurarse de que existe track_url
    if 'track_url' not in locals() or not track_url:
        track_url = input("Introduce la URL del track de Spotify: ").strip()

    # Intentar obtener información real desde Spotify
    try:
        track_info = sp.track(track_url)
        track_name = track_info['name']
        artist_name = track_info['artists'][0]['name']
        clean_query = f"{artist_name} - {track_name}"
        print(f"🎯 Nombre obtenido de Spotify: {clean_query}")
    except Exception as e:
        print(f"⚠️ No se pudo obtener información de Spotify: {e}")
        clean_query = "unknown track"

    # Construir búsqueda en YouTube
    search_query = f"ytsearch5:{clean_query}"
    print(f"🔍 Buscando en YouTube: {search_query}")

    try:
        # Obtener lista de resultados JSON
        cmd_info = f'yt-dlp --dump-json --flat-playlist "{search_query}"'
        process = subprocess.run(shlex.split(cmd_info), capture_output=True, text=True)
        lines = [json.loads(line) for line in process.stdout.strip().splitlines() if line.strip()]

        if not lines:
            print("❌ No se encontraron resultados en YouTube.")
            raise RuntimeError("No se encontraron resultados en YouTube")

        # Seleccionar primer resultado (el más relevante)
        best_match = lines[0]
        video_url = f"https://www.youtube.com/watch?v={best_match['id']}"
        print(f"🏆 Mejor coincidencia: {best_match['title']}")
        print(f"🔗 URL seleccionada: {video_url}")

        # Descargar con yt-dlp
        yt_dlp_cmd = [
            "yt-dlp", "-x", "--audio-format", "mp3",
            "-o", os.path.join(output_dir, "%(title)s.%(ext)s"),
            video_url
        ]
        print("⬇️ Descargando con yt-dlp...")
        subprocess.run(yt_dlp_cmd)

    except Exception as e:
        print(f"❌ Error en la descarga con yt-dlp: {e}")

def normalize_spotify_url(url):
    """Normaliza URLs de Spotify"""
    pattern = r'https://open\.spotify\.com/(?:intl-[a-z]{2}/)?track/([a-zA-Z0-9]+)'
    match = re.search(pattern, url)
    if match:
        track_id = match.group(1)
        return f"https://open.spotify.com/track/{track_id}"
    return url

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

def fetch_playlist_urls(playlist_url, spotdl_args=None, max_retries=3):
    """Obtiene todas las URLs de una playlist de Spotify usando el método de guardar metadata"""
    temp_metadata = Path("temp_playlist_metadata.spotdl")
    
    for attempt in range(max_retries):
        try:
            print(f"🔍 Obteniendo metadatos de la playlist (intento {attempt+1}/{max_retries})...")
            
            # Limpiar archivo temporal si existe de intentos anteriores
            if temp_metadata.exists():
                temp_metadata.unlink()
            
            # Construir comando spotdl save - NUEVO FORMATO para spotdl 4.4.1
            cmd = ["spotdl", "save", playlist_url, "--save-file", str(temp_metadata)]
            
            # Añadir flags para evitar problemas
            cmd += [
                "--audio", "youtube",
                "--lyrics", "genius"  # Usar solo Genius, evitar AZLyrics que causa problemas
            ]
            
            # Añadir credenciales si están disponibles (nuevo formato)
            if spotdl_args:
                # Convertir el formato antiguo --client-id x --client-secret y
                # al nuevo formato --client-id=x --client-secret=y
                converted_args = []
                i = 0
                while i < len(spotdl_args):
                    if spotdl_args[i] in ["--client-id", "--client-secret"]:
                        if i + 1 < len(spotdl_args):
                            converted_args.append(f"{spotdl_args[i]}={spotdl_args[i+1]}")
                            i += 2
                        else:
                            i += 1
                    else:
                        converted_args.append(spotdl_args[i])
                        i += 1
                cmd += converted_args
            
            print(f"📝 Comando ejecutado: {' '.join(cmd)}")
            
            # Ejecutar comando
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            
            # Mostrar salida completa para diagnóstico - SIN TRUNCAR
            if result.stdout:
                print("📋 Salida completa:")
                print(result.stdout)
            if result.stderr:
                print("⚠️  Errores completos:")
                print(result.stderr)
            
            if result.returncode != 0:
                error_msg = f"Error ejecutando spotdl save (código {result.returncode})"
                print(f"❌ {error_msg}")
                
                # Esperar antes de reintentar (backoff exponencial)
                wait_time = 2 ** attempt
                print(f"⏳ Esperando {wait_time} segundos antes de reintentar...")
                time.sleep(wait_time)
                continue
            
            # Verificar que el archivo se creó y no está vacío
            if not temp_metadata.exists():
                error_msg = "El archivo de metadata no se creó"
                print(f"❌ {error_msg}")
                continue
                
            if temp_metadata.stat().st_size == 0:
                error_msg = "El archivo de metadata está vacío"
                print(f"❌ {error_msg}")
                continue
            
            # Leer y procesar el archivo de metadata
            with open(temp_metadata, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    error_msg = "El archivo de metadata está vacío"
                    print(f"❌ {error_msg}")
                    continue
                    
                playlist_data = json.loads(content)
            
            # Extraer URLs de las canciones
            song_urls = []
            for item in playlist_data:
                if isinstance(item, dict) and 'url' in item and item['url'].startswith('https://open.spotify.com/track/'):
                    song_urls.append(item['url'])
            
            if not song_urls:
                error_msg = "No se encontraron URLs de canciones en los metadatos"
                print(f"❌ {error_msg}")
                continue
            
            # Limpiar archivo temporal
            temp_metadata.unlink()
            
            print(f"✅ Se encontraron {len(song_urls)} canciones en la playlist")
            return song_urls, None
            
        except subprocess.TimeoutExpired:
            error_msg = f"Timeout al obtener la metadata (intento {attempt+1})"
            print(f"❌ {error_msg}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"⏳ Esperando {wait_time} segundos antes de reintentar...")
                time.sleep(wait_time)
        except json.JSONDecodeError as e:
            error_msg = f"Error decodificando JSON: {e}"
            print(f"❌ {error_msg}")
        except Exception as e:
            error_msg = f"Error inesperado: {str(e)}"
            print(f"❌ {error_msg}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"⏳ Esperando {wait_time} segundos antes de reintentar...")
                time.sleep(wait_time)
    
    # Limpiar archivo temporal en caso de error
    if temp_metadata.exists():
        try:
            temp_metadata.unlink()
        except:
            pass
    
    error_msg = "No se pudo obtener la playlist después de múltiples intentos"
    print(f"💥 {error_msg}")
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

def download_song_with_detailed_errors(url, output_path, spotdl_args=None, timeout=300, fallback_list=None):
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
        mp3_files = list(output_path.glob("*.mp3"))
        if mp3_files:
            latest_file = max(mp3_files, key=lambda x: x.stat().st_mtime)
            new_name = f"{clean_query}.mp3"
            safe_name = re.sub(r'[<>:"/\\|?*]', '', new_name)
            new_path = output_path / safe_name
            try:
                latest_file.rename(new_path)
                print(f"✅ Archivo renombrado a: {safe_name}")
            except Exception as e:
                print(f"⚠️ No se pudo renombrar el archivo: {e}")

            if fallback_list is not None:
                fallback_list.append(clean_query)
            print(f"✅ Descarga alternativa exitosa: {clean_query}")
            return True

    print("❌ Falló incluso con yt-dlp")
    return False

    """Descarga una canción mostrando errores detallados con reintentos y verificación"""
    # Mostrar información de la canción antes de descargar
    song_info = get_song_info_for_display(url, spotdl_args)
    if song_info:
        print(f"🎵 Intentando descargar: {song_info}")
    else:
        print(f"🎵 Intentando descargar URL: {url}")
    
    max_retries = 3
    retry_delay = 5
    
    # Predecir el nombre del archivo esperado
    expected_filename = get_expected_filename(url, output_path, spotdl_args)
    if expected_filename:
        print(f"📁 Archivo esperado: {expected_filename}")
    
    # Obtener archivos existentes antes de empezar
    existing_files = set(output_path.glob("*.mp3")) if output_path.exists() else set()
    initial_file_count = len(existing_files)
    
    for attempt in range(max_retries):
        try:
            print(f"⏳ Ejecutando SpotDL (intento {attempt + 1}/{max_retries})...")
            
            # Obtener archivos existentes ANTES de cada intento
            existing_files = set(output_path.glob("*.mp3")) if output_path.exists() else set()
            initial_count = len(existing_files)

            cmd = [
                "spotdl", "download", url,
                "--output", str(output_path / "{artist} - {title}.{output-ext}"),
                "--format", "mp3",
                "--lyrics", "genius"
            ]
            
            if spotdl_args:
                cmd += spotdl_args
            
            # Ejecutar SpotDL
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            
            if result.returncode == 0:
                # Esperar un poco para que el sistema de archivos se actualice
                time.sleep(3)
                
                # Verificar que se haya creado exactamente un archivo nuevo
                current_files = set(output_path.glob("*.mp3")) if output_path.exists() else set()
                new_files = current_files - existing_files
                current_count = len(current_files)
                
                print(f"📊 Archivos antes: {initial_count}, después: {current_count}, nuevos: {len(new_files)}")
                
                # Verificación robusta: debe haber exactamente un archivo nuevo
                if len(new_files) == 1:
                    new_file = next(iter(new_files))
                    file_size = new_file.stat().st_size / (1024 * 1024)  # MB
                    
                    if file_size > 0.1:  # Archivo válido (> 100KB)
                        print(f"✅ VERIFICACIÓN: Nuevo archivo válido - {new_file.name} ({file_size:.2f} MB)")
                        return True
                    else:
                        print(f"❌ VERIFICACIÓN: Archivo demasiado pequeño - {new_file.name} ({file_size:.2f} MB)")
                        # Eliminar archivo corrupto
                        try:
                            new_file.unlink()
                        except:
                            pass
                else:
                    print(f"❌ VERIFICACIÓN: Se encontraron {len(new_files)} archivos nuevos, se esperaba 1")
                    
                # Si la verificación falla, continuar con el reintento
                print("⚠️ SpotDL reportó éxito pero la verificación falló, reintentando...")
                
            else:
                # Mostrar el error completo solo en el último intento
                if attempt == max_retries - 1:
                    print(f"\n❌ ERROR DE SPOTDL después de {max_retries} intentos:")
                    print("=" * 50)
                    if result.stdout:
                        print("STDOUT:", result.stdout)
                    if result.stderr:
                        print("STDERR:", result.stderr)
                    print("=" * 50)
                else:
                    error_summary = extract_spotdl_error(result.stderr)
                    print(f"⚠️ Intento {attempt + 1} fallado: {error_summary}")
                    
                print(f"🔄 Reintentando en {retry_delay} segundos...")
                time.sleep(retry_delay)
                    
        except subprocess.TimeoutExpired:
            if attempt == max_retries - 1:
                print("⏰ Timeout excedido después de múltiples intentos")
                break
            else:
                print(f"⏰ Timeout en intento {attempt + 1}, reintentando...")
                time.sleep(retry_delay)
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Error inesperado: {e}")
                break
            else:
                print(f"⚠️ Error en intento {attempt + 1}: {e}, reintentando...")
                time.sleep(retry_delay)
    
    # Si todos los intentos con SpotDL fallan, intentar con yt-dlp
    print("🔄 Todos los intentos con SpotDL fallaron, probando con yt-dlp...")
    
    # Obtener archivos existentes antes de intentar con yt-dlp
    existing_files = set(output_path.glob("*.mp3")) if output_path.exists() else set()
    yt_dlp_success = download_with_yt_dlp(url, output_path, spotdl_args)
    
    if yt_dlp_success:
        # Verificar también la descarga de yt-dlp
        time.sleep(3)
        current_files = set(output_path.glob("*.mp3")) if output_path.exists() else set()
        new_files = current_files - existing_files
        
        if len(new_files) >= 1:
            new_file = next(iter(new_files))
            file_size = new_file.stat().st_size / (1024 * 1024)
            if file_size > 0.1:
                print(f"✅ VERIFICACIÓN: Descarga exitosa con yt-dlp - {new_file.name} ({file_size:.2f} MB)")
                return True
        
        print("❌ yt-dlp reportó éxito pero no se encontró el archivo válido")
        return False
    
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
    """Descarga múltiples canciones desde un archivo"""
    songs_file = Path("songs-to-download.txt")
    
    print(f"📖 Leyendo canciones desde: {songs_file}")
    urls = read_songs_from_file(songs_file)
    
    if not urls:
        return False
    
    # Obtener carpeta de descarga única
    output_dir = get_unique_download_folder()
    output_dir.mkdir(exist_ok=True)
    
    # Verificar archivos existentes antes de empezar (debería estar vacía)
    existing_files_before = set(output_dir.glob("*.mp3"))
    
    stats = {
        'total': len(urls),
        'success': 0,
        'failed': 0,
        'failed_urls': []
    }
    
    print(f"\n🎵 Iniciando descarga de {stats['total']} canciones en la carpeta: {output_dir}")
    print("=" * 60)
    
    for i, url in enumerate(urls, 1):
        print(f"\n📥 [{i}/{stats['total']}]")
        print("-" * 50)
        
        # Obtener archivos existentes antes de cada descarga
        existing_files = set(output_dir.glob("*.mp3"))
        
        fallback_downloads = []
        success = download_song_with_detailed_errors(url, output_dir, spotdl_args, fallback_list=fallback_downloads)
        
        if success:
            stats['success'] += 1
            print(f"✅ Canción {i} descargada con éxito")
        else:
            stats['failed'] += 1
            stats['failed_urls'].append(url)
            print(f"❌ Error descargando canción {i}")
    
    if fallback_downloads:
        print("\n⚠️ Canciones que se descargaron usando yt-dlp (verifícalas manualmente):")
        for name in fallback_downloads:
            print(f"   - {name}")

    # Mostrar resumen
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE DESCARGA")
    print("=" * 60)
    print(f"• Total de canciones: {stats['total']}")
    print(f"• Descargas exitosas: {stats['success']}")
    print(f"• Descargas fallidas: {stats['failed']}")
    
    # Verificar archivos descargados
    final_files = set(output_dir.glob("*.mp3"))
    new_files = final_files - existing_files_before
    print(f"• Archivos nuevos descargados: {len(new_files)}")
    
    if stats['failed_urls']:
        print(f"\n❌ URLs fallidas:")
        for url in stats['failed_urls']:
            print(f"   → {url}")
    
    # Verificar que los archivos existen
    mp3_files = list(output_dir.glob("*.mp3"))
    if not mp3_files:
        print(f"\n❌ ERROR: No se encontraron archivos MP3 en la carpeta '{output_dir}'")
        print("💡 Verifica los permisos de la carpeta y tu conexión a internet")
        return False
    
    return stats['failed'] == 0

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

def main_menu():
    """Menú principal de la aplicación"""
    if not check_spotdl_installation():
        if not install_spotdl():
            print("📦 Usando yt-dlp como alternativa principal...")
    
    create_credentials_file()
    create_songs_template_file()
    
    while True:
        print("\n" + "="*50)
        print("🎵 SPOTIFY DOWNLOADER")
        print("="*50)
        print("1. Descargar una canción individual")
        print("2. Descargar múltiples canciones desde archivo")
        print("3. Exportar playlist a archivo")
        print("4. Salir")
        
        opcion = input("\nElige una opción (1, 2, 3 o 4): ").strip()
        
        if opcion == "1":
            download_single_song()
        elif opcion == "2":
            spotdl_args = get_spotdl_credentials()
            download_multiple_songs(spotdl_args)
        elif opcion == "3":
            export_playlist_to_file()
        elif opcion == "4":
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