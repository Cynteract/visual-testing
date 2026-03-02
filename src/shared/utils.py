def load_env_file() -> dict[str, str]:
    # Load .env file
    env = {}
    with open(".env") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                key, value = line.strip().split("=", 1)
                env[key] = value
    return env
