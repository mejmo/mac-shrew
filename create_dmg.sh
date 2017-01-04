#!/bin/sh
python setup.py py2app
dmgbuild -s dmgbuild.py -D app=dist/macshrew.app "MacShrew" dmg/MacShrew.dmg