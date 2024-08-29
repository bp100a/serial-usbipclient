"""get the version number"""
import importlib.metadata
import logging
import os
from pathlib import Path

LOGGER: logging.Logger = logging.getLogger(__name__)


def get_version(package_name: str) -> str:
    """return the package's version"""
    # if the toml file exists, then we are running locally (IDE probably) and can read
    # from the toml file, otherwise we are an installed package and need to fetch from
    # the package's metadata
    try:
        from tomlkit import parse  # pylint: disable=import-outside-toplevel
        toml_filepath: Path = Path(os.path.join(os.path.dirname(__file__), "..", "pyproject.toml"))
        if toml_filepath.is_file():
            with open(toml_filepath, "r", encoding='utf-8') as toml_file:
                toml_data: str = toml_file.read()
                toml_contents: dict = parse(toml_data)
                name: str = toml_contents['tool']['poetry']['name']
                if name != package_name:
                    LOGGER.warning(f"{os.path.basename(toml_filepath)} has project name of {name} does not match {package_name}!")
                return toml_contents['tool']['poetry']['version']
    except ImportError:
        # We are an installed package, so get version from metadata
        try:
            return importlib.metadata.version(package_name)
        except importlib.metadata.PackageNotFoundError:
            LOGGER.error(f"package name {package_name} not found!")
            return f'?.?.?.{package_name}'
