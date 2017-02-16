# LEDController.py 
# Written by Chase Sawyer
# February 2017
# Version 0 - Brand new.
# 
# INSTRUCTIONS FOR USE: 

import PyCmdMessenger # for communication with Arduino
from tkinter import * # see knowpapa.com/cchoser/
from tkinter.colorchooser import askcolor
import random #for testing protocol / led colors
from random import randint
import serial # I/O communication with Arduino controller
# import sys # thought was needed for keyboard interrupt
import signal # Capture keyboard interrupt
import logging # Program logging
import configparser # Reading / writing configurations
import time

# LEDController needs to be global so that stop() can access it 
# at any time when the keyboard interrupt is triggered.
LEDController = object

class LEDController(object):

	def __init__(self, timeout, port, baudrate, LEDs):
		self.timeout = timeout
		self.port = port
		self.baudrate = baudrate
		self.LEDs = LEDs
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

	
	def setupCmdMessenger(self):
		self.cmdMessenger = PyCmdMessenger.ArduinoBoard(self.port, baud_rate=self.baudrate)
		self.c = PyCmdMessenger.CmdMessenger(self.cmdMessenger,self.commands)

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

		LEDController = LEDController(timeout, port, baudrate, LEDs)
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
		random.seed()
		last = 2
		brightnessNotSet = True
		while(True):
			receivedCmdSet = None
			print('checking...')
			while (LEDController.cmdMessenger.comm.in_waiting == 0):
				time.sleep(0.0)
			receivedCmdSet = LEDController.c.receive()
			print('check Complete')
			print(receivedCmdSet)
			if (receivedCmdSet != None):
				cmd = receivedCmdSet[0]
				result = receivedCmdSet[1][0]
				# print(receivedCmdSet)
				# print(cmd)
				# print(result)
				if (cmd == "ARDUINOBUSY" and result == False):
					if (brightnessNotSet):
						LEDController.c.send("SETBRIGHTNESSALL",10)
						ret = LEDController.c.receive()
						print(ret)
						brightnessNotSet = False
					elif (last == 2):
						LEDController.c.send("SETCOLORSINGLE",
							randint(0, LEDController.LEDs),
							# 10,
							randint(0x000000, 0xFFFFFF),
							2000)
						ret = LEDController.c.receive()
						print(ret)
						last = 1
					else:
						LEDController.c.send("SETLEDSOFF",
							# 0x000001,
							# randint(0x000000, 0xFFFFFF),
							# randint(0x000000, 0xFFFFFF),
							# 500,
							2000)
						ret = LEDController.c.receive()
						print(ret)
						last = 2
			else:
				print('!')
			time.sleep(.01)



			# LEDController.c.send("SETPATTERNRAINBOW",100)
			# ret = LEDController.c.receive()
			# print(ret)
			# time.sleep(0.5)
			# LEDController.c.send("SETCOLORALL",0xFFFFFF)
			# ret = LEDController.c.receive()
			# print(ret)
			# time.sleep(0.5)
			# logging.info("Sent Color Data!")
	else:
		pass


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