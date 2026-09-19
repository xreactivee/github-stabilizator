# github-stabilizator

A lightweight, automated GitHub repository metadata stabilization tool built with Python that updates repository descriptions, topics, READMEs, and missing licenses.

## Features
- Automates repository metadata updates by scanning and applying changes
- Manages and normalizes repository topics and descriptions
- Handles automatic README rewriting and missing MIT license injection using the GitHub API
- Integrates with the Gemini API for metadata generation and model selection

## Tech Stack
- Python
- Requests
- Python-dotenv

## Installation
```bash
git clone https://github.com/xreactivee/github-stabilizator.git
cd github-stabilizator
pip install -r requirements.txt
```

## Usage
Run the stabilization script from the command line:
```bash
python main.py
```

## License
MIT