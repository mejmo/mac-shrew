# MacShrew Taskbar

**MacShrew** is a taskbar alternative to _Shrew Soft VPN Access manager_ for macOS systems
which brings following additional features:
- MacShrew Taskbar **automatically reconnects** when IPSec the connection goes down (suspend, wifi disabled,
 etc.)
- tunnel **status** in taskbar

    ![MacShrew in taskbar](http://178.79.191.30/github_linking/MacShrew1.jpg "MacShrew Taskbar")

## Getting Started

This will guide you through installation of MacShrew taskbar.

### Prerequisites

- ShrewSoft VPN Client installed (if not, then we will install it with Homebrew)
- XCode Command line developer tools (ruby)
- macOS Sierra >10.12.2 (may be working with other systems too, but not tested)

### Installing

**1. If you **do not have homebrew installed** run this:**

    ruby -e “$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)” /dev/null

**2. Install ShrewSoft VPN Client:**

    brew tap homebrew/boneyard

When everything went smoothly:

    brew install shrewsoft-vpn-client

**3. Install MacShrew Taskbar application from:**

    https://github.com/mejmo/mac-shrew/raw/master/dmg/MacShrew.dmg

**4. Run the application**

## Building

This tools are used for building:

* [py2app](https://pythonhosted.org/py2app/) - Py2App packaging into standalone app
* [dmgbuild](https://bitbucket.org/al45tair/dmgbuild/) - Packaging into dmg file
* [PyCharm](https://www.jetbrains.com/pycharm/) - The best IDE for python

On Sierra and El Capitan system you must _**disable**_ System Integrity Protection if you would like to run py2app,
otherwise py2app will not create any package.

### Disable SIP System Integrity Protection

Follow these instructions:

1. Click the  menu.
2. Select **Restart**...
3. Hold down **command-R** to boot into the **Recovery System**.
4. Click the **Utilities menu** and select **Terminal**.
5. Type ```csrutil disable``` and press return.
6. Close the **Terminal app**.
7. Click the  menu and select **Restart**....


Then simply start `create_dmg.py` script which firstly makes py2app and then prepares dmg file
in `dmg/MacShrew.dmg`

## Authors

* **Martin Formanko** - [mejmo](https://github.com/mejmo)

## License

This project is licensed under the BSD License - see the [LICENSE.md](LICENSE.md) file for details.
Icons are downloaded from iconfinder.com which are free for commercial and personal use.


