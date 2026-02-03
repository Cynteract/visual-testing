from enum import Enum

from pyinfra.api.deploy import deploy
from pyinfra.operations import files, pacman, server, systemd


class Tags(Enum):
    BASE = "base"
    DOCKER = "docker"
    CADDY = "caddy"
    VRT = "vrt"


@deploy("Install Visual Regression Tracker")
def install_vrt(tags: str | None = None):
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
        files.sync(
            name="Copy folder for vrt.",
            dest=f"/home/vrt",
            src="setup/vrt-5.1.1",
            user="vrt",
            group="vrt",
            mode="644",
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
