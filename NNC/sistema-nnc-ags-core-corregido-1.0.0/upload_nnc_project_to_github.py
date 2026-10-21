#!/usr/bin/env python3
"""
upload_nnc_project_to_github.py
Script para subir automáticamente todo el proyecto NNC + AGs-Core a tu GitHub.

Requisitos en tu terminal local:
  pip install PyGithub

Uso en tu máquina local:
  export GITHUB_TOKEN="tu_github_personal_access_token"
  python upload_nnc_project_to_github.py
"""

import os
import sys
from github import Github, GithubException

TOKEN = os.getenv("GITHUB_TOKEN")
if not TOKEN:
    print("❌ Error: Falta la variable de entorno GITHUB_TOKEN.")
    print("Ejecuta en tu terminal: export GITHUB_TOKEN='tu_token_aqui'")
    sys.exit(1)

REPO_NAME = "sistema-nnc-ags-core-agi"
REPO_DESC = "Sistema NNC + AGs-Core (demostración, datos simulados): Detección, triangulación 3D, sensorik satelital y visualización Google Earth 3D"

g = Github(TOKEN)
user = g.get_user()

def get_or_create_repo():
    try:
        repo = user.get_repo(REPO_NAME)
        print(f"ℹ️ El repositorio '{REPO_NAME}' ya existe: {repo.html_url}")
        return repo
    except GithubException:
        print(f"🚀 Creando repositorio '{REPO_NAME}'...")
        repo = user.create_repo(
            name=REPO_NAME,
            description=REPO_DESC,
            private=False,
            auto_init=True
        )
        print(f"✅ Repositorio creado con éxito: {repo.html_url}")
        return repo

def _is_text_file(path):
    text_suffixes = {".py", ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".sql", ".proto", ".sh", ".gitignore", ".tex", ".html", ".css", ".js"}
    return os.path.splitext(path)[1].lower() in text_suffixes or os.path.basename(path) in {"Dockerfile", "LICENSE"}

def upload_project_files(repo):
    root_dir = os.path.dirname(os.path.abspath(__file__))
    ignore_dirs = {'.git', '__pycache__', '.venv', 'venv'}
    
    uploaded_count = 0
    for current_root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            if file == 'upload_nnc_project_to_github.py':
                continue
            full_path = os.path.join(current_root, file)
            rel_path = os.path.relpath(full_path, root_dir).replace(os.sep, '/')
            
            try:
                if not _is_text_file(full_path):
                    print(f"↷ Omitido (binario; usar git push para este tipo de archivo): {rel_path}")
                    continue
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                try:
                    existing_file = repo.get_contents(rel_path)
                    repo.update_file(rel_path, f"Update {rel_path} via AI script", content, existing_file.sha)
                    print(f"🔄 Actualizado: {rel_path}")
                except GithubException:
                    repo.create_file(rel_path, f"Add {rel_path} via AI script", content)
                    print(f"➕ Subido: {rel_path}")
                uploaded_count += 1
            except Exception as e:
                print(f"⚠️ No se pudo subir {rel_path}: {e}")
                
    print(f"\n🎉 ¡Proyecto subido con éxito! ({uploaded_count} archivos subidos/actualizados)")
    print(f"🔗 Repositorio: {repo.html_url}")

if __name__ == "__main__":
    repo = get_or_create_repo()
    if repo:
        upload_project_files(repo)
