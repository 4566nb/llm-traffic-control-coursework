"""Obtain the teacher's unmodified code at the experiment's pinned commit."""
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "teacher-source"
REPOSITORY = "https://github.com/gotrafficgo/teaching_artificial_intelligence.git"
COMMIT = "9a324d9ce9671a11184c4e8f1f9555fb0d8ea2c1"


def main():
    if TARGET.exists():
        raise SystemExit("teacher-source already exists; preserve it and remove or rename it yourself if needed.")
    work = ROOT / ".teacher-download"
    if work.exists():
        raise SystemExit(".teacher-download already exists; inspect it before running again.")
    subprocess.run(["git", "clone", "--no-checkout", REPOSITORY, str(work)], check=True)
    subprocess.run(["git", "-C", str(work), "checkout", COMMIT, "--", "car-following-simulation"], check=True)
    shutil.copytree(work / "car-following-simulation", TARGET)
    shutil.rmtree(work)
    print("Pinned teacher simulator installed into teacher-source")


if __name__ == "__main__":
    main()
