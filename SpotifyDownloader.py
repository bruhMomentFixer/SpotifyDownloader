import os
import subprocess
import time
import json
import logging
import re
import sys
from pathlib import Path

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
    """Intenta descargar usando yt-dlp como respaldo"""
    try:
        print("🔄 Intentando con yt-dlp como alternativa...")
        
        # Obtener información real de la canción
        search_query = get_song_info(spotify_url, spotdl_args)
        if not search_query:
            # Si falla, usar el ID del track como último recurso
            track_id = spotify_url.split('/track/')[-1].split('?')[0]
            search_query = f"spotify track {track_id}"
        
        print(f"🎵 Buscando en YouTube: {search_query}")
        
        # Crear directorio de descargas si no existe
        output_path.mkdir(exist_ok=True)
        
        # Descargar con yt-dlp - mostrar progreso real
        cmd = [
            "yt-dlp",
            f"ytsearch1:{search_query}",  # ytsearch1 para solo el primer resultado
            "-x", 
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "-o", str(output_path / "%(title)s.%(ext)s"),
            "--no-playlist",
            "--no-simulate",  # Forzar descarga real
            "--newline"  # Mostrar progreso
        ]
        
        print("⬇️ Descargando con yt-dlp...")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                 universal_newlines=True, bufsize=1)
        
        # Mostrar progreso en tiempo real
        for line in process.stdout:
            if line.strip():
                print(f"📦 {line.strip()}")
        
        process.wait()
        
        if process.returncode == 0:
            # VERIFICAR que el archivo realmente se creó
            if verify_download_completion(output_path):
                print("✅ Descarga exitosa con yt-dlp")
                return True
            else:
                print("❌ yt-dlp reportó éxito pero no se encontraron archivos MP3 válidos")
                return False
        else:
            print("❌ Error en la descarga con yt-dlp")
            return False
            
    except Exception as e:
        logger.error(f"Error con yt-dlp: {e}")
        return False

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
    
    # Si no se puede obtener info, buscar cualquier archivo mp3 reciente
    return None

def verify_download_completion(output_path, expected_filename=None):
    """Verifica que la descarga se completó correctamente y el archivo existe"""
    # Esperar un poco para que el sistema de archivos se actualice
    time.sleep(2)
    
    # Buscar todos los archivos MP3 en la carpeta
    mp3_files = list(output_path.glob("*.mp3"))
    
    if not mp3_files:
        print("❌ VERIFICACIÓN: No se encontraron archivos MP3 después de la descarga")
        return False
    
    # Si tenemos un nombre esperado, buscar ese archivo específicamente
    if expected_filename:
        for mp3_file in mp3_files:
            if mp3_file.name == expected_filename:
                file_size = mp3_file.stat().st_size / (1024 * 1024)
                if file_size > 0.1:  # Archivo debe tener al menos 100KB
                    print(f"✅ VERIFICACIÓN: Archivo encontrado - {mp3_file.name} ({file_size:.2f} MB)")
                    return True
        
        print(f"❌ VERIFICACIÓN: No se encontró el archivo esperado '{expected_filename}'")
        print(f"   Archivos encontrados: {[f.name for f in mp3_files]}")
        return False
    
    # Si no tenemos nombre esperado, verificar que al menos un archivo tenga tamaño decente
    for mp3_file in mp3_files:
        file_size = mp3_file.stat().st_size / (1024 * 1024)
        if file_size > 0.1:  # Archivo debe tener al menos 100KB
            print(f"✅ VERIFICACIÓN: Archivo encontrado - {mp3_file.name} ({file_size:.2f} MB)")
            return True
    
    print("❌ VERIFICACIÓN: Los archivos MP3 encontrados son demasiado pequeños o están corruptos")
    print(f"   Archivos: {[f.name for f in mp3_files]}")
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

def download_song_with_detailed_errors(url, output_path, spotdl_args=None, timeout=300):
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
    
    for attempt in range(max_retries):
        try:
            print(f"⏳ Ejecutando SpotDL (intento {attempt + 1}/{max_retries})...")
            
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
                # VERIFICAR que el archivo realmente se creó
                if verify_download_completion(output_path, expected_filename):
                    print("✅ Descarga exitosa con SpotDL y verificación completada")
                    return True
                else:
                    print("⚠️ SpotDL reportó éxito pero no se encontró el archivo, reintentando...")
                    # Limpiar archivos corruptos/pequeños
                    for mp3_file in output_path.glob("*.mp3"):
                        if mp3_file.stat().st_size < 100 * 1024:  # Menos de 100KB
                            mp3_file.unlink()
                            print(f"🗑️ Eliminado archivo corrupto: {mp3_file.name}")
                    
                    if attempt < max_retries - 1:
                        print(f"🔄 Reintentando en {retry_delay} segundos...")
                        time.sleep(retry_delay)
                    continue
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
    yt_dlp_success = download_with_yt_dlp(url, output_path, spotdl_args)
    
    if yt_dlp_success:
        # Verificar también la descarga de yt-dlp
        if verify_download_completion(output_path):
            print("✅ Descarga exitosa con yt-dlp y verificación completada")
            return True
        else:
            print("❌ yt-dlp reportó éxito pero no se encontró el archivo")
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
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if is_valid_spotify_track_url(line):
                normalized_url = normalize_spotify_url(line)
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
    
    output_dir = Path("downloads")
    output_dir.mkdir(exist_ok=True)
    
    stats = {
        'total': len(urls),
        'success': 0,
        'failed': 0,
        'failed_urls': []
    }
    
    print(f"\n🎵 Iniciando descarga de {stats['total']} canciones")
    print("=" * 60)
    
    for i, url in enumerate(urls, 1):
        print(f"\n📥 [{i}/{stats['total']}]")
        print("-" * 50)
        
        success = download_song_with_detailed_errors(url, output_dir, spotdl_args)
        
        if success:
            stats['success'] += 1
            print(f"✅ Canción {i} descargada con éxito")
        else:
            stats['failed'] += 1
            stats['failed_urls'].append(url)
            print(f"❌ Error descargando canción {i}")
    
    # Mostrar resumen
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE DESCARGA")
    print("=" * 60)
    print(f"• Total de canciones: {stats['total']}")
    print(f"• Descargas exitosas: {stats['success']}")
    print(f"• Descargas fallidas: {stats['failed']}")
    
    if stats['failed_urls']:
        print(f"\n❌ URLs fallidas:")
        for url in stats['failed_urls']:
            print(f"   → {url}")
    
    # Verificar que los archivos existen
    mp3_files = list(output_dir.glob("*.mp3"))
    if not mp3_files:
        print(f"\n❌ ERROR: No se encontraron archivos MP3 en la carpeta 'downloads'")
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
    
    output_dir = Path("downloads")
    output_dir.mkdir(exist_ok=True)
    
    print(f"\n📥 Descargando: {normalized_url}")
    print("-" * 50)
    
    success = download_song_with_detailed_errors(normalized_url, output_dir, spotdl_args)
    
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
    else:
        print("\n💥 La descarga falló")

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