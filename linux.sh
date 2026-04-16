#!/bin/bash

cd "$(dirname "$0")" || exit 1

echo "🔍 Vérification de Python3..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 n'est pas installé."
    exit 1
fi

if [ -d "env" ]; then
    echo "🔧 Activation de l'environnement virtuel..."
    source env/bin/activate
else
    echo "⚠️  Environnement virtuel non trouvé. Création d'un environnement virtuel..."
    python3 -m venv env
    source env/bin/activate
fi

echo "📦 Installation des dépendances..."
pip install -r requirements.txt 2>/dev/null || {
    echo "⚠️  Fichier requirements.txt non trouvé. Installation manuelle..."
    pip3 install requests beautifulsoup4 pyinstaller playwright
    echo "Installation du navigateur playwright"
    playwright install
}


echo "🔨 Compilation avec PyInstaller..."
pyinstaller --onefile --name fr-scrap main.py

if [ -f "dist/fr-scrap" ]; then
    echo "✅ Compilation réussie!"
    echo "📍 Exécutable : ./fr-scrap"
    mv dist/fr-scrap .
    rm -rf build/ __pycache__/ fr-scrap.spec dist/
else
    echo "❌ Erreur lors de la compilation."
    exit 1
fi
