#!/bin/bash
# Installation for Debian-based systems

# Update the package manager
sudo apt-get update

# Install required packages
sudo apt-get install ffmpeg espeak

# Install Python dependencies
pip3 install -r ./requirements.txt

# Download NLTK data
python3 -m nltk.downloader punkt

# Install vits model from Coqui-ai
~/.local/bin/tts --text "I am excited to demo Phoenix ten point one" --model_name tts_models/en/vctk/vits --speaker_idx p267 --out_path temp.wav

# Cleanup
rm temp.wav