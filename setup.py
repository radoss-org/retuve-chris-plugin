from setuptools import setup

setup(
    name="retuve_chris_plugin",
    version="1.0.0",
    description="Retuve ChRIS plugin",
    author="Adam",
    author_email="adam@radoss.org",
    url="https://github.com/radoss-org/chris-plugin-example",
    packages=["retuve_chris_plugin"],
    install_requires=[
        "chris_plugin",
        "retuve-yolo-plugin @ git+https://github.com/radoss-org/retuve-yolo-plugin.git",
    ],
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
