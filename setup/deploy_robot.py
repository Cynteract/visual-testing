import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from robot.config import get_builds_download_dir


@dataclass
class RobotConfig:
    vrt_email: str
    vrt_password: str
    vrt_api_key: str


def deploy_robot(robot_config: RobotConfig):
    if sys.platform != "win32":
        logging.error("Robot deployment is only supported on Windows.")
        sys.exit(1)
    logging.info("Platform Windows OK")

    project_root = Path(__file__).parent.parent.resolve()
    os.chdir(project_root)

    # Check python version against .python-version
    expected_version = (project_root / ".python-version").read_text().strip()
    if not sys.version.startswith(expected_version):
        logging.warning(
            f"Python version mismatch. Expected: {expected_version}, Found: {sys.version.split()[0]}"
        )
    logging.info(f"Python version OK")

    # Create virtual environment in repository root if it doesn't exist
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        logging.info(f"Create virtual environment in {venv_python} .")
        subprocess.run([sys.executable, "-m", "venv", str(project_root / ".venv")])

    # Activate virtual environment if not already activated
    if not Path(sys.executable).samefile(venv_python):
        logging.info(f"Activate virtual environment {venv_python} .")
        venv_process = subprocess.run([str(venv_python), __file__])
        sys.exit(venv_process.returncode)
    else:
        logging.info(f"Virtual environment OK")

    # Install requirements if not already installed
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
            break
    if needs_reinstall:
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", "-r", str(requirements_path)]
        )
    else:
        logging.info(f"Pip requirements OK")

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
            bat_content = (
                f'@echo off\ncd {project_root}\n"{python_path}" -m github_service\n'
            )
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
