"""Runner script that:

1. Ensures an env file exists (and is gitignored).
2. Optionally prompts for missing values (e.g. GitHub PAT).
3. Verifies Docker is installed and usable.
4. If Docker is missing, offers best-effort installation
   using platform-appropriate tools (choco / apt / brew).
5. Runs: docker compose pull
6. Runs: docker compose up
"""

import argparse
import getpass
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def r_ensure_gitignore_entry(path: Path) -> None:
    gitignore = Path(".gitignore")
    if not gitignore.exists():
        return
    rel = path.as_posix()
    lines = gitignore.read_text(encoding="utf-8").splitlines()
    if rel in lines:
        return
    lines.append(rel)
    gitignore.write_text("".join(lines) + "", encoding="utf-8")


def r_prompt_new_env(env_path: Path) -> None:
    print(f"{env_path} does not exist.")
    answer = input("Create a new env file now? [y/N]: ").strip().lower()
    if answer not in ("y", "yes"):
        print("Aborting: env file is required.")
        sys.exit(1)
    print(
        "You can leave any value blank if you do not want to set it."
        "Values are written to the env file in KEY=VALUE format."
    )
    github_pat = getpass.getpass(
        "GITHUB_PERSONAL_ACCESS_TOKEN (hidden, optional): "
    ).strip()
    lines: list[str] = []
    if github_pat:
        lines.append(f"GITHUB_PERSONAL_ACCESS_TOKEN={github_pat}")
    print(
        "You may add extra KEY=VALUE entries. Press Enter on an empty line "
        "when finished."
    )
    while True:
        raw = input("Extra env (KEY=VALUE, blank to finish): ").strip()
        if not raw:
            break
        if "=" not in raw:
            print("Invalid format, expected KEY=VALUE. Try again.")
            continue
        lines.append(raw)
    env_text = "".join(lines) + "" if lines else ""
    env_path.write_text(env_text, encoding="utf-8")
    r_ensure_gitignore_entry(env_path)
    print(f"Wrote env file to: {env_path}")
    if not lines:
        print("Warning: env file is currently empty.")


def r_ensure_env_file(env_path: Path) -> None:
    if env_path.exists():
        r_ensure_gitignore_entry(env_path)
        return
    r_prompt_new_env(env_path)


def r_run_command(cmd: list[str]) -> None:
    print(f"+ {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print(f"Error: command not found: {cmd[0]}")
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        print(f"Error: command failed with code {exc.returncode}")
        sys.exit(exc.returncode)


def r_try_install_docker_windows() -> None:
    if shutil.which("docker"):
        return
    print("Docker not found. Attempting Windows install via choco (if available)...")
    if not shutil.which("choco"):
        print(
            "Chocolatey is not installed. Please install Docker Desktop manually "
            "from https://docs.docker.com/desktop/windows/install/ and re-run."
        )
        sys.exit(1)
    ps_cmd = [
        "powershell",
        "-Command",
        "Start-Process",
        "choco",
        "-ArgumentList",
        "'install docker-desktop -y'",
        "-Verb",
        "runAs",
    ]
    print("Requesting elevated install of Docker Desktop via Chocolatey...")
    subprocess.run(ps_cmd, check=False)
    print("Please complete Docker Desktop installation, then re-run this script.")
    sys.exit(1)


def r_try_install_docker_linux() -> None:
    if shutil.which("docker"):
        return
    print("Docker not found. Attempting Linux install via apt (if available)...")
    if not shutil.which("apt"):
        print(
            "apt not found. Please install Docker using your distro's package "
            "manager: https://docs.docker.com/engine/install/"
        )
        sys.exit(1)
    try:
        r_run_command(["sudo", "apt", "update"])
        r_run_command([
            "sudo",
            "apt",
            "install",
            "-y",
            "docker.io",
            "docker-compose-plugin",
        ])
    except SystemExit:
        print(
            "Automatic install failed. Please install Docker manually and re-run."
        )
        sys.exit(1)


def r_try_install_docker_macos() -> None:
    if shutil.which("docker"):
        return
    print("Docker not found. Attempting macOS install via Homebrew (if available)...")
    if not shutil.which("brew"):
        print(
            "Homebrew is not installed. Please install Docker Desktop from "
            "https://docs.docker.com/desktop/mac/install/ and re-run."
        )
        sys.exit(1)
    r_run_command(["brew", "install", "--cask", "docker"])
    print(
        "Docker Desktop installed. Please launch Docker.app once, wait for it "
        "to finish initial setup, then re-run this script."
    )
    sys.exit(1)


def r_ensure_docker_available() -> None:
    if shutil.which("docker"):
        return
    system = platform.system()
    if system == "Windows":
        r_try_install_docker_windows()
    elif system == "Linux":
        r_try_install_docker_linux()
    elif system == "Darwin":
        r_try_install_docker_macos()
    else:
        print(
            f"Unsupported OS for auto-install: {system}. Please install Docker "
            "manually from https://docs.docker.com/get-docker/."
        )
        sys.exit(1)


def r_run_docker_compose(compose_file: Path, env_file: Path, pull: bool) -> None:
    base_cmd = [
        "docker",
        "compose",
        "--file",
        str(compose_file),
        "--env-file",
        str(env_file),
    ]
    if pull:
        r_run_command(base_cmd + ["pull"])
    r_run_command(base_cmd + ["up"])


def r_parse_runner_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify env file, ensure Docker, and run docker compose pull/up -d."
        )
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to env file (default: .env).",
    )
    parser.add_argument(
        "--compose-file",
        default="compose.yml",
        help="Path to docker compose file (default: docker-compose.yml).",
    )
    parser.add_argument(
        "--no-pull",
        action="store_true",
        help="Skip 'docker compose pull' and only run 'up -d'.",
    )
    return parser.parse_args(argv)


def r_main(argv: list[str] | None = None) -> None:
    args = r_parse_runner_args(argv)
    env_path = Path(args.env_file)
    compose_path = Path(args.compose_file)
    if not compose_path.exists():
        print(f"Error: compose file not found: {compose_path}")
        sys.exit(1)
    r_ensure_env_file(env_path)
    r_ensure_docker_available()
    do_pull = not args.no_pull
    r_run_docker_compose(compose_path, env_path, pull=do_pull)

if __name__ == "__main__":
   r_main()
