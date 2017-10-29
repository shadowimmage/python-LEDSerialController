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
import base64 #for parsing hex color strings to numbers

# GUI things
import tkinter as tk
from tkinter import ttk
from tkinter.colorchooser import *


# LEDController needs to be global so that stop() can access it
# at any time when the keyboard interrupt is triggered.
LEDController = object

class LEDController(object):
    MAX_INTERVAL = 60000
    MIN_INTERVAL = 0

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
        self.brightness_set_cycle = True
        self.brightness_set_last_cmd = 'Breathe'
        # Store commands as lambdas so that they can be passed parameters
        # when commands change settings for the controller.
        self.cmd_lambdas = {
            'SCA1': lambda: self.setColorAll(
                self.cmd_parameters['color1'],
                self.cmd_parameters['interval']
            ),
            'SCA2': lambda: self.setColorAll(
                self.cmd_parameters['color2'],
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
        # Initial settings for commands - these get changed throughout the 
        # lifecycle of the program.
        self.cmd_parameters = {
            'color1': 0xFFFFFF,
            'color2': 0x000000,
            'st_led-index': 20,
            'num-steps': 100,
            'brightness': 0,
            'interval': 4000,
        }

    # Set up the PyCmdMessenger library (which also handles setup of the
    # serial port given and allows structured communication over serial.)
    def setupCmdMessenger(self):
        """Initialize the command messenger"""
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
        received_cmd_set = None
        logging.debug(src + ': getCommand...')
        while (self.cmdMessenger.comm.in_waiting == 0): # blocking - here as a final check before self.c.receive()
            time.sleep(0.1)
        received_cmd_set = self.c.receive()
        logging.debug(src + ': getCommand complete.')
        if (received_cmd_set[0] == "CMDERROR"):
            logging.error("CMDERROR: " + received_cmd_set[1][0])
        logging.debug(received_cmd_set)
        return received_cmd_set

    # Handles the gathering of the polling status from the connected Arduino / LED driver.
    # debug_trace takes a string that gets passed to the logging module.
    def arduino_ready(self, debug_trace):
        received_cmd_set = self.getCommandSet(debug_trace)
        if (received_cmd_set != None):
            cmd = received_cmd_set[0]
            result = received_cmd_set[1][0]
            return (cmd == "ARDUINOBUSY" and result == False)
        else:
            return False

    # --- Command definitions --- Add additional commands below here, integrate command lambdas above.
        
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

    # Wipe pattern sets each led in sequence to color given over over the time period.
    def setPatternWipe(self, color, update_ms):
        color = self.constrainColor(color)
        self.c.send("SETPATTERNWIPE", color, max(1, int(update_ms/self.numLEDs)))
        self.getCommandSet('SPW return')

    # Sets LEDs in sequence to give a bright point traveling along the string and back again.
    def setPatternScanner(self, color, update_ms):
        color = self.constrainColor(color)
        self.c.send("SETPATTERNSCANNER", color, max(1, int(update_ms/(2*self.numLEDs))))
        self.getCommandSet('SPS return')

    # Starts at color 1 and then fades to color 2 - a component of the breathe effect (transitions
    # between color 1 and 2 and then returns to color 1 again)
    def setPatternFade(self, color1, color2, steps, update_ms):
        color1 = self.constrainColor(color1)
        color2 = self.constrainColor(color2)
        self.c.send("SETPATTERNFADE", color1, color2, steps, max(1, int(update_ms/steps)))
        self.getCommandSet('SPF return')

    # Sets the global brightness parameter on the LED controller (Arduino or similar) which will
    # handle scaling brightness of given color parameters. 
    # Slow - Should not be used often or for patterning.
    def setBrightness(self, brightness):
        brightness = self.constrain(brightness, 0, 255)
        self.c.send("SETBRIGHTNESSALL", brightness)
        self.brightness_set_cycle = False # return controller to normal operations once complete
        self.set_command_brightness()
        self.getCommandSet('Brightness return')

    # Turns off LEDs
    def setLedsOff(self, update_ms):
        self.c.send("SETLEDSOFF", update_ms)
        self.getCommandSet('SLO return')

    # Use to send no command at interval - controller will continue last command.
    def setNoCmd(self, flag=True):
        self.c.send("NOCOMMAND", flag)
        self.getCommandSet('SNC return')

    # --- Composite Effect definitions --- Use some of the primitives above in combination
    # to create more advanced effects.
        
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

    # --- Utility definitions ---
    
    # Description
    def constrainColor(self, color):
        return self.constrain(color, 0x000000, 0xFFFFFF)

    # Description
    def constrain(self, number, minimum, maximum):
        number = min(number, maximum)
        number = max(number, minimum)
        return number

    def repeat(self):
        """Executes transmission of the command that was set or last set.

        Commands are only executed through this function under normal operating conditions,
        allowing settings and variables to be modified through the UI semi-asynchronously
        between command calls"""
        logging.debug("repeat called")
        if self.arduino_ready('repeat function'):
            self.cmd_lambdas[self.last_command_lambda]()

    def set_command(self, cmd, **kwargs):
        logging.debug("set_command: " + str(cmd))
        self.last_command_lambda = cmd
        for key, value in kwargs.items():
            self.cmd_parameters[key] = value

    def set_command_brightness(self):
        """Similar to temporarily sets the next command to set the LED brightness.
        Returns the last_command_lambda to it's previous value after execution."""
        if self.brightness_set_cycle:
            # Temporarily interrupt next repeat command to allow a brightness command to be sent
            self.brightness_set_last_cmd = self.last_command_lambda
            self.last_command_lambda = 'SBA'
            ### This is returned to False in the actual set brightness command
            # self.brightness_set_cycle = False
        else:
            # Return last_command_lambda to the last task that was being performed.
            self.last_command_lambda = self.brightness_set_last_cmd
            self.brightness_set_cycle = True

    def set_brightness(self, brightness):
        """Sets the internal brightness storage to the passed value."""
        brightness = self.constrain(brightness, 0, 255)
        self.cmd_parameters['brightness'] = brightness
        self.brightness_set_cycle = True # ensure that brightness setting will happen
        self.set_command_brightness()

    def get_interval(self):
        return self.cmd_parameters['interval']

    def set_interval(self, interval):
        self.cmd_parameters['interval'] = self.constrain(interval, self.MIN_INTERVAL, self.MAX_INTERVAL)

    def set_color(self, color, color_1_2):
        """Set one of the LEDController's Color variables

        color: a string representing a hex color value in RGB. "FFFFFF" would  be 100% white
        color_1_2: an integer selecting which color variable to set to color
        """
        color_num = int.from_bytes(base64.b16decode(color, True), byteorder='big')
        if color_1_2 == 1:
            self.cmd_parameters['color1'] = color_num
        elif color_1_2 == 2:
            self.cmd_parameters['color2'] = color_num
        else:
            pass

# UI ------------------------------

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

        # for F in (StartPage, ): #If there are more than one page, can add them as part of a loop here.
        F = MainUIPage
        frame = F(container, self)
        self.frames[F] = frame
        frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame(F)

    def show_frame(self, cont):
        frame = self.frames[cont]
        frame.tkraise()

class MainUIPage(ttk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        page_label = ttk.Label(self, text="LED Controller", font=LARGE_FONT)
        page_label.grid(ipady=10, ipadx=10)

        button_container = ttk.Frame(self)
        button_container.grid()
        # counters to keep track of element locations on control grid
        row_counter = 7 #max
        column_counter = 3 #max
        button_container.grid_rowconfigure(row_counter, weight=1)
        button_container.grid_columnconfigure(column_counter, weight=1)
        row_counter = 0
        column_counter = 0

        # ROW 0 - Section Headers
        pattern_column_label = ttk.Label(button_container, text="Patterns", font=MEDIUM_FONT)
        pattern_column_label.grid(row=row_counter, column=column_counter)
        column_counter += 1

        column_2_3_label_colors = ttk.Label(button_container, text="Color Config", font=MEDIUM_FONT)
        column_2_3_label_colors.grid(row=row_counter, column=column_counter, columnspan=2)

        # ROW 1
        row_counter += 1
        column_counter = 0
        rainbow_pattern_button = ttk.Button(
            button_container,
            text="Rainbow",
            command=lambda: LEDController.set_command('SPR')
        )
        rainbow_pattern_button.grid(row=row_counter, column=column_counter)
        column_counter += 1

        color_1_choice_button = ttk.Button(
            button_container,
            text="Primary Color",
            command=lambda: self.apply_colors(self.get_color(1), color_1_label_style, 1)
        )
        color_1_choice_button.grid(row=row_counter, column=column_counter)
        column_counter += 1

        color_1_label_style = ttk.Style()
        color_1_label_style.configure("Color1.TLabel", foreground="black", background="green")
        color_1_cell = ttk.Label(button_container, style="Color1.TLabel", text=" Primary ")
        color_1_cell.grid(row=row_counter, column=column_counter)

        # ROW 2
        column_counter = 0
        row_counter += 1
        theater_pattern_button = ttk.Button(
            button_container,
            text="Theater",
            command=lambda: LEDController.set_command('SPT')
        )
        theater_pattern_button.grid(row=row_counter, column=column_counter)
        column_counter += 1

        color_2_choice_button = ttk.Button(
            button_container,
            text="Secondary Color",
            command=lambda: self.apply_colors(self.get_color(1), color_1_label_style, 2)
        )
        color_2_choice_button.grid(row=row_counter, column=column_counter)
        column_counter += 1

        color_2_label_style = ttk.Style()
        color_2_label_style.configure("Color2.TLabel", foreground="black", background="green")
        color_2_cell = ttk.Label(button_container, style="Color2.TLabel", text=" Secondary ")
        color_2_cell.grid(row=row_counter, column=column_counter)

        # ROW 3
        column_counter = 0
        row_counter += 1
        wipe_pattern_button = ttk.Button(
            button_container,
            text="Wipe",
            command=lambda: LEDController.set_command('SPW')
        )
        wipe_pattern_button.grid(row=row_counter, column=column_counter)
        column_counter += 1

        column_2_3_label_interval = ttk.Label(
            button_container,
            text="Interval (ms)",
            font=MEDIUM_FONT
        )
        column_2_3_label_interval.grid(row=row_counter, column=column_counter, columnspan=2)

        # ROW 4
        column_counter = 0
        row_counter += 1
        scanner_pattern_button = ttk.Button(
            button_container,
            text="Scanner",
            command=lambda: LEDController.set_command('SPS')
        )
        scanner_pattern_button.grid(row=row_counter, column=column_counter)
        column_counter += 1

        # The following piece of magic comes from https://stackoverflow.com/questions/4140437/interactively-validating-entry-widget-content-in-tkinter/4140988#4140988
        # valid percent substitutions (from the Tk entry man page)
        # note: you only have to register the ones you need; this
        # example registers them all for illustrative purposes
        #
        # %d = Type of action (1=insert, 0=delete, -1 for others)
        # %i = index of char string to be inserted/deleted, or -1
        # %P = value of the entry if the edit is allowed
        # %s = value of entry prior to editing
        # %S = the text string being inserted or deleted, if any
        # %v = the type of validation that is currently set
        # %V = the type of validation that triggered the callback
        #      (key, focusin, focusout, forced)
        # %W = the tk name of the widget
        validate_interval_entry_cmd = (
            button_container.register(self.validate_interval_entry), '%P', '%s', '%S'
        )
        interval_var = tk.StringVar()
        interval_entry_field = ttk.Entry(
            button_container,
            validate="key",
            validatecommand=validate_interval_entry_cmd,
            textvariable=interval_var,
            justify=tk.CENTER,
            width=10
        )
        interval_entry_field.grid(row=row_counter, column=column_counter)
        column_counter += 1

        interval_apply_button = ttk.Button(
            button_container,
            text="Apply",
            command=lambda: LEDController.set_interval(int(interval_var.get()))
        )
        interval_apply_button.grid(row=row_counter, column=column_counter)

        # ROW 5
        column_counter = 0
        row_counter += 1
        fade_pattern_button = ttk.Button(
            button_container,
            text="Fade",
            command=lambda: LEDController.set_command('SPF')
        )
        fade_pattern_button.grid(row=row_counter, column=column_counter)
        column_counter += 1

        column_2_3_label_fine = ttk.Label(button_container, text="Fine Control", font=MEDIUM_FONT)
        column_2_3_label_fine.grid(row=row_counter, column=column_counter, columnspan=2)
        column_counter += 1

        # ROW 6
        column_counter = 0
        row_counter += 1
        breathe_pattern_button = ttk.Button(
            button_container,
            text="Breathe",
            command=lambda: LEDController.set_command('Breathe')
        )
        breathe_pattern_button.grid(row=row_counter, column=column_counter)
        column_counter += 1

        set_all_pri_button = ttk.Button(
            button_container,
            text="Set All Primary",
            command=lambda: LEDController.set_command('SCA1')
        )
        set_all_pri_button.grid(row=row_counter, column=column_counter)
        column_counter += 1

        set_all_sec_button = ttk.Button(
            button_container,
            text="Set All Secondary",
            command=lambda: LEDController.set_command('SCA2')
        )
        set_all_sec_button.grid(row=row_counter, column=column_counter)

        # ROW 7
        column_counter = 0
        row_counter += 1
        brightness_label = ttk.Label(button_container, text="Brightness", font=MEDIUM_FONT)
        brightness_label.grid(row=row_counter, column=column_counter)
        column_counter += 1

        brightness_scaler = tk.Scale(
            button_container,
            from_=1,
            to=255,
            resolution=10,
            orient=tk.HORIZONTAL,
        )
        brightness_scaler.grid(row=row_counter, column=column_counter)
        column_counter += 1

        set_brightness_button = ttk.Button(
            button_container,
            text="Set",
            command=lambda: LEDController.set_brightness(int(brightness_scaler.get()))
        )
        set_brightness_button.grid(row=row_counter, column=column_counter)


    def validate_interval_entry(self, P, s, S):
        """Only allows ints"""
        if S in '1234567890':
            try:
                int(P)
                return True
            except ValueError:
                return False
        else:
            return False

    def get_color(self, desired_tuple):
        color = askcolor()
        return color[desired_tuple]

    def apply_colors(self, color_str, label_style, color_1_2):
        if color_1_2 == 1:
            label_style.configure("Color1.TLabel", background=color_str)
            color_str = color_str[1:]
            LEDController.set_color(color_str, 1)
        elif color_1_2 == 2:
            label_style.configure("Color2.TLabel", background=color_str)
            color_str = color_str[1:]
            LEDController.set_color(color_str, 2)

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
#TODO: load UI settings
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
    #TODO save UI settings for program restart
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
