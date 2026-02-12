from dataclasses import dataclass
from enum import Enum

from pyinfra.api.deploy import deploy
from pyinfra.operations import files, pacman, server, systemd


class Tags(Enum):
    BASE = "base"
    DOCKER = "docker"
    CADDY = "caddy"
    VRT = "vrt"


@dataclass
class VRTConfig:
    postgres_password: str
    admin_email: str
    admin_password: str
    admin_api_key: str


@deploy("Install Visual Regression Tracker")
def install_vrt(vrt_config: VRTConfig, tags: str | None = None):
    def base():
        pacman.packages(
            name="Install packages.",
            packages=[
                "caddy",
                "docker",
                "docker-compose",
            ],
        )

    def docker():
        systemd.service(
            name="Start docker service.",
            service="docker.service",
            running=True,
            enabled=True,
        )

    def caddy():
        server.user(
            name="Add caddy user.",
            user="caddy",
        )
        files.put(
            name="Update Caddyfile.",
            src="setup/caddy/Caddyfile",
            dest="/etc/caddy/Caddyfile",
            user="caddy",
            group="caddy",
            mode="644",
        )
        files.put(
            name="Update file caddy.service.",
            src="setup/caddy/caddy.service",
            dest="/etc/systemd/system/caddy.service",
            user="root",
            group="root",
            mode="644",
        )
        systemd.service(
            name="Reload caddy service.",
            service="caddy.service",
            running=True,
            enabled=True,
            reloaded=True,
        )

    def vrt():
        server.user(
            name="Add vrt user.",
            user="vrt",
        )
        files.put(
            name="Update docker-compose.yml.",
            dest=f"/home/vrt/docker-compose.yml",
            src="setup/vrt-5.1.1/docker-compose.yml",
            user="vrt",
            group="vrt",
            mode="644",
        )
        files.template(
            name="Update .env file.",
            path="/home/vrt/.env",
            src="setup/vrt-5.1.1/.env.j2",
            dest="/home/vrt/.env",
            user="vrt",
            group="vrt",
            mode="644",
            context={
                "POSTGRES_PASSWORD": vrt_config.postgres_password,
                "DEFAULT_USER_EMAIL": vrt_config.admin_email,
                "DEFAULT_USER_PASSWORD": vrt_config.admin_password,
                "DEFAULT_USER_API_KEY": vrt_config.admin_api_key,
            },
        )
        server.shell(
            name="Start vrt docker containers.",
            commands=[
                "cd /home/vrt && docker compose up -d --no-recreate --remove-orphans",
            ],
        )

    if tags and Tags.BASE.value in tags:
        base()
    if tags and Tags.CADDY.value in tags:
        caddy()
    if tags and Tags.DOCKER.value in tags:
        docker()
    if tags and Tags.VRT.value in tags:
        vrt()
