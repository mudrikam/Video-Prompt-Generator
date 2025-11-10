# Video Prompt Generator

Aplikasi desktop untuk menggenerate AI prompts dari video menggunakan Google GenAI API.

## Fitur Utama

- **Drag & Drop Video Files**: Seret video langsung ke tabel aplikasi
- **Batch Processing**: Generate multiple prompts untuk banyak video sekaligus
- **Smart Batch Splitting**: Otomatis memecah request besar untuk menghindari token limit
- **Flexible Generation Modes**: 
  - Generate untuk video yang dipilih (Selected Videos)
  - Generate untuk semua video (All Videos)
  - Generate hanya untuk video tanpa prompt (Ungenerated Only)
- **Secure API Key Management**: API key disimpan di `.env` file (tidak di-track git)
- **Customizable Parameters**: 
  - Jumlah prompt per video (1-10)
  - Level kompleksitas (1-5)
  - Aspect ratio (16:9, 1:1, 9:16)
  - Level variasi (1-5)
- **Database Storage**: Semua data tersimpan di SQLite database
- **Copy Management**: Right-click copy dengan status tracking
- **Progress Tracking**: Real-time progress bar dan status
- **Threading**: Background processing agar UI tetap responsif
- **Statistics**: Tracking jumlah video, prompt generated, dan success rate

## Instalasi

1. **Clone atau extract project ke folder**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Setup API Key**:
   - File `.env` akan otomatis dibuat saat pertama kali menjalankan aplikasi
   - Edit file `.env` dan isi dengan API key kamu:
   ```
   GENAI_API_KEY=your_actual_api_key_here
   ```
   - Atau gunakan Settings di aplikasi

## Cara Penggunaan

### 1. Menambahkan Video
- **Drag & Drop**: Seret file video (.mp4, .avi, .mov, .mkv, .webm) ke tabel
- **Atau**: File akan ditambahkan otomatis ke database

### 2. Mengatur Parameter Generation
- **Mode**: Pilih mode generation:
  - **Selected Videos**: Generate hanya untuk video yang dipilih di tabel
  - **All Videos**: Generate untuk semua video
  - **Ungenerated Only**: Generate hanya untuk video yang belum punya prompt
- **Prompts per Video**: Jumlah prompt yang akan digenerate (1-10)
  - Request besar otomatis dipecah menjadi batch kecil (max 5 per batch)
  - Misal: 20 prompts = 4 batch @ 5 prompts
- **Complexity Level**: 
  - 1: Basic description
  - 2: Detailed scene analysis
  - 3: Advanced cinematography  
  - 4: Professional production
  - 5: Expert creative direction
- **Aspect Ratio**: Format target video (16:9, 1:1, 9:16)
- **Variation Level**: Tingkat variasi dalam prompt (1-5)

### 3. Generate Prompts
1. Pilih mode generation (Selected/All/Ungenerated)
2. Jika mode "Selected", pilih video di tabel terlebih dahulu
3. Klik tombol hijau **"Generate Prompts"**
4. Monitor progress bar dan status (akan menampilkan batch progress)
5. Tunggu hingga proses selesai

### 4. Mengelola Results
- **View Prompts**: Double-click video untuk melihat detail prompts
- **Copy Prompts**: Right-click → "Copy All Prompts" untuk copy ke clipboard
- **Status Tracking**: Row akan berubah warna kuning setelah di-copy

### 5. Mengatur Settings
- Klik **"Settings"** untuk konfigurasi:
  - API Key GenAI
  - Default values
  - Window size
  - Database settings

## Struktur Folder

```
├── main.py                    # Entry point aplikasi
├── config.json                # Konfigurasi aplikasi
├── .env                       # API key (tidak di-track git)
├── .env.example               # Template untuk .env
├── .gitignore                 # Git ignore rules
├── requirements.txt           # Python dependencies
├── data_manager/              # Database management
│   └── database_helper.py
├── user_interface/            # GUI components  
│   ├── main_window.py
│   ├── settings_dialog.py
│   ├── prompts_dialog.py
│   └── custom_widgets/
│       └── video_table.py
├── ai_engine/                 # GenAI integration
│   ├── genai_helper.py
│   └── prompt_generator.py
└── app_utils/                 # Utilities
    ├── config_manager.py
    └── threading_helper.py
```

## Konfigurasi

### API Key (.env file)
API key disimpan di `.env` (tidak di-track git):
```
GENAI_API_KEY=your_api_key_here
```

### Config.json
Settings aplikasi di `config.json`:
- `api`: Model settings
- `generation`: Generation parameters (termasuk `max_prompts_per_batch: 5`)
- `ui`: Interface settings
- `database`: Database configuration
- `video`: Video processing settings

### Database Schema
- **videos**: Video files dengan status tracking
- **prompts**: Generated prompts dengan metadata
- **app_settings**: Application settings

## Troubleshooting

### Error: API Key Not Configured
- Masuk ke Settings → API Settings
- Input GenAI API key yang valid

### Error: Video Upload Failed  
- Check ukuran file (max 500MB default)
- Pastikan format didukung (.mp4, .avi, .mov, .mkv, .webm)
- Check koneksi internet

### Error: Generation Stuck
- Klik "Stop Generation" 
- Check API quota/limits
- Restart aplikasi jika perlu

### Database Issues
- File database: `video_prompts.db` 
- Backup otomatis jika diaktifkan di settings
- Delete file database untuk reset total

## Tips Penggunaan

1. **Generation Modes**: 
   - "Ungenerated Only" untuk video baru (default)
   - "Selected" untuk video tertentu
   - "All" untuk semua video
2. **Smart Batching**: Request besar otomatis dipecah (20 prompts → 4×5)
3. **API Key**: Disimpan aman di `.env`, jangan share file ini

## Development

### Adding New Features
- Semua settings dari `config.json` - no hardcoded values
- Use singleton patterns untuk managers
- Threading untuk long-running operations
- Database untuk persistent storage

### File Naming Convention  
- Folder names: 2 kata dipisah underscore (e.g., `data_manager`, `user_interface`)
- Python files: snake_case
- Classes: PascalCase
- Functions: snake_case

## License

MIT License

Singkatnya, kamu bebas menggunakan, menyalin, memodifikasi, dan mendistribusikan kode ini — termasuk untuk tujuan komersial — selama kamu menyertakan pemberitahuan hak cipta dan teks lisensi MIT yang asli. Lisensi ini juga menyatakan bahwa kode diberikan "as-is" tanpa jaminan apa pun; pemilik tidak bertanggung jawab atas kerusakan yang timbul dari penggunaan perangkat lunak.

Lihat file `LICENSE` untuk teks lengkap lisensi MIT.