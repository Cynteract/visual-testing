import logging
import os
import shutil
import subprocess
import winreg
from pathlib import Path

from robot.browser import delete_local_storage
from robot.config import password, username


def _reset_player_prefs():
    try:
        logging.info(
            "Remove registry key HKEY_CURRENT_USER\\Software\\Cynteract\\Cynteract."
        )
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\\Cynteract\\Cynteract",
            0,
            winreg.KEY_ALL_ACCESS,
        ) as key:
            winreg.DeleteKey(key, "")
    except FileNotFoundError:
        pass
    except Exception as e:
        logging.error(f"Error removing registry key: {e}")


def _reset_firestore():
    try:
        logging.info("Remove directories Cynteract, firebase-heartbeat, firestore.")
        for dir_path in [
            os.path.expandvars(
                r"%USERPROFILE%\\AppData\\LocalLow\\Cynteract\\Cynteract"
            ),
            os.path.expandvars(r"%LOCALAPPDATA%\\firebase-heartbeat"),
            os.path.expandvars(r"%LOCALAPPDATA%\\firestore"),
        ]:
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)
    except Exception as e:
        logging.error(f"Error removing directories: {e}")


def _reset_auth():
    # There are multiple cached Firebase auth identities on a dev machine, not just one -
    # confirmed via `cmdkey /list`: GameCenter (prod), ConnectorIntegration (prod), and
    # GameCenter (test project). Missing any one of these lets a session silently survive
    # a "reset" and auto-login on the next run instead of showing the login screen.
    # see https://github.com/firebase/firebase-cpp-sdk/blob/ec49e5988907840e085630fbfa93b6e42ca2c465/app/src/secure/user_secure_windows_internal.cc#L175
    identifiers = [
        "com.Cynteract.GameCenter.cynteract-a52e4.firebase.auth",
        "com.Cynteract.ConnectorIntegration.cynteract-a52e4.firebase.auth",
        "com.Cynteract.GameCenter.cynteract-test.firebase.auth",
    ]
    for identifier in identifiers:
        for i in [0, 1]:
            target = f"{identifier}/__FIRAPP_DEFAULT[{i}]"
            try:
                logging.info(f"Delete credential for {target}.")
                subprocess.run(["cmdkey", f"/delete:{target}"], check=True)
            except subprocess.CalledProcessError as e:
                logging.error(f"Error deleting credential for {target}: {e}")


def _reset_browser_local_storage():
    logging.info("Delete local storage for *my.cynteract.com from browser.")
    try:
        delete_local_storage("my.cynteract.com")
        delete_local_storage("staging-my.cynteract.com")
        delete_local_storage("testing-my.cynteract.com")
    except Exception as e:
        logging.error(f"Error deleting local storage from browser: {e}")


def reset_app_state():
    _reset_player_prefs()
    _reset_firestore()
    _reset_auth()
    _reset_browser_local_storage()


def reset_player_data():
    logging.info("Reset player data for user %s.", username)
    subprocess.run(
        [
            "fnm",
            "exec",
            "npm.cmd",
            "--",
            "run",
            "resetPlayerData",
            "--",
            f"--username={username}",
            f"--password={password}",
        ],
        cwd=Path(__file__).parent.parent / "firebase_user_scripts",
        check=True,
    )


if __name__ == "__main__":
    reset_app_state()
