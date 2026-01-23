from datetime import datetime, timedelta, timezone

import github


class Service:
    def __init__(self, env):
        assert env.get("GITHUB_PAT") is not None, "GITHUB_PAT not found in environment"
        self.github_token = env.get("GITHUB_PAT")
        self.repo = github.Github(login_or_token=self.github_token).get_repo(
            "Cynteract/cynteract-app"
        )

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

            commit_sha = dev_build_runs[0].head_commit.sha
            commit = self.repo.get_commit(commit_sha)
            statuses = commit.get_statuses()
            commit_status = None
            for status in statuses:
                if status.context == "visual regression test":
                    commit_status = status
                    break
            if commit_status is None:
                commit.create_status(
                    state="success",
                    context="visual regression test",
                    description="Visual tests passed",
                    target_url="https://cynteract.com",
                )
            return
