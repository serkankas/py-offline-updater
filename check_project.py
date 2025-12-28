#!/usr/bin/env python3
"""
py-offline-updater - Project Health Check
Tüm proje yapısını, kodu ve gereksinimleri kontrol eder.
"""

import os
import sys
import subprocess
from pathlib import Path
import ast
import re

# Renkli output için
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")

def print_ok(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_fail(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")

# Proje root
PROJECT_ROOT = Path(__file__).parent

def check_file_structure():
    """Dosya yapısını kontrol et"""
    print_header("1. DOSYA YAPISI KONTROLÜ")
    
    required_files = {
        'src/bootstrap.py': 'Bootstrap script',
        'src/update_engine/__init__.py': 'Engine module',
        'src/update_engine/engine.py': 'Ana engine',
        'src/update_engine/actions.py': 'Action implementations',
        'src/update_engine/checks.py': 'Check implementations',
        'src/update_engine/backup.py': 'Backup sistem',
        'src/update_engine/state.py': 'State management',
        'src/update_engine/utils.py': 'Utilities',
        'src/update_service/main.py': 'FastAPI service',
        'src/update_service/config.py': 'Config',
        'src/update_service/api/endpoints.py': 'API endpoints',
        'src/update_service/frontend/index.html': 'Web UI',
        'src/update_service/frontend/static/css/style.css': 'CSS',
        'src/update_service/frontend/static/js/app.js': 'JavaScript',
        'scripts/install.sh': 'Install script',
        'scripts/build_package.sh': 'Package builder',
        'requirements.txt': 'Root requirements',
        'src/update_service/requirements.txt': 'Service requirements',
        'package.json': 'Semantic release config',
        '.releaserc.json': 'Release config',
        '.gitignore': 'Git ignore',
        'README.md': 'Documentation',
    }
    
    missing = []
    for filepath, description in required_files.items():
        full_path = PROJECT_ROOT / filepath
        if full_path.exists():
            print_ok(f"{description}: {filepath}")
        else:
            print_fail(f"{description}: {filepath} - EKSIK!")
            missing.append(filepath)
    
    if missing:
        print_warning(f"Eksik dosyalar: {len(missing)}")
        return False
    return True

def check_python_syntax():
    """Python dosyalarının syntax kontrolü"""
    print_header("2. PYTHON SYNTAX KONTROLÜ")
    
    python_files = list(PROJECT_ROOT.glob('src/**/*.py'))
    errors = []
    
    for py_file in python_files:
        try:
            with open(py_file, 'r') as f:
                ast.parse(f.read())
            print_ok(f"Syntax OK: {py_file.relative_to(PROJECT_ROOT)}")
        except SyntaxError as e:
            print_fail(f"Syntax Error: {py_file.relative_to(PROJECT_ROOT)} - {e}")
            errors.append(py_file)
    
    if errors:
        print_warning(f"Syntax hataları: {len(errors)}")
        return False
    return True

def check_maritime_references():
    """Maritime referanslarını kontrol et"""
    print_header("3. MARITIME REFERANS KONTROLÜ")
    
    exclude_dirs = {'venv', 'node_modules', '__pycache__', '.git'}
    maritime_found = []
    
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if file.endswith(('.py', '.md', '.yml', '.yaml', '.sh', '.html', '.js')):
                filepath = Path(root) / file
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if 'maritime' in content.lower():
                            matches = re.findall(r'.{0,30}maritime.{0,30}', content.lower())
                            maritime_found.append((filepath.relative_to(PROJECT_ROOT), matches[:3]))
                except:
                    pass
    
    if maritime_found:
        print_fail("Maritime referansları bulundu:")
        for filepath, matches in maritime_found:
            print(f"  📄 {filepath}")
            for match in matches:
                print(f"    └─ {match.strip()}")
        return False
    else:
        print_ok("Maritime referansı yok")
        return True

def check_hardcoded_paths():
    """Hardcoded path kontrolü"""
    print_header("4. HARDCODED PATH KONTROLÜ")
    
    suspicious_paths = ['/app/app', '/opt/updater', '/home/']
    exclude_files = {'install.sh', 'README.md', 'manifest.yml'}
    found_paths = []
    
    python_files = list(PROJECT_ROOT.glob('src/**/*.py'))
    
    for py_file in python_files:
        if py_file.name in exclude_files:
            continue
            
        try:
            with open(py_file, 'r') as f:
                content = f.read()
                for path in suspicious_paths:
                    if path in content and 'example' not in content.lower():
                        matches = re.findall(f'.{{0,40}}{re.escape(path)}.{{0,40}}', content)
                        found_paths.append((py_file.relative_to(PROJECT_ROOT), path, matches[:2]))
        except:
            pass
    
    if found_paths:
        print_warning("Hardcoded path'ler bulundu (config'den alınmalı):")
        for filepath, path, matches in found_paths:
            print(f"  📄 {filepath}")
            print(f"    └─ Path: {path}")
            for match in matches:
                print(f"       {match.strip()}")
        return False
    else:
        print_ok("Hardcoded path yok")
        return True

def check_engine_features():
    """Engine özelliklerini kontrol et"""
    print_header("5. ENGINE ÖZELLİKLERİ KONTROLÜ")
    
    checks = []
    
    # actions.py kontrolü
    actions_file = PROJECT_ROOT / 'src/update_engine/actions.py'
    if actions_file.exists():
        with open(actions_file, 'r') as f:
            content = f.read()
            
            # Action types
            required_actions = [
                'command', 'backup', 'restore_backup',
                'docker_compose_down', 'docker_compose_up', 
                'docker_load', 'docker_prune',
                'file_copy', 'file_sync', 'file_merge'
            ]
            
            for action in required_actions:
                if f"'{action}'" in content or f'"{action}"' in content:
                    print_ok(f"Action type: {action}")
                    checks.append(True)
                else:
                    print_fail(f"Action type eksik: {action}")
                    checks.append(False)
            
            # file_sync modes
            if 'mirror' in content and 'add_only' in content and 'overwrite_existing' in content:
                print_ok("file_sync modes: mirror, add_only, overwrite_existing")
                checks.append(True)
            else:
                print_fail("file_sync modes eksik")
                checks.append(False)
            
            # file_merge strategies
            if 'keep_existing' in content and 'overwrite_all' in content and 'merge_keys' in content:
                print_ok("file_merge strategies: keep_existing, overwrite_all, merge_keys")
                checks.append(True)
            else:
                print_fail("file_merge strategies eksik")
                checks.append(False)
    else:
        print_fail("actions.py bulunamadı")
        checks.append(False)
    
    # checks.py kontrolü
    checks_file = PROJECT_ROOT / 'src/update_engine/checks.py'
    if checks_file.exists():
        with open(checks_file, 'r') as f:
            content = f.read()
            
            required_checks = [
                'disk_space', 'docker_running', 'file_exists',
                'docker_health', 'http_check', 'service_running'
            ]
            
            for check in required_checks:
                if f"'{check}'" in content or f'"{check}"' in content:
                    print_ok(f"Check type: {check}")
                    checks.append(True)
                else:
                    print_fail(f"Check type eksik: {check}")
                    checks.append(False)
    else:
        print_fail("checks.py bulunamadı")
        checks.append(False)
    
    # backup.py - sequential naming
    backup_file = PROJECT_ROOT / 'src/update_engine/backup.py'
    if backup_file.exists():
        with open(backup_file, 'r') as f:
            content = f.read()
            
            if 'backup_' in content and ('001' in content or '{:03d}' in content):
                print_ok("Backup: Sequential naming (backup_001)")
                checks.append(True)
            else:
                print_fail("Backup: Sequential naming eksik")
                checks.append(False)
            
            if 'latest' in content and 'symlink' in content.lower():
                print_ok("Backup: 'latest' symlink")
                checks.append(True)
            else:
                print_fail("Backup: 'latest' symlink eksik")
                checks.append(False)
            
            if 'CHECKSUM' in content:
                print_ok("Backup: CHECKSUM dosyası")
                checks.append(True)
            else:
                print_fail("Backup: CHECKSUM dosyası eksik")
                checks.append(False)
            
            if 'metadata.json' in content:
                print_ok("Backup: metadata.json")
                checks.append(True)
            else:
                print_fail("Backup: metadata.json eksik")
                checks.append(False)
    else:
        print_fail("backup.py bulunamadı")
        checks.append(False)
    
    # state.py - power failure recovery
    state_file = PROJECT_ROOT / 'src/update_engine/state.py'
    if state_file.exists():
        with open(state_file, 'r') as f:
            content = f.read()
            
            if 'checksum' in content.lower():
                print_ok("State: Checksum protection")
                checks.append(True)
            else:
                print_fail("State: Checksum protection eksik")
                checks.append(False)
            
            if 'in_progress' in content:
                print_ok("State: Incomplete update detection")
                checks.append(True)
            else:
                print_fail("State: Incomplete update detection eksik")
                checks.append(False)
    else:
        print_fail("state.py bulunamadı")
        checks.append(False)
    
    # bootstrap.py
    bootstrap_file = PROJECT_ROOT / 'src/bootstrap.py'
    if bootstrap_file.exists():
        with open(bootstrap_file, 'r') as f:
            content = f.read()
            
            if 'CHECKSUM' in content and 'verify' in content.lower():
                print_ok("Bootstrap: Engine checksum verification")
                checks.append(True)
            else:
                print_fail("Bootstrap: Engine checksum verification eksik")
                checks.append(False)
            
            if 'fallback' in content.lower() or 'previous' in content.lower():
                print_ok("Bootstrap: Fallback to previous engine")
                checks.append(True)
            else:
                print_fail("Bootstrap: Fallback logic eksik")
                checks.append(False)
    else:
        print_fail("bootstrap.py bulunamadı")
        checks.append(False)
    
    return all(checks)

def check_hash_algorithm():
    """Hash algoritması kontrolü (MD5 olmalı)"""
    print_header("6. HASH ALGORİTMASI KONTROLÜ")
    
    utils_file = PROJECT_ROOT / 'src/update_engine/utils.py'
    if utils_file.exists():
        with open(utils_file, 'r') as f:
            content = f.read()
            
            if 'hashlib.md5' in content:
                print_ok("Hash: MD5 kullanılıyor")
                return True
            elif 'hashlib.sha256' in content:
                print_warning("Hash: SHA256 kullanılıyor (MD5 olmalı)")
                return False
            else:
                print_fail("Hash: Algoritma bulunamadı")
                return False
    else:
        print_fail("utils.py bulunamadı")
        return False

def check_api_endpoints():
    """API endpoints kontrolü"""
    print_header("7. API ENDPOINTS KONTROLÜ")
    
    endpoints_file = PROJECT_ROOT / 'src/update_service/api/endpoints.py'
    if endpoints_file.exists():
        with open(endpoints_file, 'r') as f:
            content = f.read()
            
            required_endpoints = [
                '/api/system-info',
                '/api/upload-update',
                '/api/apply-update',
                '/api/update-status',
                '/api/update-stream',
                '/api/rollback',
                '/api/backups'
            ]
            
            checks = []
            for endpoint in required_endpoints:
                if endpoint in content:
                    print_ok(f"Endpoint: {endpoint}")
                    checks.append(True)
                else:
                    print_fail(f"Endpoint eksik: {endpoint}")
                    checks.append(False)
            
            # SSE kontrolü
            if 'EventSourceResponse' in content or 'text/event-stream' in content:
                print_ok("SSE: Server-Sent Events support")
                checks.append(True)
            else:
                print_fail("SSE: Server-Sent Events eksik")
                checks.append(False)
            
            return all(checks)
    else:
        print_fail("endpoints.py bulunamadı")
        return False

def check_frontend():
    """Frontend kontrolü"""
    print_header("8. FRONTEND KONTROLÜ")
    
    index_file = PROJECT_ROOT / 'src/update_service/frontend/index.html'
    js_file = PROJECT_ROOT / 'src/update_service/frontend/static/js/app.js'
    
    checks = []
    
    if index_file.exists():
        with open(index_file, 'r') as f:
            content = f.read()
            
            if 'drag' in content.lower() and 'drop' in content.lower():
                print_ok("UI: Drag & drop support")
                checks.append(True)
            else:
                print_fail("UI: Drag & drop eksik")
                checks.append(False)
            
            if 'progress' in content.lower():
                print_ok("UI: Progress bar")
                checks.append(True)
            else:
                print_fail("UI: Progress bar eksik")
                checks.append(False)
            
            if 'incomplete' in content.lower() or 'recovery' in content.lower():
                print_ok("UI: Incomplete update recovery prompt")
                checks.append(True)
            else:
                print_warning("UI: Incomplete update recovery prompt eksik (olabilir)")
                checks.append(True)  # Optional
    else:
        print_fail("index.html bulunamadı")
        checks.append(False)
    
    if js_file.exists():
        with open(js_file, 'r') as f:
            content = f.read()
            
            if 'EventSource' in content:
                print_ok("JS: SSE (EventSource)")
                checks.append(True)
            else:
                print_fail("JS: SSE eksik")
                checks.append(False)
    else:
        print_fail("app.js bulunamadı")
        checks.append(False)
    
    return all(checks)

def check_scripts():
    """Script dosyaları kontrolü"""
    print_header("9. SCRIPT KONTROLÜ")
    
    install_script = PROJECT_ROOT / 'scripts/install.sh'
    build_script = PROJECT_ROOT / 'scripts/build_package.sh'
    
    checks = []
    
    if install_script.exists():
        with open(install_script, 'r') as f:
            content = f.read()
            
            if '--base-dir' in content or 'BASE_DIR' in content:
                print_ok("install.sh: --base-dir parameter")
                checks.append(True)
            else:
                print_fail("install.sh: --base-dir parameter eksik")
                checks.append(False)
            
            if install_script.stat().st_mode & 0o111:
                print_ok("install.sh: Executable permission")
                checks.append(True)
            else:
                print_warning("install.sh: Executable permission yok (chmod +x gerekebilir)")
                checks.append(True)  # Not critical
    else:
        print_fail("install.sh bulunamadı")
        checks.append(False)
    
    if build_script.exists():
        with open(build_script, 'r') as f:
            content = f.read()
            
            if 'checksums.md5' in content or 'checksum' in content.lower():
                print_ok("build_package.sh: Checksum generation")
                checks.append(True)
            else:
                print_fail("build_package.sh: Checksum generation eksik")
                checks.append(False)
            
            if build_script.stat().st_mode & 0o111:
                print_ok("build_package.sh: Executable permission")
                checks.append(True)
            else:
                print_warning("build_package.sh: Executable permission yok")
                checks.append(True)
    else:
        print_fail("build_package.sh bulunamadı")
        checks.append(False)
    
    return all(checks)

def check_examples():
    """Örnek manifest'leri kontrol et"""
    print_header("10. ÖRNEK MANIFEST KONTROLÜ")
    
    example_dirs = [
        'examples/docker-app',
        'examples/python-service',
        'examples/full-system'
    ]
    
    checks = []
    
    for example_dir in example_dirs:
        manifest_file = PROJECT_ROOT / example_dir / 'manifest.yml'
        if manifest_file.exists():
            print_ok(f"Manifest: {example_dir}/manifest.yml")
            checks.append(True)
        else:
            print_fail(f"Manifest eksik: {example_dir}/manifest.yml")
            checks.append(False)
    
    # Full-system özel kontrol (senin use case'in)
    full_system_manifest = PROJECT_ROOT / 'examples/full-system/manifest.yml'
    if full_system_manifest.exists():
        with open(full_system_manifest, 'r') as f:
            content = f.read()
            
            important_actions = [
                'systemctl stop',
                'docker-compose',
                'file_sync',
                'file_merge'
            ]
            
            for action in important_actions:
                if action in content:
                    print_ok(f"full-system: '{action}' action var")
                else:
                    print_warning(f"full-system: '{action}' action yok (olmalı)")
    
    return all(checks)

def check_dependencies():
    """Dependency kontrolü"""
    print_header("11. DEPENDENCY KONTROLÜ")
    
    root_req = PROJECT_ROOT / 'requirements.txt'
    service_req = PROJECT_ROOT / 'src/update_service/requirements.txt'
    
    checks = []
    
    required_root = ['pyyaml', 'python-dotenv']
    required_service = ['fastapi', 'uvicorn', 'python-multipart', 'aiofiles', 'sse-starlette']
    
    if root_req.exists():
        with open(root_req, 'r') as f:
            content = f.read().lower()
            for dep in required_root:
                if dep in content:
                    print_ok(f"Root dependency: {dep}")
                    checks.append(True)
                else:
                    print_fail(f"Root dependency eksik: {dep}")
                    checks.append(False)
    else:
        print_fail("requirements.txt bulunamadı")
        checks.append(False)
    
    if service_req.exists():
        with open(service_req, 'r') as f:
            content = f.read().lower()
            for dep in required_service:
                if dep in content:
                    print_ok(f"Service dependency: {dep}")
                    checks.append(True)
                else:
                    print_fail(f"Service dependency eksik: {dep}")
                    checks.append(False)
    else:
        print_fail("src/update_service/requirements.txt bulunamadı")
        checks.append(False)
    
    return all(checks)

def check_semantic_release():
    """Semantic release config kontrolü"""
    print_header("12. SEMANTIC RELEASE KONTROLÜ")
    
    package_json = PROJECT_ROOT / 'package.json'
    releaserc = PROJECT_ROOT / '.releaserc.json'
    
    checks = []
    
    if package_json.exists():
        print_ok("package.json mevcut")
        checks.append(True)
        
        with open(package_json, 'r') as f:
            content = f.read()
            if 'semantic-release' in content:
                print_ok("package.json: semantic-release configured")
                checks.append(True)
            else:
                print_fail("package.json: semantic-release eksik")
                checks.append(False)
    else:
        print_fail("package.json bulunamadı")
        checks.append(False)
    
    if releaserc.exists():
        print_ok(".releaserc.json mevcut")
        checks.append(True)
    else:
        print_fail(".releaserc.json bulunamadı")
        checks.append(False)
    
    return all(checks)

def main():
    """Ana kontrol fonksiyonu"""
    print(f"\n{Colors.BOLD}🔍 py-offline-updater - Project Health Check{Colors.END}\n")
    
    results = {}
    
    results['file_structure'] = check_file_structure()
    results['python_syntax'] = check_python_syntax()
    results['no_maritime'] = check_maritime_references()
    results['no_hardcoded_paths'] = check_hardcoded_paths()
    results['engine_features'] = check_engine_features()
    results['hash_algorithm'] = check_hash_algorithm()
    results['api_endpoints'] = check_api_endpoints()
    results['frontend'] = check_frontend()
    results['scripts'] = check_scripts()
    results['examples'] = check_examples()
    results['dependencies'] = check_dependencies()
    results['semantic_release'] = check_semantic_release()
    
    # Özet
    print_header("📊 ÖZET")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed
    
    for check, result in results.items():
        status = f"{Colors.GREEN}PASS{Colors.END}" if result else f"{Colors.RED}FAIL{Colors.END}"
        print(f"{status} - {check.replace('_', ' ').title()}")
    
    print(f"\n{Colors.BOLD}Toplam: {total} | Başarılı: {passed} | Başarısız: {failed}{Colors.END}")
    
    if failed == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 Tüm kontroller başarılı! Proje hazır!{Colors.END}\n")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}⚠️  {failed} kontrol başarısız! Düzeltme gerekiyor.{Colors.END}\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())