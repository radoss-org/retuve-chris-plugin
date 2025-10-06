from setuptools import setup


# Read requirements from requirements.lock
def read_requirements():
    with open("requirements.txt", "r") as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.startswith("#")
        ]


setup(
    name="retuve_chris_plugin",
    version="1.0.0",
    description="Retuve ChRIS plugin",
    author="Adam",
    author_email="adam@radoss.org",
    url="https://github.com/radoss-org/retuve-chris-plugin",
    packages=["retuve_chris_plugin"],
    install_requires=read_requirements(),
    license="Apache-2.0 license",
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            # here you need to declare the name of your executable program
            # and your main function
            "retuve_chris_plugin = retuve_chris_plugin:main"
        ]
    },
)
