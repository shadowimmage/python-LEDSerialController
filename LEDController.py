# LEDController.py 
# Written by Chase Sawyer
# February 2017
# Version 0 - Brand new.
# 
# INSTRUCTIONS FOR USE: 

import PyCmdMessenger # for communication with Arduino
import random #for testing protocol / led colors
from random import randint
import serial # I/O communication with Arduino controller
import signal # Capture keyboard interrupt
import logging # Program logging
import configparser # Reading / writing configurations
import time # for delays, etc.

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
		self.commands = [["CMDERROR","s"],
						["SETCOLORALL","LL"],
						["SETCOLORSINGLE","bLL"],
						["SETCOLORRANGE","bbLL"],
						["SETPATTERNRAINBOW","L"],
						["SETPATTERNTHEATER","LLL"],
						["SETPATTERNWIPE","LL"],
						["SETPATTERNSCANNER","LL"],
						["SETPATTERNFADE","LLIL"],
						["SETBRIGHTNESSALL","b"],
						["SETLEDSOFF","L"],
						["ARDUINOBUSY","?"],
						["NOCOMMAND","?"],
						["CMDCONF","L"]]

	# Set up the PyCmdMessenger library (which also handles setup of the
	# serial port given and allows structured communication over serial.)
	def setupCmdMessenger(self):
		self.cmdMessenger = PyCmdMessenger.ArduinoBoard(self.port, baud_rate=self.baudrate)
		self.c = PyCmdMessenger.CmdMessenger(self.cmdMessenger,self.commands)

	# Handler for returned commands from the device connected at the other 
	# end of the serial line. Returns the Command that was received.
	# Blocks while waiting for a response over serial by checking for there
	# to be waiting data on the computer's serial input buffer.
	def getCommandSet(self, src):
		receivedCmdSet = None
		logging.debug(src + ': getCommand...')
		while (self.cmdMessenger.comm.in_waiting == 0):
			time.sleep(0.0)
		receivedCmdSet = self.c.receive()
		logging.debug(src + ': getCommand complete.')
		if (receivedCmdSet[0] == "CMDERROR"):
			logging.error("CMDERROR: " + receivedCmdSet[1][0])
		logging.debug(receivedCmdSet)
		return receivedCmdSet

	# Description
	def setColorAll(self, color, update_ms):
		color = self.constrainColor(color)
		self.c.send("SETCOLORALL", color, update_ms)
		self.getCommandSet('SCA return')

	# Description
	def setColorSingle(self, color, index, update_ms):
		color = self.constrainColor(color)
		index = self.constrain(index, 0, self.numLEDs)
		self.c.send("SETCOLORSINGLE", index, color, update_ms)
		self.getCommandSet('SCS return')

	# Description
	def setColorRange(self, color, st_led, num, update_ms):
		color = self.constrainColor(color)
		st_led = self.constrain(st_led, 0, self.numLEDs-1)
		num = self.constrain(num, 0, self.numLEDs-st_led)
		self.c.send("SETCOLORRANGE", st_led, num, color, update_ms)
		self.getCommandSet('SCR return')

	# Description
	def setPatternRainbow(self, update_ms):
		self.c.send("SETPATTERNRAINBOW", max(1, int(update_ms/256)))
		self.getCommandSet('SPR return')

	# Description
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

	# Description
	def constrainColor(self, color):
		return self.constrain(color, 0x000001, 0xFFFFFF)

	# Description
	def constrain(self, number, minimum, maximum):
		number = min(number, maximum)
		number = max(number, minimum)
		return number


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

def main():
	global LEDController
	# Main control area - interfaces for brightness and color settings
	if setup():
		# do the demo patterns program indefinitely.
		# run_demo()
		pre_run_commands()
		while(True):
			if (arduino_ready('main')):
				LEDController.setColorAll(0xfcff56, 2000)
	else:
		pass

def pre_run_commands():
	global LEDController
	if (arduino_ready('prerun')):
		LEDController.setBrightness(LEDController.brightness)

def arduino_ready(debug_trace):
	receivedCmdSet = LEDController.getCommandSet(debug_trace)
	if (receivedCmdSet != None):
		cmd = receivedCmdSet[0]
		result = receivedCmdSet[1][0]
		return (cmd == "ARDUINOBUSY" and result == False)
	else:
		return False

# Demo code that will go through all the possible command combinations that
# are exposed from the LEDController class and are implemented in the 
# Arduino driver for the LED strips.
# Loops continuously - won't return - use as a test of the LED strip and 
# communication between host computer and the attached Arduino before moving
# onto more complex behaviour.
def run_demo():
	global LEDController
	random.seed()
	democmd = 0
	brightnessNotSet = True
	demoloop = 0
	while(True):
		if (arduino_ready('main')):
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

if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt: # Called when user ends process with CTRL+C
		stop()