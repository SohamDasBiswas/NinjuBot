<<<<<<< HEAD
# 🎵 NinjaBot — Discord Music Bot
**Made by sdb_darkninja** | YouTube & Twitch Streamer

---

## ✅ Features
- 🎵 Play music from **YouTube, Spotify, JioSaavn, SoundCloud**
- 📋 Full queue system with loop modes
- 📊 **Twitch analytics voice channels** (auto-updates every 5 min)
- ⚡ Fast audio with FFmpeg + yt-dlp
- 🔊 Volume control
- ℹ️ Credits command mentions creator

---

## 🚀 Setup

### 1. Install Requirements
```bash
pip install -r requirements.txt
```
Also install **FFmpeg**:
- **Windows**: Download from https://ffmpeg.org → add to PATH
- **Ubuntu/Debian**: `sudo apt install ffmpeg`
- **Mac**: `brew install ffmpeg`

### 2. Set Up API Keys

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
```

| Key | Where to get it |
|-----|----------------|
| `DISCORD_TOKEN` | https://discord.com/developers/applications → Bot → Token |
| `SPOTIFY_CLIENT_ID/SECRET` | https://developer.spotify.com/dashboard |
| `TWITCH_CLIENT_ID/SECRET` | https://dev.twitch.tv/console/apps |

### 3. Enable Discord Bot Intents
Go to Discord Developer Portal → Your App → Bot:
- ✅ Message Content Intent
- ✅ Server Members Intent
- ✅ Presence Intent

### 4. Run the Bot
```bash
python bot.py
```

---

## 📋 Commands

### 🎵 Music
| Command | Description |
|---------|-------------|
| `!play <song/url>` | Play from YouTube, Spotify, JioSaavn |
| `!pause` | Pause music |
| `!resume` | Resume music |
| `!skip` | Skip song |
| `!stop` | Stop & clear queue |
| `!queue` | Show queue |
| `!nowplaying` | Current song info |
| `!loop [song\|queue\|none]` | Set loop mode |
| `!volume <1-100>` | Set volume |
| `!join` / `!leave` | Join/leave voice |

### 📊 Twitch
| Command | Description |
|---------|-------------|
| `!twitchsetup` | Create analytics voice channels *(Admin only)* |
| `!twitchstats` | Show live Twitch stats |

### ℹ️ Info
| Command | Description |
|---------|-------------|
| `!credits` | See who made the bot |
| `!help` | Show all commands |

---

## 🎵 Platform Examples
```
!play https://youtube.com/watch?v=...       # YouTube URL
!play Never Gonna Give You Up               # YouTube search
!play https://open.spotify.com/track/...    # Spotify track
!play https://open.spotify.com/playlist/... # Spotify playlist
!play jio:Kesariya                          # JioSaavn search
```

---

## 🌐 Free Hosting (24/7)
Use **Oracle Cloud Free Tier** (best option):
1. Sign up at https://cloud.oracle.com
2. Create a free ARM VM (Ubuntu)
3. `git clone` your bot code
4. `pip install -r requirements.txt`
5. `sudo apt install ffmpeg`
6. Run with `screen` or `systemd`

---

## 👤 Creator
**sdb_darkninja**
- 📺 YouTube: https://youtube.com/@sdb_darkninja
- 🎮 Twitch: https://twitch.tv/sdb_darkninja
=======
# NinjuBot
>>>>>>> f81b4ac67ac9c02269b87d22f9ef18d371af8c7f
