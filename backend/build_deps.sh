#!/usr/bin/env bash
# build_deps.sh — run this as the Render build command
# Installs both system packages and Python dependencies

set -e

echo "==> Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
  poppler-utils \       # pdf2image needs pdfinfo + pdftoppm
  ffmpeg \              # video/audio processing
  libgl1-mesa-glx \     # opencv headless needs this on some Render images
  libglib2.0-0          # also needed by opencv

echo "==> Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Build complete."
