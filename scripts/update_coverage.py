import re
import subprocess
import sys
from pathlib import Path


def main():
    print("Running tests with coverage...")
    try:
        result = subprocess.run(
            [
                "uv",
                "run",
                "pytest",
                "tests/",
                "--cov=skim",
                "--cov-report=term-missing",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(e.stdout)
        print(e.stderr)
        return 1

    match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", result.stdout)
    if not match:
        print("Could not parse coverage percentage from pytest output.")
        return 1

    coverage = int(match.group(1))
    print(f"Detected coverage: {coverage}%")

    if coverage >= 95:
        color = "brightgreen"
    elif coverage >= 90:
        color = "green"
    elif coverage >= 80:
        color = "yellowgreen"
    elif coverage >= 70:
        color = "yellow"
    else:
        color = "red"

    readme_path = Path(__file__).parents[1] / "README.md"
    content = readme_path.read_text()

    new_badge_url = f"https://img.shields.io/badge/coverage-{coverage}%25-{color}.svg"
    url_pattern = r"https://img\.shields\.io/badge/coverage-\d+%25-[a-z]+\.svg"

    if re.search(url_pattern, content):
        new_content = re.sub(url_pattern, new_badge_url, content)
        if new_content != content:
            readme_path.write_text(new_content)
            print(f"Updated README.md with coverage {coverage}%")

            subprocess.run(["git", "add", "README.md"], check=True)
        else:
            print("Coverage unchanged, skipping README update.")
    else:
        print("Coverage badge not found in README.md")

    return 0


if __name__ == "__main__":
    sys.exit(main())
