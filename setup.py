from setuptools import setup

APP = ['MacShrew.py']
DATA_FILES = [('', ['resources'])]
OPTIONS = {
    'argv_emulation': True,
    'plist': {
        'LSUIElement': True,
        'CFBundleIconFile': 'app.icns'
    },
    'packages': ['rumps']
}

OPTIONS2 = {
    'iconfile': 'app.icns',
    'plist': {
        'LSUIElement': True,
        'CFBundleIconFile': 'app.icns'
    }
}

setup(
    app=APP,
    data_files=DATA_FILES,
    version="1.0.1",
    options={'pyc2app': OPTIONS, 'py2app': OPTIONS2},
    setup_requires=['py2app'],
)
