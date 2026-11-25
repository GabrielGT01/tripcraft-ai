
import os
import shutil
import zipfile
import subprocess
from pathlib import Path


# --------------------------------------------------
# Configuration
# --------------------------------------------------

# IMPORTANT:
# This must match the Python runtime selected in AWS Lambda.
PYTHON_VERSION = "3.14"

# Your Mac M1 is ARM, but your Lambda is x86_64.
# Docker will build the package for Lambda, not for your Mac.
DOCKER_PLATFORM = "linux/amd64"


# --------------------------------------------------
# Project paths
# --------------------------------------------------

# deploy.py is inside backend/
BACKEND_DIR = Path(__file__).resolve().parent

# Project root is one level above backend/
PROJECT_ROOT = BACKEND_DIR.parent

# requirements.txt is at project root
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"

# Temporary build folder
PACKAGE_DIR = PROJECT_ROOT / "lambda-package"

# Final ZIP file
ZIP_FILE = PROJECT_ROOT / "lambda-deployment.zip"


def main():
    print("Creating TripCraft Lambda deployment package...")

    # --------------------------------------------------
    # 1. Make sure requirements.txt exists
    # --------------------------------------------------

    if not REQUIREMENTS_FILE.exists():
        raise FileNotFoundError(
            f"requirements.txt not found at: "
            f"{REQUIREMENTS_FILE}"
        )


    # --------------------------------------------------
    # 2. Clean previous build
    # --------------------------------------------------

    if PACKAGE_DIR.exists():
        shutil.rmtree(PACKAGE_DIR)

    if ZIP_FILE.exists():
        ZIP_FILE.unlink()

    PACKAGE_DIR.mkdir()


    # --------------------------------------------------
    # 3. Install dependencies for AWS Lambda
    # --------------------------------------------------

    print("Installing Lambda-compatible dependencies...")

    subprocess.run(
        [
            "docker",
            "run",
            "--rm",

            # Mount the whole project into Docker
            "-v",
            f"{PROJECT_ROOT}:/var/task",

            # Mac M1 is ARM, but our Lambda is x86_64
            "--platform",
            DOCKER_PLATFORM,

            # We only want to use the Lambda image
            # as our Python/Linux build environment
            "--entrypoint",
            "",

            # Must match the Python runtime in AWS Lambda
            f"public.ecr.aws/lambda/python:{PYTHON_VERSION}",

            "/bin/sh",
            "-c",

            # Because pip is already running INSIDE the
            # official Lambda Linux image, we do not need
            # to manually force manylinux packages.
            (
                "pip install "
                "--target /var/task/lambda-package "
                "-r /var/task/requirements.txt "
                "--upgrade "
                "--no-cache-dir"
            ),
        ],
        check=True,
    )


    # --------------------------------------------------
    # 4. Copy TripCraft backend
    # --------------------------------------------------

    print("Copying TripCraft backend...")

    # Copy the whole backend package.
    #
    # This includes:
    # app.py
    # lambda_handler.py
    # config.py
    # memory.py
    # pipeline.py
    # prompts.py
    # schemas.py
    # tools.py
    #
    # deploy.py is ignored because Lambda does not
    # need the script that builds the ZIP.
    shutil.copytree(
        BACKEND_DIR,
        PACKAGE_DIR / "backend",
        ignore=shutil.ignore_patterns(
            "__pycache__",
            "*.pyc",
            ".DS_Store",
            "deploy.py",
        ),
    )


    # --------------------------------------------------
    # 5. Create Lambda ZIP
    # --------------------------------------------------

    print("Creating Lambda ZIP...")

    with zipfile.ZipFile(
        ZIP_FILE,
        "w",
        zipfile.ZIP_DEFLATED,
    ) as zipf:

        for root, dirs, files in os.walk(
            PACKAGE_DIR
        ):
            for file in files:

                file_path = (
                    Path(root) / file
                )

                # Remove lambda-package/ from the path
                # stored inside the ZIP.
                arcname = file_path.relative_to(
                    PACKAGE_DIR
                )

                zipf.write(
                    file_path,
                    arcname,
                )


    # --------------------------------------------------
    # 6. Show final package size
    # --------------------------------------------------

    size_mb = (
        ZIP_FILE.stat().st_size
        / (1024 * 1024)
    )

    print()
    print(
        f"✓ Created lambda-deployment.zip "
        f"({size_mb:.2f} MB)"
    )

    print(
        f"✓ Built for Python {PYTHON_VERSION}"
    )

    print(
        "✓ Built for Lambda x86_64"
    )

    print()
    print(
        "Lambda handler:"
    )

    print(
        "backend.lambda_handler.handler"
    )


if __name__ == "__main__":
    main()
