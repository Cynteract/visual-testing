import argparse
import logging

from shared.utils import load_env_file

logging.basicConfig(format="%(message)s", level=logging.INFO)


def run_pyinfra(func, host, sudo_password: str, **kwargs):
    hosts = [
        (
            host,
            {},
        )
    ]
    inventory = Inventory((hosts, {}))
    config = Config(SUDO=True, SUDO_PASSWORD=sudo_password)
    state = State(inventory, config)
    connect_all(state)
    add_op(state, func, **kwargs)
    try:
        run_ops(state)
    except PyinfraError as e:
        logging.error("PyinfraError: {0}".format(e))


def assert_env_variable(env, key):
    assert env.get(key) is not None, f"{key} not found in environment"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run tests on Cynteract App.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    vrt_parser = subparsers.add_parser("vrt", help="Deploy visual regression tracker.")
    vrt_parser.add_argument(
        "--host",
        type=str,
        required=True,
        help="Specify the VRT host.",
    )
    vrt_parser.add_argument(
        "--tags",
        type=str,
        required=False,
        help=f"Specify the deployment tags.",
    )

    robot_parser = subparsers.add_parser("robot", help="Deploy test-runner service.")

    args = parser.parse_args()

    env = load_env_file()
    assert_env_variable(env, "ROBOT_USERNAME")
    assert_env_variable(env, "ROBOT_PASSWORD")
    assert_env_variable(env, "GITHUB_PAT")
    assert_env_variable(env, "VRT_API_URL")
    assert_env_variable(env, "VRT_FRONTEND_URL")
    assert_env_variable(env, "VRT_ADMIN_EMAIL")
    assert_env_variable(env, "VRT_ADMIN_PASSWORD")
    assert_env_variable(env, "VRT_ADMIN_API_KEY")

    if args.command == "vrt":
        assert_env_variable(env, "SUDO_PASSWORD")
        assert_env_variable(env, "VRT_POSTGRES_PASSWORD")

        from pyinfra.api.config import Config
        from pyinfra.api.connect import connect_all
        from pyinfra.api.exceptions import PyinfraError
        from pyinfra.api.inventory import Inventory
        from pyinfra.api.operation import add_op
        from pyinfra.api.operations import run_ops
        from pyinfra.api.state import State

        from setup.deploy_vrt import VRTConfig, deploy_vrt

        run_pyinfra(
            deploy_vrt,
            args.host,
            sudo_password=env["SUDO_PASSWORD"],
            vrt_config=VRTConfig(
                postgres_password=env["VRT_POSTGRES_PASSWORD"],
                admin_email=env["VRT_ADMIN_EMAIL"],
                admin_password=env["VRT_ADMIN_PASSWORD"],
                admin_api_key=env["VRT_ADMIN_API_KEY"],
            ),
            tags=args.tags,
        )

    elif args.command == "robot":
        from setup.deploy_robot import deploy_robot

        deploy_robot()