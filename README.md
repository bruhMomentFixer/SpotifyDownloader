# 🎵 Spotify Playlist Synchronization Tool (SpotPSync Tool)

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-PolyForm%20Noncommercial-blue.svg)](LICENSE)

🌐 Language: English | [Español](README_ES.md)

> Python tool for managing Spotify playlists, synchronizing local music folders, and maintaining ID3 metadata consistency.

> The program supports both English and Spanish. You can select the interface language when starting the tool.

## 📋 Table of Contents

* [✨ Features](#-features)
* [🔧 Requirements](#-requirements)
* [🧠 Technical Highlights](#-technical-highlights)
* [🚀 Installation](#-installation)
* [⚙️ Configuration](#️-configuration)
* [🌐 Language Selection](#-language-selection)
* [📖 Usage](#-usage)
* [🎯 Examples](#-examples)
* [🔍 Troubleshooting](#-troubleshooting)
* [🤝 Contributing](#-contributing)
* [📄 License](#-license)

## ✨ Features

* 🎶 **Track processing**: Processes individual Spotify track URLs.
* 🔄 **Automatic synchronization**: Keeps your local music folder synchronized with Spotify playlists.
* 🏷️ **ID3 metadata**: Automatically updates track numbers, ISRC codes, and Spotify URLs.
* 🎚️ **Fallback mechanism**: Integrates `spotdl` and `yt-dlp` as alternatives when the main processing method fails.
* 📁 **Organization**: Automatically creates folders based on the playlist name.
* 🔍 **Smart detection**: Finds existing files and avoids duplicates.
* 🌐 **Multilingual support**: Handles accents, symbols, and special characters.
* ⚡ **Large playlist processing**: Designed to work with large playlists and avoid duplicate processing.

## 🔧 Requirements

* **Python**: Version 3.8 or higher.
* **Dependencies**: `spotipy`, `mutagen`, `yt-dlp`, `spotdl`.
* **Spotify Developer credentials**: Optional for some features, but recommended to avoid usage limitations and improve compatibility with the Spotify Web API.
* **Operating system**: Windows, Linux, or macOS.

## 🧠 Technical Highlights

* Spotify Web API integration using `spotipy`.
* ID3 metadata management using `mutagen`.
* Synchronization between Spotify playlists and local folders.
* Filename, accent, and special character normalization.
* Detection of duplicates and files that do not belong to the playlist.
* Retry logic, result verification, and error handling.
* Cross-platform path handling using `pathlib`.
* Integration with external tools such as `spotdl` and `yt-dlp`.

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/bruhMomentFixer/spotpsync-tool.git
cd spotpsync-tool
```

### 2. Install Python

Download and install Python from [python.org](https://www.python.org/downloads/).

### 3. Install the dependencies

```bash
pip install -r requirements.txt
```

### 4. Update dependencies (optional)

Run option 5 in the program to automatically update `spotdl` and `yt-dlp`.

## ⚙️ Configuration

### Spotify Credentials

The program can use your own Spotify Developer credentials or the default credentials provided by `spotdl`. **Using your own credentials is recommended** to avoid usage limits and ensure better compatibility.

Some features, such as local playlist synchronization, require your own Spotify Developer credentials because they directly use the Spotify Web API through `spotipy`.

#### How to get your credentials:

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Create a new application.
3. Copy the `Client ID` and `Client Secret`.
4. Create a file named `spotify_client_data.txt` in the same folder as `spotpsync.py`:

   ```text
   YOUR_CLIENT_ID_HERE
   YOUR_CLIENT_SECRET_HERE
   ```

   **Important**: do not upload the `spotify_client_data.txt` file to the repository. Add it to `.gitignore` to avoid exposing your Spotify Developer credentials.

#### Credential options in the program:

When running a feature that requires Spotify access, the program may ask you to choose:

* **Option 1**: Use credentials from the `spotify_client_data.txt` file (recommended)
* **Option 2**: Use the default `spotdl` credentials (limited, not recommended for all features)
* **Option 3**: Enter credentials manually

### Initial Setup

Run the program and select the credential option. The program will guide you through the process.

## 🌐 Language Selection

SpotPSync Tool supports both English and Spanish.

When the program starts, it asks you to choose the interface language:

```text
==================================================
🌐 Language / Idioma
==================================================
1. Español
2. English

Choose language / Elige idioma (1 or 2):
```

After selecting the language, all main menus, prompts, and status messages will be displayed in the selected language.

## 📖 Usage

### Run the program

```bash
python spotpsync.py
```

You can also start the program directly in a specific language:
```bash
python spotpsync.py --lang en
python spotpsync.py --lang es
```

Available language options:

* `--lang en`: English interface
* `--lang es`: Spanish interface

If no language parameter is provided, the program will ask you to select the interface language at startup.

### Main Menu

```text
==================================================
🎵 SpotPSync Tool
==================================================
1. Process a single track
2. Process multiple tracks from file
3. Export playlist to file
4. Synchronize local folder with Spotify playlist
5. Check and update dependencies
6. Exit

Choose an option (1, 2, 3, 4, 5 or 6):
```

## 🎯 Examples

### 1. Process a single track

```text
Choose an option: 1
Enter the Spotify track URL: https://open.spotify.com/track/<track_id>
```

Result: processes the provided URL and stores the resulting file in the `./downloads` folder. If the folder does not exist, it is created automatically. If it already exists and contains files, a new folder such as `./downloads0` is created.

### 2. Process multiple tracks from file

```text
Choose an option: 2
```

Result: reads the `spotify-track-list.txt` file, processes the listed URLs, and stores the resulting files in the `./downloads` folder.

### 3. Export playlist to file

```text
Choose an option: 3
Enter the playlist URL: https://open.spotify.com/playlist/<playlist_id>
```

Result: automatically creates the `spotify-track-list.txt` file with all track URLs from the playlist.

### 4. Synchronize local folder with Spotify playlist

```text
Choose an option: 4
Enter the playlist URL: https://open.spotify.com/playlist/<playlist_id>
Enter the local folder path: C:\Music\Chill EDM
```

Result: compares the Spotify playlist with the local folder, processes missing tracks, and updates ID3 metadata.

### 5. Check and update dependencies

```text
Choose an option: 5
```

Result: updates `spotdl` and `yt-dlp` to the latest available versions.

## 🔍 Troubleshooting

### Authentication Error

* Verify that `spotify_client_data.txt` contains the correct credentials.
* Make sure your Spotify Developer application is properly configured and that the credentials are valid.

### Track Processing Failed

* The program uses `spotdl` as the main method and `yt-dlp` as a fallback mechanism.
* If processing fails, check your internet connection and make sure the URLs are valid.

### Metadata Issues

* Make sure the MP3 files are not locked.
* Use a metadata editor such as Mp3tag or an equivalent tool to verify the tags.

### Playlist Does Not Synchronize Correctly

* Verify that the local folder has write permissions.
* If duplicates exist, the program prioritizes files based on the track number metadata field (TRCK).
* Local playlist synchronization requires valid Spotify Developer credentials.

### Common Commands

```bash
# View detailed logs by redirecting output to a file
python spotpsync.py > log.txt

# The program is interactive and does not require additional arguments
# All configuration is handled through the menu
```

## 🤝 Contributing

Suggestions, bug reports, and improvement proposals are welcome through Issues.

## 📄 License

This project is licensed under the PolyForm Noncommercial License 1.0.0.

You may use, copy, modify, and share this software for personal, educational, and other non-commercial purposes.

Commercial use is not permitted without a separate commercial license. For commercial licensing, contact the author through the GitHub profile associated with this repository.

Third-party dependencies are distributed under their respective licenses.

---

**⚠️ Important note**: This project is intended only for personal, educational, and non-commercial use. Users are responsible for ensuring that their use of this tool complies with applicable law, the terms of service of the platforms used, and copyright regulations.
