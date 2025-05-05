import os

# Path configurations
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output', 'provas_geradas')
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')

# Application settings
APP_NAME = "Prova Guard"
VERSION = "1.0.0"

# AI Configuration
GEMINI_API_KEY = "AIzaSyCoO6FgADLnHT_JTNaF26HqSpHEi0qu2jg"
