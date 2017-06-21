#!python3
# LEDController.py 
# Written by Chase Sawyer
# Feb-June 2017
# Version 0.1 - Commands are finalized, GUI programming underway.
# 
# INSTRUCTIONS FOR USE: (in general....)
# Set up and flash an Arduino or similar that uses serial / Messenger for control, and hook that up to your machine
# and get to COM port/address that the serial port binds to.
# Set up settings in /LEDControllerSettings.ini
# Fire up this script to start the UI and controlling your LEDs!

import PyCmdMessenger # for communication with Arduino
import random #for testing protocol / led colors
from random import randint
import serial # I/O communication with Arduino controller
import signal # Capture keyboard interrupt
import logging # Program logging
import configparser # Reading / writing configurations
import time # for delays, etc.

# GUI things
import tkinter as tk
from tkinter import ttk
from tkinter.colorchooser import *


# LEDController needs to be global so that stop() can access it
# at any time when the keyboard interrupt is triggered.
LEDController = object

class LEDController(object):
    def __init__(self, timeout, port, baudrate, LEDs, brightness):
        self.timeout = timeout
        self.port = port
        self.baudrate = baudrate
        self.numLEDs = LEDs
        self.brightness = brightness
        self.c = None
        self.cmdMessenger = None
        self.commands = [["CMDERROR", "s"],
                         ["SETCOLORALL", "LL"],
                         ["SETCOLORSINGLE", "bLL"],
                         ["SETCOLORRANGE", "bbLL"],
                         ["SETPATTERNRAINBOW", "L"],
                         ["SETPATTERNTHEATER", "LLL"],
                         ["SETPATTERNWIPE", "LL"],
                         ["SETPATTERNSCANNER", "LL"],
                         ["SETPATTERNFADE", "LLIL"],
                         ["SETBRIGHTNESSALL", "b"],
                         ["SETLEDSOFF", "L"],
                         ["ARDUINOBUSY", "?"],
                         ["NOCOMMAND", "?"],
                         ["CMDCONF", "L"]]
        self.last_command_lambda = 'Breathe'
        # last cycle is used as a switch to alternate animations that use
        # other commands as primitives (see Breathe effect)
        self.last_cycle = 0
        self.cmd_lambdas = {
            'SCA': lambda: self.setColorAll(
                self.cmd_parameters['color1'],
                self.cmd_parameters['interval']
            ),
            'SCS': lambda: self.setColorSingle(
                self.cmd_parameters['color1'],
                self.cmd_parameters['st_led-index'],
                self.cmd_parameters['interval']
            ),
            'SCR': lambda: self.setColorRange(
                self.cmd_parameters['color1'],
                self.cmd_parameters['st_led'],
                self.cmd_parameters['num-steps'],
                self.cmd_parameters['interval']
            ),
            'SPR': lambda: self.setPatternRainbow(
                self.cmd_parameters['interval']
            ),
            'SPT': lambda: self.setPatternTheater(
                self.cmd_parameters['color1'],
                self.cmd_parameters['color2'],
                self.cmd_parameters['interval']
            ),
            'SPW': lambda: self.setPatternWipe(
                self.cmd_parameters['color1'],
                self.cmd_parameters['interval']
            ),
            'SPS': lambda: self.setPatternScanner(
                self.cmd_parameters['color1'],
                self.cmd_parameters['interval']
            ),
            'SPF': lambda: self.setPatternFade(
                self.cmd_parameters['color1'],
                self.cmd_parameters['color2'],
                self.cmd_parameters['num-steps'],
                self.cmd_parameters['interval']
            ),
            'SBA': lambda: self.setBrightness(self.cmd_parameters['brightness']),
            'SLO': lambda: self.setLedsOff(self.cmd_parameters['interval']),
            'Breathe': lambda: self.breathe_effect()
        }
        self.cmd_parameters = {
            'color1': 0xFFFFFF,
            'color2': 0x000000,
            'st_led-index': 20,
            'num-steps': 100,
            'brightness': 0,
            'interval': 2000,
        }

    # Set up the PyCmdMessenger library (which also handles setup of the
    # serial port given and allows structured communication over serial.)
    def setupCmdMessenger(self):
        self.cmdMessenger = PyCmdMessenger.ArduinoBoard(self.port, baud_rate=self.baudrate)
        self.c = PyCmdMessenger.CmdMessenger(self.cmdMessenger, self.commands)

    # A faster way of checking the serial line for incoming data - use to prevent
    # calling blocking operations until necessary.
    def serial_has_waiting(self):
        """Return true if there is serial data in the input buffer - non-Blocking"""
        return self.cmdMessenger.comm.in_waiting != 0

    # Handler for returned commands from the device connected at the other
    # end of the serial line. Returns the Command that was received.
    # Blocks while waiting for a response over serial by checking for there
    # to be waiting data on the computer's serial input buffer.
    def getCommandSet(self, src):
        receivedCmdSet = None
        logging.debug(src + ': getCommand...')
        while (self.cmdMessenger.comm.in_waiting == 0):
            time.sleep(0.1)
        receivedCmdSet = self.c.receive()
        logging.debug(src + ': getCommand complete.')
        if (receivedCmdSet[0] == "CMDERROR"):
            logging.error("CMDERROR: " + receivedCmdSet[1][0])
        logging.debug(receivedCmdSet)
        return receivedCmdSet

    # Handles the gathering of the polling status from the connected Arduino / LED driver.
    # debug_trace takes a string that gets passed to the logging module.
    def arduino_ready(self, debug_trace):
        receivedCmdSet = LEDController.getCommandSet(debug_trace)
        if (receivedCmdSet != None):
            cmd = receivedCmdSet[0]
            result = receivedCmdSet[1][0]
            return (cmd == "ARDUINOBUSY" and result == False)
        else:
            return False

    # Sets all of the LEDs in the strip to the color desired, and for a duration equal to update_ms.
    def setColorAll(self, color, update_ms):
        color = self.constrainColor(color)
        self.c.send("SETCOLORALL", color, update_ms)
        self.getCommandSet('SCA return')

    # Sets a single LED (index) to the color desired, and for a duration equal to update_ms.
    def setColorSingle(self, color, index, update_ms):
        color = self.constrainColor(color)
        index = self.constrain(index, 0, self.numLEDs)
        self.c.send("SETCOLORSINGLE", index, color, update_ms)
        self.getCommandSet('SCS return')

    # Sets a number of LEDs, starting at st_led (index), to a desired color.
    # update_ms doesn't have much functionality here, as the update is instantaneous and there
    # is no pattern to update. Can be used to delay the controller's next check-in.
    def setColorRange(self, color, st_led, num, update_ms):
        color = self.constrainColor(color)
        st_led = self.constrain(st_led, 0, self.numLEDs-1)
        num = self.constrain(num, 0, self.numLEDs-st_led)
        self.c.send("SETCOLORRANGE", st_led, num, color, update_ms)
        self.getCommandSet('SCR return')

    # Sets the controller to activate the rainbow pattern.
    # Use update_ms to control how fast the pattern updates.
    def setPatternRainbow(self, update_ms):
        self.c.send("SETPATTERNRAINBOW", max(1, int(update_ms/256)))
        self.getCommandSet('SPR return')

    # Sets the controller to activate a theater chase pattern, consisting of alternating
    # color1 and color2. Update_ms defines how fast the pattern will update.
    def setPatternTheater(self, color1, color2, update_ms):
        color1 = self.constrainColor(color1)
        color2 = self.constrainColor(color2)
        self.c.send("SETPATTERNTHEATER", color1, color2, max(1, int(update_ms/self.numLEDs)))
        self.getCommandSet('SPT return')

    # Description
    def setPatternWipe(self, color, update_ms):
        color = self.constrainColor(color)
        self.c.send("SETPATTERNWIPE", color, max(1, int(update_ms/self.numLEDs)))
        self.getCommandSet('SPW return')

    # Description
    def setPatternScanner(self, color, update_ms):
        color = self.constrainColor(color)
        self.c.send("SETPATTERNSCANNER", color, max(1, int(update_ms/(2*self.numLEDs))))
        self.getCommandSet('SPS return')

    # Description
    def setPatternFade(self, color1, color2, steps, update_ms):
        color1 = self.constrainColor(color1)
        color2 = self.constrainColor(color2)
        self.c.send("SETPATTERNFADE", color1, color2, steps, max(1, int(update_ms/steps)))
        self.getCommandSet('SPF return')

    # Description
    def setBrightness(self, brightness):
        brightness = self.constrain(brightness, 0, 255)
        self.c.send("SETBRIGHTNESSALL", brightness)
        self.getCommandSet('Brightness return')

    # Description
    def setLedsOff(self, update_ms):
        self.c.send("SETLEDSOFF", update_ms)
        self.getCommandSet('SLO return')

    # Description
    def setNoCmd(self, flag=True):
        self.c.send("NOCOMMAND", flag)
        self.getCommandSet('SNC return')

    # Alternates two colors on a fade effect to give a 'breathing' animation.
    # Uses the same parameters as fade.
    def breathe_effect(self):
        self.last_cycle = self.constrain(self.last_cycle, 0, 1) # ensure we start correctly
        if self.last_cycle == 0:
            self.setPatternFade(
                self.cmd_parameters['color1'],
                self.cmd_parameters['color2'],
                self.cmd_parameters['num-steps'],
                self.cmd_parameters['interval']
            )
            self.last_cycle += 1
        elif self.last_cycle == 1:
            self.setPatternFade(
                self.cmd_parameters['color2'],
                self.cmd_parameters['color1'],
                self.cmd_parameters['num-steps'],
                self.cmd_parameters['interval']
            )
            self.last_cycle -= 1

    # Description
    def constrainColor(self, color):
        return self.constrain(color, 0x000001, 0xFFFFFF)

    # Description
    def constrain(self, number, minimum, maximum):
        number = min(number, maximum)
        number = max(number, minimum)
        return number

    def repeat(self):
        logging.debug("repeat called")
        if self.arduino_ready('repeat function'):
            self.cmd_lambdas[self.last_command_lambda]()

    def set_command(self, cmd, **kwargs):
        logging.debug("set_command: " + str(cmd))
        self.last_command_lambda = cmd
        for key, value in kwargs.items():
            self.cmd_parameters[key] = value

    def get_interval(self):
        return self.cmd_parameters['interval']



LARGE_FONT = ("Segoe UI", 14)
MEDIUM_FONT = ("Segoe UI", 10)

class ControllerUI(tk.Tk):

    def __init__(self, *args, **kwargs):

        tk.Tk.__init__(self, *args, **kwargs)

        container = ttk.Frame(self)
        container.grid()

        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}

        # for F in (StartPage, ): #If there are more than one page, can add them here.
        F = StartPage
        frame = F(container, self)
        self.frames[F] = frame
        frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame(StartPage)

    def show_frame(self, cont):
        frame = self.frames[cont]
        frame.tkraise()

class StartPage(ttk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        page_label = ttk.Label(self, text="LED Controller", font=LARGE_FONT)
        page_label.grid(ipady=10, ipadx=10)
        
        button_container = ttk.Frame(self)
        button_container.grid()
        button_container.grid_rowconfigure(3, weight=1)
        button_container.grid_columnconfigure(3, weight=1)

        column_1_label = ttk.Label(self, text="Patterns", font=MEDIUM_FONT)
        column_1_label.grid(row=0, column=0)

        column_2_3_label = ttk.Label(self, text="Color Config", font=MEDIUM_FONT)
        column_2_3_label.grid(row=0, column=1, columnspan=2)

        rainbow_button = ttk.Button(
            button_container,
            text="rainbow",
            command=lambda: LEDController.set_command('SPR', interval=200)
        )
        rainbow_button.grid(row=1, column=0)

        color_1_choice_button = ttk.Button(button_container, text="Primary Color", command=lambda: style.configure("Color.TLabel", background=self.get_color(1)))
        color_1_choice_button.grid(row=1, column=1)
        
        style = ttk.Style()
        style.configure("Color.TLabel", foreground="black", background="green")
        color_cell = ttk.Label(button_container, style="Color.TLabel", text="test")
        color_cell.grid(row=1, column=2)

        button3 = ttk.Button(
            button_container,
            text="Red",
            command=lambda: LEDController.set_command('SCA', color1=16711680, interval=1000)
        )
        button3.grid(row=1, column=0)

        button4 = ttk.Button(
            button_container,
            text="Blue",
            command=lambda: LEDController.set_command('SCA', color1=255, interval=1000)
        )
        button4.grid(row=1, column=2)

    def get_color(self, desired_tuple):
        color = askcolor()
        return color[desired_tuple]


# Read configuration file and set up attributes
def setup():
    global LEDController

    config = configparser.ConfigParser()
    try:

        config.read_file(open("LEDControllerSettings.ini"))
        timeout = config.getint('LEDControllerSettings', 'Timeout')
        baudrate = config.getint('LEDControllerSettings', 'Baudrate')
        port = config.get('LEDControllerSettings', 'COMPort')
        log_level = config.get('LEDControllerSettings', 'LogLevel')
        LEDs = config.getint('LEDControllerSettings', 'LEDs')
        brightness = config.getint('LEDControllerSettings', 'Brightness')

        LEDController = LEDController(timeout, port, baudrate, LEDs, brightness)
        LEDController.setupCmdMessenger()

        numeric_level = getattr(logging, log_level.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: {0}'.format(log_level))

        setup_log(numeric_level)

        print("Using Serial Port: {0}. OK.".format(LEDController.port))
        logging.info("Program Started with Serial Port: {0}, Timeout: {1}, Baudrate: {2}, Log Level: {3}. Num LEDs set to {4}."\
            .format(LEDController.port, timeout, baudrate, log_level, LEDs))

    except FileNotFoundError as e:
        setup_log(logging.DEBUG)
        logging.critical("Unable to open \'LEDControllerSettings.ini\'. Error Text: {!r}".format(e))
        print("Critical Error: Unable to open \'LEDControllerSettings.ini\'. See log file for details.")
        return False

    return True

def setup_log(level):
    logging.basicConfig(filename='LEDControllerLog.log',
        format='%(asctime)s:%(levelname)s: %(message)s', level=level)


# Runs once from main once setup is complete. Generally can be used to set brightness as
# a global before going into the main loop of the system - will also be used to set up any
# early parameters for UI before going into the main control loop, eg. Networking, alerts, etc.
def pre_run_commands():
    global LEDController
    if (LEDController.arduino_ready('prerun')):
        LEDController.setBrightness(LEDController.brightness)


# sets up a continuous check on the controller to maintain constant intercommunication between
# the UI/Controller code and the actual controller.
def update_controller():
    """Check the LED Controller, and issue, or re-issue a command as needed"""
    if LEDController.serial_has_waiting():
        LEDController.repeat()
    app.after(75, update_controller)


# Demo code that will go through all the possible command combinations that
# are exposed from the LEDController class and are implemented in the
# Arduino driver for the LED strips.
# Loops continuously - won't return - use as a test of the LED strip and
# communication between host computer and the attached Arduino before moving
# onto more complex behavior.
# Can be used as an example / reference of some of the functionality that can be used.
def run_demo():
    global LEDController
    random.seed()
    democmd = 0
    brightnessNotSet = True
    demoloop = 0
    while (True):
        if (LEDController.arduino_ready('main')):
            if (brightnessNotSet):
                print("set Brightness 100.")
                LEDController.setBrightness(100)
                brightnessNotSet = False
            elif (democmd == 0):
                print("Set Color all, red, 2 seconds.")
                LEDController.setColorAll(0xFF0000, 2000)
                democmd += 1
            elif (democmd == 1):
                print("Set Color Single, Blue, in the middle, 2 seconds.")
                LEDController.setColorSingle(0x0000FF, LEDController.numLEDs/2, 2000)
                democmd += 1
            elif (democmd == 2):
                print("Set Color Range, Green, 1/2 of the strip, 2 seconds.")
                LEDController.setColorRange(0x00FF00, 1, 60, 2000)
                democmd += 1
            elif (democmd == 3):
                print("Rainbow Pattern, 10 times, 200ms intervals - 2 seconds total.")
                LEDController.setPatternRainbow(200)
                demoloop += 1
                if (demoloop >= 10):
                    demoloop = 0
                    democmd += 1
            elif (democmd == 4):
                print("Theater Pattern, Black/White, 6 seconds")
                LEDController.setPatternTheater(0x000000, 0xFFFFFF, 6000)
                democmd += 1
            elif (democmd == 5):
                print("Wipe Pattern, random color, 250 ms intervals, 10 times")
                color = randint(0x000000, 0xFFFFFF)
                LEDController.setPatternWipe(color, 250)
                demoloop += 1
                if (demoloop >= 10):
                    demoloop = 0
                    democmd += 1
            elif (democmd == 6):
                print("Scanner Pattern, R, G, B, W, 500 ms passes each (4 total passes).")
                if demoloop == 0:
                    LEDController.setPatternScanner(0xFF0000, 500)
                if demoloop == 1:
                    LEDController.setPatternScanner(0x00FF00, 500)
                if demoloop == 2:
                    LEDController.setPatternScanner(0x0000FF, 500)
                if demoloop == 3:
                    LEDController.setPatternScanner(0xFFFFFF, 500)
                demoloop += 1
                if (demoloop >= 4):
                    demoloop = 0
                    democmd += 1
            elif (democmd == 7):
                print("Fade Pattern, R, G, B, W, to black, 500 ms passes each (4 total passes).")
                if demoloop == 0:
                    LEDController.setPatternFade(0xFF0000, 0x000000, 30, 500)
                if demoloop == 1:
                    LEDController.setPatternFade(0x00FF00, 0x000000, 30, 500)
                if demoloop == 2:
                    LEDController.setPatternFade(0x0000FF, 0x000000, 30, 500)
                if demoloop == 3:
                    LEDController.setPatternFade(0xFFFFFF, 0x000000, 30, 500)
                demoloop += 1
                if (demoloop >= 4):
                    demoloop = 0
                    democmd += 1
            elif (democmd == 8):
                print("Set LEDs off - 2 seconds.")
                LEDController.setLedsOff(2000)
                democmd = 0
        else:
            print('!')
        time.sleep(.01)

def end_program(end_condition):
    global LEDController
    # LEDController.ser.close()
    print("Complete. {}".format(end_condition))
    logging.info("Program End.")

def stop():
    print("Keyboard Interrupt - Shutting down...")
    logging.info("Keyboard Interrupt - Shutting down Serial Port.")
    end_program("")

# This needs to be available in the global scope so that update_controller() and main
# can both find it easily.
app = ControllerUI()

if __name__ == '__main__':
    try:
        if setup():
            pre_run_commands()
            app.after(500, update_controller)
            app.mainloop()
    except KeyboardInterrupt: # Called when user ends process with CTRL+C
        stop()
