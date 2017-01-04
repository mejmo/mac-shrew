from setuptools import setup

APP = ['MacShrew.py']
DATA_FILES = [('', ['resources'])]
OPTIONS = {
    'argv_emulation': True,
    'plist': {
        'LSUIElement': True,
    },
    'packages': ['rumps'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'pyc2app': OPTIONS},
    setup_requires=['py2app'],
)