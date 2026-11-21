"""Download the course simulator at the experiment's pinned revision."""
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "teacher-source"
COMMIT = "9a324d9ce9671a11184c4e8f1f9555fb0d8ea2c1"
BASE = ("https://raw.githubusercontent.com/gotrafficgo/teaching_artificial_intelligence/"
        + COMMIT + "/car-following-simulation/")
FILES = ("config.py", "vehicle.py", "vehicle_idm.py", "simulator.py",
         "plotting.py", "main.py", "vehicle_knn.py", "vehicle_llm.py",
         "test_simulation.py", "requirements.txt", "README.md")


def main():
    TARGET.mkdir(exist_ok=True)
    for name in FILES:
        with urlopen(BASE + name, timeout=30) as response:
            data = response.read()
        target = TARGET / name
        if target.exists():
            if target.read_bytes().replace(b"\r\n", b"\n") != data.replace(b"\r\n", b"\n"):
                raise SystemExit(f"{target} differs from pinned source; preserving existing file.")
        else:
            target.write_bytes(data)
        print(f"Verified {name}")


if __name__ == "__main__":
    main()
