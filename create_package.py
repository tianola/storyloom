#!/usr/bin/env python3
"""Create code package zip for AI review - only code, no media/models/runtimes."""

import os
import zipfile
import fnmatch

SOURCE_DIR = r'F:\AI-PROJECTS\longform-explainer'
ZIP_PATH = r'F:\AI-PROJECTS\longform-explainer-code-package.zip'

EXCLUDE_PATTERNS = [
    '.venv', '.venv-xpu', 'node_modules', '__pycache__', '.pytest_cache',
    '_scratch', 'models', 'media', 'dist',
    'tools/blender-*', 'models', 'media',
    'work/episode-*', 'work/*/renders', 'work/*/dist', 'work/*/segments',
    'work/*/qc', 'work/*/vo', 'work/*/renders', 'work/*/segments',
    'work/*/edit', 'work/*/music', 'work/*/motion', 'work/*/assets',
    '.venv', '.venv-xpu', 'node_modules', '__pycache__', '.pytest_cache',
    '.superpowers', '.git', '.github', '*.log', '*.tmp', '*.tmp.*',
    '*.mp4', '*.wav', '*.png', '*.jpg', '*.jpeg', '*.webp', '*.gif',
    '*.zip', '*.tar', '*.gz', '*.rar', '*.7z',
    '.vs', '.vscode', '.idea', '*.swp', '*.swo', '*~',
    'Thumbs.db', 'ehthumbs.db', 'Desktop.ini',
]


def should_exclude(rel_path):
    """Check if a relative path matches any exclude pattern."""
    for pattern in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(rel_path, pattern + '/*'):
            return True
    return False


def main():
    SOURCE_DIR = r'F:\AI-PROJECTS\longform-explainer'
    ZIP_PATH = r'F:\AI-PROJECTS\longform-explainer-code-package.zip'

    if os.path.exists(ZIP_PATH):
        os.remove(ZIP_PATH)

    count = 0
    with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root, dirs, files in os.walk(SOURCE_DIR):
            # Filter directories in-place to avoid walking excluded dirs
            rel_root = os.path.relpath(root, SOURCE_DIR).replace('\\', '/')
            if rel_root != '.':
                if should_exclude(rel_root):
                    dirs[:] = []
                    continue

            # Filter subdirs in-place
            dirs[:] = [d for d in dirs if not should_exclude(
                os.path.join(os.path.relpath(root, SOURCE_DIR), d).replace('\\', '/')
            )]

            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(os.path.join(root, file), SOURCE_DIR).replace('\\', '/')

                if not should_exclude(rel_path):
                    zf.write(abs_path, rel_path)
                    print(f'Added: {rel_path}')

    print(f'Done! Created {ZIP_PATH}')


if __name__ == '__main__':
    main()