import logging
import os
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from robot.config import get_builds_download_dir


def deploy_robot():
    if sys.platform != "win32":
        logging.error("Robot deployment is only supported on Windows.")
        sys.exit(1)
    logging.info("Platform Windows OK")

    project_root = Path(__file__).parent.parent.parent.resolve()
    os.chdir(project_root)

    # Check python version against .python-version
    expected_version = (project_root / ".python-version").read_text().strip()
    if not sys.version.startswith(expected_version):
        logging.warning(
            f"Python version mismatch. Expected: {expected_version}, Found: {sys.version.split()[0]}"
        )
    logging.info(f"Python version OK")

    # Create virtual environment in repository root if it doesn't exist
    venv_folder = project_root / ".venv"
    venv_python = venv_folder / "Scripts" / "python.exe"
    if not venv_python.exists():
        logging.info(f"Creating virtual environment in {venv_folder} ...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_folder)])

    # Activate virtual environment if not already activated
    if not Path(sys.executable).samefile(venv_python):
        logging.info(f"Activating virtual environment {venv_python} ...")
        venv_process = subprocess.run(
            executable=str(venv_python), args=[str(venv_python), *sys.argv], shell=False
        )
        sys.exit(venv_process.returncode)
    else:
        logging.info(f"Virtual environment OK")

    requirements_path = project_root / "requirements.txt"
    with open(requirements_path) as f:
        required_packages = [
            line.split()[0] for line in f if line.strip() and not line.startswith("#")
        ]

    installed_packages = {
        pkg.metadata["Name"].lower() for pkg in metadata.distributions()
    }
    needs_reinstall = False
    for package in required_packages:
        if package.lower() not in installed_packages:
            needs_reinstall = True
            logging.info(f"Package [{package}] not installed.")
    if needs_reinstall:
        logging.info("Installing missing pip requirements...")
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", "-r", str(requirements_path)]
        )
        venv_process = subprocess.run(
            executable=str(venv_python), args=[str(venv_python), *sys.argv], shell=False
        )
        sys.exit(venv_process.returncode)
    else:
        logging.info("Pip requirements OK")

    # Install node and dependencies for firebase user scripts if not already installed
    firebase_scripts_dir = project_root / "src" / "firebase_user_scripts"
    if not (firebase_scripts_dir / "node_modules").exists():
        logging.info(f"Install node dependencies for firebase user scripts.")
        subprocess.run(["fnm", "install"], cwd=firebase_scripts_dir, check=True)
        subprocess.run(
            ["fnm", "exec", "npm.cmd", "install"],
            cwd=firebase_scripts_dir,
            check=True,
        )
    else:
        logging.info(f"Node dependencies for firebase user scripts OK")

    # Create script in autostart folder
    startup_bat = (
        Path(os.environ["APPDATA"])
        / "Microsoft/Windows/Start Menu/Programs/Startup"
        / "start_cynteract_robot.bat"
    )
    if not startup_bat.exists():
        logging.info(f"Create start_cynteract_robot.bat in startup folder.")
        python_path = Path(sys.executable).resolve()
        with open(startup_bat, "w") as bat_file:
            bat_content = f'@echo off\nset PYTHONPATH=src\ncd {project_root}\n"{python_path}" -m github_service\n'
            bat_file.write(bat_content)
    else:
        logging.info(f"Startup script OK")

    # Add Windows Defender security exception
    logging.info(f"Add Windows Defender exclusion for builds download directory.")
    exclusion_path = get_builds_download_dir()
    subprocess.run(
        [
            "powershell",
            "-Command",
            f"Start-Process powershell -ArgumentList \"Add-MpPreference -ExclusionPath '{exclusion_path}'\" -Verb RunAs",
        ]
    )
