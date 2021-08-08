from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="WannaCRI",
    description="Criware media formats library",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="donmai",
    url="https://github.com/donmai-me/WannaCRI",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Games/Entertainment",
    ],
    packages=[
        "wannacri",
        "wannacri.usm",
        "wannacri.usm.media",
    ],
    entry_points={
        "console_scripts": ["wannacri=wannacri:main"],
    },
    python_requires="~=3.8",
    use_scm_version=True,
    setup_requires=["setuptools_scm"],
    install_requires=["ffmpeg-python~=0.2.0"],
)
