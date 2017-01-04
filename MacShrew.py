#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# macshrew: Taskbar-enabled GUI alternative for ShrewSoft VPN
# Copyright: (c) 2016, Martin Formanko. All rights reserved.
# License: BSD, see LICENSE for details.
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

import ConfigParser
import argparse
import os
import subprocess
from shutil import copyfile
from threading import Thread, Timer

import pexpect
import sys
import logging

import time

from rumps import rumps

# Default values

IKEC_PATH = '/usr/local/bin/ikec'
IKED_PATH = '/usr/local/sbin/iked'
RETRY_SLEEP_DURATION = 2
PING_HOST = None
PING_ENABLED = False
NOGUI = False
DEBUG_ENABLED = False
SELECTED_PROFILE = None
RUMPS_DEBUG = False


# DO NOT EDIT BELOW THIS LINE

CONFIG_LOADED = '.*config loaded for site.*'
FAIL_TO_LOAD = '.*failed to load'
TUNNEL_ENABLED = 'tunnel enabled'
DETACHED = 'detached from key daemon'

DEFAULT_ICON = 'resources/images/q1.png'
CONNECTING_ICON = 'resources/images/q3.png'
CONNECTED_ICON = 'resources/images/q2.png'
PLAY_ICON = 'resources/images/play.png'
CROSS_ICON = 'resources/images/exit.png'
STOP_ICON = 'resources/images/stop.png'
ABOUT_ICON = 'resources/images/user.png'
SETTINGS_ICON = 'resources/images/sliders.png'
SHOWLOG_ICON = 'resources/images/half.png'

LOGNAME = 'MacShrew.log'

logger = None
gui = None

class APP_STATES:
    STARTED       = 0b0001
    CONNECTED     = 0b0010
    CONNECTING    = 0b0100
    STOPPING      = 0b1000

class ShrewHelperWorker(Thread):

    def __init__(self, profile_name):
        global logger
        Thread.__init__(self)
        self._monitor_timer = None
        self._child = None
        self.set_state(0)
        self.profile_name = profile_name
        self.logger = logger

    def __execute_binary(self):
        """
        Spawns the ikec binary with specified profile name
        :return:
        """
        self.set_state(APP_STATES.CONNECTING)
        self.logger.info("Starting ikec binary with %s -r \"%s\"" % (IKEC_PATH, self.profile_name))
        self._child = pexpect.spawn('%s -r \"%s\"' % (IKEC_PATH, self.profile_name))
        self._child.logfile_read = StreamProxy()
        self.__step_initialisation()

    def __step_initialisation(self):
        """
        We expect that the profile name specified for iked was successfully loaded
        :return:
        """

        i = self._child.expect([pexpect.TIMEOUT, CONFIG_LOADED, FAIL_TO_LOAD])

        if i == 0:
            fatal("Timeout while executing ikec")
            self.disconnect()

        if i == 1:
            self.logger.info("Config loaded")
            self.__step_send_connect()

        if i == 2:
            fatal("Fail to load site configuration for %s" % self.profile_name)
            self.disconnect()

    def state(self):
        return self._state

    def set_state(self, value):
        """
        If the state of the worker changes, we notify the GUI as well (if enabled)
        :param value: APP_STATES bitmask value
        :return:
        """
        global gui
        if not NOGUI:
            if value & APP_STATES.CONNECTING:
                gui.icon = CONNECTING_ICON
            else:
                if value & APP_STATES.CONNECTED:
                    gui.icon = CONNECTED_ICON
                if not value & APP_STATES.STARTED:
                    gui.icon = DEFAULT_ICON
            gui.set_state(value)
        self._state = value

    def __step_send_connect(self):
        """
        Config loaded, let's create the tunnel
        :return:
        """

        self.logger.info("Sending C command to connect")
        self._child.sendline('c')
        i = self._child.expect([pexpect.TIMEOUT, TUNNEL_ENABLED, DETACHED])

        if i == 0:
            self.logger.error("Cannot establish tunnel. Retrying")

        if i == 1:
            self.logger.info("Tunnel established")
            self.__monitor_loop()

        if i == 2:
            self.logger.info("Detached from key daemon")
            self.__retry_with_sleep(RETRY_SLEEP_DURATION)

    def __monitor_loop(self):
        """
        Continuously looping every 30 seconds if some new data has come
        :return:
        """
        self.logger.info('Monitoring changes of the tunnel')
        self.set_state(APP_STATES.STARTED | APP_STATES.CONNECTED)
        try:
            while True:
                if self._monitor_timer == None and PING_ENABLED:
                    self.__create_monitor_thread()
                i = self._child.expect([pexpect.TIMEOUT, DETACHED], timeout=10)
                if i == 0:
                    continue
                if i == 1:
                    self.set_state(APP_STATES.STARTED | APP_STATES.CONNECTING)
                    self.logger.info("Tunnel has been closed. Retrying to establish the connection")
                    self.__retry_with_sleep(RETRY_SLEEP_DURATION)
        except Exception as e:
            if not self._state & APP_STATES.STOPPING:
                self.logger.error("Quiting monitoring loop due to exception %s" % e)
                self.disconnect()

    def __retry_with_sleep(self, sleep_duration):
        self.logger.debug("Waiting %d seconds" % (sleep_duration))
        time.sleep(sleep_duration)
        self.__step_send_connect()

    def __create_monitor_thread(self):
        """
        If pinging enabled, this just pings every 20 seconds the host specified in PING_HOST. Works only in nogui mode
        :return:
        """
        try:
            self.__ping_host()
        except Exception:
            self.logger.error("Exception while pinging host")
        if self._state & APP_STATES.CONNECTED:
            self._monitor_timer = Timer(20, self.__create_monitor_thread)
            self._monitor_timer.start()

    def __ping_host(self):

        self.logger.debug("Pinging host %s" % (PING_HOST))
        proc = subprocess.Popen("ping -c 1 %s" % PING_HOST, stdout=subprocess.PIPE, shell=True)
        (out, err) = proc.communicate()
        if proc.returncode == 0:
            self.logger.debug("Successfully pinged host")
        else:
            self.logger.error("Host %s unreachable" % (PING_HOST))

    def run(self):
        self.set_state(APP_STATES.STARTED)
        self.__execute_binary()

    def disconnect(self):
        """
        Let's cancel the worker, pexpect and set state to STOPPED
        :return:
        """
        self.set_state(APP_STATES.STOPPING)
        if self._child != None:
            self._child.close(force=True)
        if self._monitor_timer != None:
            self._monitor_timer.cancel()
        self.set_state(0)

class ShrewHelperApp(rumps.App):

    def __init__(self, *args, **kwargs):
        super(ShrewHelperApp, self).__init__(*args, **kwargs)
        self._selected_profile = SELECTED_PROFILE
        self.__create_menu_callbacks()
        self.shrew_helper = None

    def _create_profile_entry(self, profile):
        """
        Prepares menu item for the Selected profile SubMenu
        :param profile:String value of the profile
        :return: rumps.MenuItem
        """
        item = rumps.MenuItem(profile)
        item.set_callback(self.profile_callback, profile)
        if profile == self._selected_profile: item.state = True
        return item

    def profile_callback(self, sender):
        """
        Callback for every profile entry in submenu
        :param sender: profile rumps.MenuItem
        :return:
        """
        global SELECTED_PROFILE
        self._selected_profile = sender.key
        for profile, menu_item in self.profiles_entries.items():
            menu_item.state = profile == sender.key
        SELECTED_PROFILE = sender.key
        self.connect_menu_item.title = 'Connect %s' % (sender.key)
        self.connect_menu_item.set_callback(self.connect)
        write_config()

    def disable_profiles(self):
        # self.menu["Select profile"]["Import profile"].set_callback(None)
        for profile, menu_item in self.profiles_entries.items():
            menu_item.set_callback(None)

    def enable_profiles(self):
        # self.menu["Select profile"]["Import profile"].set_callback(self.import_profile)
        for profile, menu_item in self.profiles_entries.items():
            menu_item.set_callback(self.profile_callback, profile)

    def __create_menu_callbacks(self):
        """
        Creates menu in taskbar and sets callbacks
        :return:
        """

        profiles_dict = {profile: self._create_profile_entry(profile) for profile in self.get_available_profiles()}
        self.profiles_entries = profiles_dict
        profiles = profiles_dict.values()

        self.connect_menu_item = rumps.MenuItem("Connect %s" % (self._selected_profile), icon=PLAY_ICON, dimensions=(16, 16))
        self.disconnect_menu_item = rumps.MenuItem("Disconnect", icon=STOP_ICON, dimensions=(16, 16))

        self.menu = [
            self.connect_menu_item,
            self.disconnect_menu_item,
            None,
            [rumps.MenuItem("Select profile", icon=SETTINGS_ICON, dimensions=(16, 16)), profiles],
            None,
            rumps.MenuItem("About", icon=ABOUT_ICON, dimensions=(16, 16)),
            [rumps.MenuItem("Logging", icon=SHOWLOG_ICON, dimensions=(16, 16)), [rumps.MenuItem("Show log"), rumps.MenuItem("Verbose logging")]],
            rumps.MenuItem("Quit", icon=CROSS_ICON, dimensions=(16, 16))
        ]
        # self.menu["Select profile"]["Import profile"].set_callback(self.import_profile)

        if SELECTED_PROFILE is not None and len(SELECTED_PROFILE) > 0:
            self.connect_menu_item.set_callback(self.connect)

        self.menu["Logging"]["Verbose logging"].state = DEBUG_ENABLED

    def connect(self, sender):
        if self.shrew_helper is not None:
            self.shrew_helper.disconnect()
            self.shrew_helper.join()
        self.shrew_helper = ShrewHelperWorker(self._selected_profile)
        self.shrew_helper.start()

    def disconnect(self, sender):
        self.shrew_helper.disconnect()

    @rumps.clicked("About")
    def about(self, _):
        rumps.alert("MacShrew 2016\nDevelMagic s.r.o.\nMartin Formanko\n\nhttp://github.com/mejmo/mac-shrew")

    @rumps.clicked("Quit")
    def exit(self, _):
        rumps.quit_application()

    @rumps.clicked("Logging", "Show log")
    def openlog(self, _):
        if os.path.exists(LOGNAME):
            subprocess.call(['open', '-a', 'TextEdit', LOGNAME])
        else:
            fatal('Cannot find the log file')

    @rumps.clicked("Logging", "Verbose logging")
    def set_debug(self, sender):
        global DEBUG_ENABLED
        sender.state = not sender.state
        if sender.state:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
        DEBUG_ENABLED = sender.state
        write_config()

    def get_available_profiles(self):
        """
        Searches through ~/.ike folder and it tries to find any available profiles in sites subfolder
        :return: sorted list with string names
        """
        from os.path import expanduser, isfile, join
        home = expanduser("~")
        if not os.path.isdir(home+"/.ike") or not os.path.isdir(home+"/.ike/sites"):
            return []
        profiles = [f for f in os.listdir(home + "/.ike/sites") if isfile(join(home + "/.ike/sites", f))]
        profiles.sort()
        return profiles

    def set_state(self, value):

        if value & APP_STATES.STARTED:
            self.menu['Disconnect'].set_callback(self.disconnect)
            self.connect_menu_item.set_callback(None)
            self.disable_profiles()
        else:
            self.disconnect_menu_item.set_callback(None)
            self.connect_menu_item.set_callback(self.connect)
            self.enable_profiles()

class IkedRunner:

    @staticmethod
    def is_running():
        """
        Checkes if iked is not already running
        :return:
        """
        import commands
        return False if len(commands.getoutput("pgrep iked")) == 0 else True

    @staticmethod
    def run_iked():
        """
        Creates popup box with login prompt for the administrator username/password. We need iked to run under root
        :return:
        """
        os.system("osascript -e 'do shell script \"%s\" with administrator privileges'" % (IKED_PATH))

class StreamProxy:

    def write(self, msg):
        """
        Proxy for pexpect so that we can forward logging into our logger class
        :param msg:
        :return:
        """
        logger.debug("Ikec output: \n%s" % msg)

    def flush(self):
        pass

def signal_handler(signal, frame):
    """
    Kills the pinging thread and UI thread as well, when CTRL+C received
    :param signal:
    :param frame:
    :return:
    """
    global shrew_helper
    if shrew_helper is not None:
        shrew_helper.disconnect()
    if gui is not None:
        gui.quit_application()


def create_logger():
    """
    Logs into stdout and MacShrew.log file simultaneously
    :return: logger object
    """
    logger = logging.getLogger('shrew_helper')
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

    fh = logging.FileHandler(LOGNAME)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)

    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    ch.setLevel(logging.DEBUG)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger

def fatal(msg):

    logger.fatal(msg)
    if not NOGUI:
        rumps.alert(msg)

def parse_arguments():
    """
    Values from config, can be overriden by application arguments
    :return:
    """
    global IKEC_PATH, IKED_PATH, NOGUI, SELECTED_PROFILE

    parser = argparse.ArgumentParser(description='Client for ShrewSoft VPN with reconnect feature and GUI')
    parser.add_argument("-n", "--nogui", action='store_true', default=NOGUI, dest='nogui', help='disable GUI and run in console')
    parser.add_argument("-r", "--profile", dest='profile', default=SELECTED_PROFILE, help='(only with --nogui) profile name to be used. It must be located under ~/.ike/sites/<NAME>')
    parser.add_argument("-ic", "--ikec", default=IKEC_PATH, dest='ikecpath', help='path to ikec binary')
    parser.add_argument("-id", "--iked", default=IKED_PATH, dest='ikedpath', help='path to iked binary')
    parser.add_argument("-p", "--pinghost", dest='pinghost', help='ping this host every 20secs when tunnel is established')

    args = parser.parse_args()

    if args.nogui and args.profile == '':
        parser.error('You must specify profile name when --nogui is active')
        sys.exit(22)

    IKEC_PATH = args.ikecpath
    IKED_PATH = args.ikedpath
    PING_HOST = args.pinghost
    NOGUI = args.nogui
    SELECTED_PROFILE = args.profile

    if PING_HOST == None:
        PING_ENABLED = False

def read_config():
    """
    If the file ~/.macshrew/MacShrew.conf does not exist, just copy the default values and load the config
    :return:
    """
    global IKEC_PATH, IKED_PATH, SELECTED_PROFILE, DEBUG_ENABLED

    config = ConfigParser.ConfigParser()
    if not os.path.isdir(os.path.expanduser("~/.macshrew")):
        os.makedirs(os.path.expanduser("~/.macshrew"))
    if not os.path.isfile(os.path.expanduser("~/.macshrew")+"/MacShrew.conf"):
        copyfile("resources/conf/MacShrew.conf", os.path.expanduser("~/.macshrew/MacShrew.conf"))
    config.readfp(open(os.path.expanduser("~/.macshrew/MacShrew.conf")))

    SELECTED_PROFILE = config.get("UI", "Profile")
    DEBUG_ENABLED = config.getboolean("UI", "VerboseLogging")

    if len(config.get("IKE", "ikedpath", IKED_PATH)) > 0:
        IKED_PATH = config.get("IKE", "ikedpath", IKED_PATH)

    if len(config.get("IKE", "ikecpath", IKEC_PATH)) > 0:
        IKEC_PATH = config.get("IKE", "ikecpath", IKEC_PATH)

def write_config():

    config = ConfigParser.RawConfigParser()
    config.add_section("UI")
    config.set("UI", "Profile", SELECTED_PROFILE)
    config.set("UI", "VerboseLogging", DEBUG_ENABLED)
    config.add_section("IKE")
    config.set("IKE", "ikedpath", IKED_PATH)
    config.set("IKE", "ikecpath", IKEC_PATH)

    with open(os.path.expanduser('~/.macshrew/MacShrew.conf'), 'wb') as configfile:
        config.write(configfile)

if __name__ == "__main__":

    logger = create_logger()

    read_config()
    parse_arguments()

    logger.setLevel(logging.DEBUG if DEBUG_ENABLED == True else logging.INFO)

    if not os.path.exists(IKEC_PATH):
        fatal('Cannot find ikec binary on path %s. Install ShrewSoft VPN or set the correct ikec path' % IKEC_PATH)
        sys.exit(2)

    if not os.path.exists(IKED_PATH):
        fatal('Cannot find iked binary on path %s. Install ShrewSoft VPN or set the correct iked path' % IKED_PATH)
        sys.exit(2)

    try:
        if not IkedRunner.is_running():
            logger.info("Iked is not running. Starting daemon")
            IkedRunner.run_iked()
    except Exception as e:
        fatal("Cannot start iked daemon: %s" % (e))
        sys.exit(3)

    if not IkedRunner.is_running():
        fatal("Cannot start iked")
        sys.exit(3)

    rumps.debug_mode(RUMPS_DEBUG)

    if NOGUI:
        app = ShrewHelperWorker()
        app.run()
    else:
        gui = ShrewHelperApp("ShrewMac", icon=DEFAULT_ICON, quit_button=None)
        gui.run()







