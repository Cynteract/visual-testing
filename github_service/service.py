import asyncio
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import github
import requests


class TestResult:
    def __init__(self, passed: bool, details: str):
        self.passed = passed
        self.details = details


class Service:
    def __init__(self, env):
        assert env.get("GITHUB_PAT") is not None, "GITHUB_PAT not found in environment"
        self.github_token = env.get("GITHUB_PAT")
        self.repo = github.Github(login_or_token=self.github_token).get_repo(
            "Cynteract/cynteract-app"
        )

    async def execute_command(self, *args: str, **kwargs) -> str:
        print(f"Executing command: {' '.join(args)}")
        subprocess_result = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **kwargs,
        )
        stdout, stderr = await subprocess_result.communicate()
        if subprocess_result.returncode != 0:
            raise RuntimeError(
                f"Command failed with code {subprocess_result.returncode}: {stderr.decode()}"
            )
        return stdout.decode().strip()

    async def get_version_info(self, *args: str) -> str:
        # needs the cynteract-app repo to be cloned locally
        app_dir = Path("../cynteract-app")
        if not app_dir.exists():
            # clone the repo with PAT
            clone_url = self.repo.clone_url.replace(
                "https://", f"https://{self.github_token}@"
            )
            await self.execute_command("git", "clone", clone_url, app_dir.as_posix())
        else:
            # fetch the latest changes
            await self.execute_command("git", "fetch", "origin", cwd=app_dir.as_posix())
        version_info = await self.execute_command(
            sys.executable, "tools/get_version_info.py", *args, cwd=app_dir.as_posix()
        )
        return version_info

    async def run_test(self, version: str) -> TestResult:
        try:
            await self.get_app_folder(version)
        except Exception as e:
            return TestResult(passed=False, details=str(e))
        return TestResult(passed=True, details="All tests passed")

    async def get_app_folder(self, version: str) -> Path:
        app_folder = Path.home() / "Downloads" / "builds" / f"Cynteract-{version}"
        if not app_folder.exists():
            zip_path = app_folder.with_name(app_folder.name + ".zip")
            if not zip_path.exists():
                # download the build zip from Google Cloud Storage
                base_url = "https://storage.googleapis.com/cynteract-unity-auto-build"
                download_url = f"{base_url}/windows/{zip_path.name}"
                print(f"Downloading build from {download_url}...")
                zip_path.parent.mkdir(parents=True, exist_ok=True)
                response = requests.get(download_url, stream=True)
                response.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=32768):
                        f.write(chunk)
            # extract the zip
            print(f"Extracting build to {app_folder}/...")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(app_folder)
        return app_folder

    async def process_commit(self, commit_sha: str):
        commit = self.repo.get_commit(commit_sha)
        commit_status = None
        for status in commit.get_statuses():
            if status.context == "visual regression test":
                commit_status = status
                break
        if commit_status is None:
            version_info = await self.get_version_info(
                "--ci-development", "--commitish=" + commit.sha
            )
            version_string, file_name_base, bundle_version_code = version_info.split(
                ","
            )
            test_result = await self.run_test(file_name_base)
            print(
                f"Test result for commit {commit.sha}: {'PASSED' if test_result.passed else 'FAILED'} - {test_result.details}"
            )
            # commit.create_status(
            #     state="success" if test_result.passed else "failure",
            #     context="visual regression test",
            #     description=test_result.details,
            #     target_url="https://cynteract.com",
            # )

    async def run(self):
        # poll action runs
        actions = self.repo.get_workflows()
        dev_build = None
        pr_build = None
        for action in actions:
            if action.name == ".github/workflows/on-development-push.yaml":
                dev_build = action
            elif action.name == ".github/workflows/on-pr-commit.yaml":
                pr_build = action
        assert dev_build is not None, "Development build workflow not found"
        assert pr_build is not None, "PR build workflow not found"

        # don't consider runs older than 7 days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)

        while True:
            # API docs: https://docs.github.com/en/rest/actions/workflow-runs?apiVersion=2022-11-28#list-workflow-runs-for-a-repository
            dev_build_runs = dev_build.get_runs(
                status="success", created=f">{cutoff_date.strftime('%Y-%m-%d')}"
            )
            # pr_build_runs = pr_build.get_runs(
            #     status="success", created=f">{cutoff_date.strftime('%Y-%m-%d')}"
            # )

            cutoff_date = datetime.now(timezone.utc) - timedelta(minutes=5)

            for run in dev_build_runs:
                await self.process_commit(run.head_sha)
                return
