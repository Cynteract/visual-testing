import logging
import os
import shutil
import subprocess
import winreg

import plyvel


def reset_app():
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

    try:
        logging.info(
            "Delete credentials for com.Cynteract.GameCenter.cynteract-a52e4.firebase.auth."
        )
        # see https://github.com/firebase/firebase-cpp-sdk/blob/ec49e5988907840e085630fbfa93b6e42ca2c465/app/src/secure/user_secure_windows_internal.cc#L175
        for i in [0, 1]:
            subprocess.run(
                [
                    "cmdkey",
                    f"/delete:com.Cynteract.GameCenter.cynteract-a52e4.firebase.auth/__FIRAPP_DEFAULT[{i}]",
                ],
                check=True,
            )
    except subprocess.CalledProcessError as e:
        logging.error(f"Error deleting credentials: {e}")

    try:
        logging.info("Delete local storage for *my.cynteract.com from Chrome.")
        db = plyvel.DB(
            "C:/Users/ABrun/AppData/Local/Google/Chrome/User Data/Default/Local Storage/leveldb"
        )
        for key, _ in db:
            decoded_key = key.decode("utf-8")
            if (
                decoded_key.startswith("_https://staging-my.cynteract.com")
                or decoded_key.startswith("_https://testing-my.cynteract.com")
                or decoded_key.startswith("_https://my.cynteract.com")
            ):
                db.delete(key)
    except Exception as e:
        logging.error(f"Error deleting local storage: {e}")


if __name__ == "__main__":
    reset_app()
