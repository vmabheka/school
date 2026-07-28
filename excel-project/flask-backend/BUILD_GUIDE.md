# Build & Distribution Guide

## Quick Reference

| Platform | Build Command | Output |
|----------|---------------|--------|
| **Linux** | `./build.sh` | `dist/ExcelSchools/ExcelSchools` |
| **Linux (portable)** | `./build.sh --portable` | `dist/ExcelSchools-portable` |
| **Windows** | `build.bat` | `dist\ExcelSchools\ExcelSchools.exe` |
| **Windows (portable)** | `build.bat --portable` | `dist\ExcelSchools-portable.exe` |
| **macOS** | `./build_macos.sh` | `dist/ExcelSchools/ExcelSchools` |
| **Docker** | `docker build -t excel-schools .` | Docker image |

---

## Step-by-Step: Building Executables

### 1. Prerequisites

Install Python 3.8+ and pip, then install dependencies:

```bash
pip install -r requirements.txt
pip install pyinstaller
```

### 2. Build for Linux

```bash
# Make build script executable
chmod +x build.sh

# Build both directory-based and portable executables
./build.sh --all

# Or build just one:
./build.sh --portable    # Single-file portable (34MB)
./build.sh --directory   # Directory bundle (73MB)
```

### 3. Build for Windows

```cmd
REM Install PyInstaller first
pip install pyinstaller

REM Build both
build.bat --all

REM Or just one:
build.bat --portable
build.bat --directory
```

### 4. Build for macOS

```bash
chmod +x build_macos.sh
./build_macos.sh --all
```

### 5. Build with Docker

```bash
docker build -t excel-schools .
docker run -p 5000:5000 excel-schools
```

---

## Creating Windows Installer (.exe)

1. Install [Inno Setup](https://jrsoftware.org/isinfo.php)
2. Run `build.bat --all` first
3. Open `installer.iss` in Inno Setup Compiler
4. Click **Build > Compile**
5. Output: `installer_output/ExcelSchools-Setup-1.0.0.exe`

---

## Creating Distribution Packages

After building, run the package script:

```bash
chmod +x package.sh
./package.sh
```

This creates:
- `dist/ExcelSchools-1.0.0-linux-x86_64.tar.gz`
- `dist/ExcelSchools-1.0.0-linux-x86_64.zip`

Each package contains:
- Executable(s)
- README.md
- run.sh / run.bat launcher scripts
- install.sh (Linux installer to /opt/excel-schools)
- uninstall.sh

---

## Running the Executables

### Portable (Single-File)
```bash
# Linux/macOS
./ExcelSchools-portable

# Windows
ExcelSchools-portable.exe
```

### Directory Bundle
```bash
# Linux/macOS
cd ExcelSchools
./ExcelSchools

# Windows
cd ExcelSchools
ExcelSchools.exe
```

### Command-Line Options
```
--online         Run in online mode (enables API sync push)
--init-only      Initialize database only
--port PORT      Run on custom port (default: 5000)
--host HOST      Bind to host (default: 0.0.0.0)
--debug          Enable debug mode
```

---

## Deployment Scenarios

### Scenario 1: Offline School Network
1. Build executable for the school's OS
2. Copy to school server
3. Run: `./ExcelSchools --host 0.0.0.0`
4. Access from any computer: `http://SERVER_IP:5000`

### Scenario 2: Online (School Website)
1. Deploy to cloud server (AWS, DigitalOcean, etc.)
2. Use Docker or Gunicorn for production
3. Set environment variables:
   - `DATABASE_URL=postgresql://...`
   - `SECRET_KEY=your-secure-key`
   - `DEPLOYMENT_MODE=online`

### Scenario 3: Offline + Online Sync
1. Run offline on school server
2. Periodically export data (Sync Center → Export)
3. Upload exported JSON to online system
4. Online system imports and merges data

---

## File Sizes (Approximate)

| Type | Linux | Windows | macOS |
|------|-------|---------|-------|
| Portable .exe | ~34MB | ~35MB | ~38MB |
| Directory bundle | ~73MB | ~75MB | ~78MB |
| Windows Installer | ~30MB | - | - |
| Docker image | ~200MB | - | - |
