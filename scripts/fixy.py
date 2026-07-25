import subprocess


def main() -> None:
    subprocess.run(["uv", "run", "ty", "check"], check=True)
    subprocess.run(["uv", "run", "ty", "check", "--error", "all"], check=True)
    subprocess.run(["uv", "run", "ruff", "format"], check=True)
    subprocess.run(["uv", "run", "ruff", "check", "--fix"], check=True)
    subprocess.run(["uv", "run", "pytest"], check=True)


if __name__ == "__main__":
    raise SystemExit(main())
