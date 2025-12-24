#!/usr/bin/env python3
"""Generate version from git commit SHA for WPM package.

This script generates a version string from the current git commit SHA
and updates VERSION.txt for PEP 621 compliance.
"""

import subprocess
import sys
from pathlib import Path

def get_git_version():
    """Get version from git using setuptools-scm format."""
    try:
        # Try to get version using git describe (for tagged commits)
        result = subprocess.run(
            ["git", "describe", "--tags", "--dirty", "--always"],
            capture_output=True,
            text=True,
            check=True,
        )
        git_describe = result.stdout.strip()
        
        # Get short SHA
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        sha = result.stdout.strip()
        
        # Check if working tree is dirty
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
        is_dirty = bool(result.stdout.strip())
        
        # Format as dev version with SHA
        # For bleeding edge dev, use format: 0.1.0.dev{N}+g{sha}
        # If dirty, add .dirty
        if is_dirty:
            version = f"0.1.0.dev0+g{sha}.dirty"
        else:
            version = f"0.1.0.dev0+g{sha}"
            
        return version
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        # Fallback if git is not available
        print(f"Warning: Could not get git version: {e}", file=sys.stderr)
        return "0.1.0.dev0"

def main():
    """Generate version file."""
    repo_root = Path(__file__).parent.parent
    version_file = repo_root / "src" / "wpm" / "VERSION.txt"
    
    version = get_git_version()
    
    version_file.parent.mkdir(parents=True, exist_ok=True)
    version_file.write_text(f"{version}\n", encoding="utf-8")
    
    print(f"Generated version: {version}")
    print(f"Written to: {version_file}")

if __name__ == "__main__":
    main()

