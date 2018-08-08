import os

from setuptools import setup, find_packages
import sys
import subprocess
import pkg_resources

MAIN_MODULE = 'agent'

# Find the agent package that contains the main module
packages = find_packages('.')
agent_package = 'ksi_agent'

try:
    requirements = [x.strip() for x in open('./setup-requires.txt', 'r').readlines()]
except IOError:  # file not found?
    requirements = []

to_install = []

for requirement in requirements:
    if not requirement or requirement.strip().startswith('#'):
        continue
    try:
        pkg_resources.require(requirement)
    except pkg_resources.DistributionNotFound:
        to_install.append(requirement)

print sys.path[0:0]
if to_install:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + to_install)

# Find the version number from the main module
agent_module = agent_package + '.' + MAIN_MODULE
_temp = __import__(agent_module, globals(), locals(), ['__version__'], -1)
__version__ = _temp.__version__


# Setup
setup(
    name=agent_package + 'agent',
    version=__version__,
    author="Guardtime USA",
    install_requires=['volttron'] + to_install,
    packages=packages,
    entry_points={
        'setuptools.installation': [
            'eggsecutable = ' + agent_module + ':main',
        ]
    }
)