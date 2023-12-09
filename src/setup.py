from setuptools import find_packages, setup

# Read requirements from requirements.txt
with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="aimarafone",
    version="0.1.0",
    description="The marafone bot package",
    url="https://github.com/federico-fabiani/alpha-maraffa",
    author="Federico Fabiani",
    author_email="federico.fabiani96@gmail.com",
    license="BSD 3-Clause",
    packages=find_packages(),
    package_data={"aimarafone": ["resources/*"]},
    install_requires=requirements,
)
