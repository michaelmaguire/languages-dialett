from setuptools import setup

# Registers the dataset with cldfbench, so that e.g. `cldfbench makecldf rogn` works by name once it is
# installed (`pip install -e .`). The everyday build is pipeline/build_all.sh.
setup(
    name="cldfbench_rogn",
    py_modules=["cldfbench_rogn"],
    include_package_data=True,
    zip_safe=False,
    entry_points={"cldfbench.dataset": ["rogn=cldfbench_rogn:Dataset"]},
    install_requires=["cldfbench", "pycldf", "openpyxl", "pypdf"],
    extras_require={"test": ["pytest-cldf"]},
)
