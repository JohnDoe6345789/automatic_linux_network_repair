# Automatic Linux Network Repair

![PyPI version](https://img.shields.io/pypi/v/automatic_linux_network_repair.svg)
[![Documentation Status](https://readthedocs.org/projects/automatic_linux_network_repair/badge/?version=latest)](https://automatic_linux_network_repair.readthedocs.io/en/latest/?version=latest)

Automatic Linux Network Repair

* PyPI package: https://pypi.org/project/automatic_linux_network_repair/
* Free software: MIT License
* Documentation: https://automatic_linux_network_repair.readthedocs.io.

## Features

* TODO

## Preparing an offline wheelhouse

Use `scripts/prepare_wheelhouse.py` to download project dependencies and copy the wheel files to a mounted USB flash drive. This is helpful when the target machine will not have internet access.

Example usage:

```
python scripts/prepare_wheelhouse.py --usb-mount /media/usb
```

The script downloads the dependencies listed in `requirements.txt`, builds a wheel for the project itself, and copies the resulting `wheelhouse/` directory onto the USB drive so it can be installed offline.

## Credits

This package was created with [Cookiecutter](https://github.com/audreyfeldroy/cookiecutter) and the [audreyfeldroy/cookiecutter-pypackage](https://github.com/audreyfeldroy/cookiecutter-pypackage) project template.
