# BiasLights.py 
# Written by Chase Sawyer
# February 2017
# Version 0 - Brand new.
# 
# INSTRUCTIONS FOR USE: 

from tkinter import * # see knowpapa.com/cchoser/
from tkinter.colorchooser import askcolor
import random #for testing protocol / led colors
from random import randint
import serial # I/O communication with Arduino controller
# import sys # thought was needed for keyboard interrupt
import signal # Capture keyboard interrupt
import logging # Program logging
import configparser # Reading / writing configurations

# LEDController needs to be global so that stop() can access it 
# at any time when the keyboard interrupt is triggered.
LEDController = object

class LEDController(object):

	def __init__(self, timeout, port, baudrate, ser, LEDs):
		self.timeout = timeout
		self.port = port
		self.baudrate = baudrate
		self.ser = ser
		self.LEDs = LEDs

	def setupSer(self):
		self.ser.timeout = self.timeout
		self.ser.baudrate = self.baudrate
		self.ser.port = self.port
		self.ser.open()

# Read configuration file and set up attributes
def setup():
	global LEDController

	config = configparser.ConfigParser()
	try:

		config.read_file(open("BiasLightSettings.ini"))
		timeout = config.getint('BiasLightSettings', 'Timeout')
		baudrate = config.getint('BiasLightSettings', 'Baudrate')
		port = config.get('BiasLightSettings', 'COMPort')
		log_level = config.get('BiasLightSettings', 'LogLevel')
		LEDs = config.getint('BiasLightSettings', 'LEDs')

		LEDController = LEDController(timeout, port, baudrate, serial.Serial(), LEDs)
		LEDController.setupSer()

		numeric_level = getattr(logging, log_level.upper(), None)
		if not isinstance(numeric_level, int):
			raise ValueError('Invalid log level: {0}'.format(log_level))

		setup_log(numeric_level)

		print("Using Serial Port: {0}. OK.".format(LEDController.ser.name))
		logging.info("Program Started with Serial Port: {0}, Timeout: {1}, Baudrate: {2}, Log Level: {3}. Num LEDs set to {4}."\
			.format(LEDController.ser.name, timeout, baudrate, log_level, LEDs))

	except FileNotFoundError as e:
		setup_log(logging.DEBUG)
		logging.critical("Unable to open \'BiasLightSettings.ini\'. Error Text: {!r}".format(e))
		print("Critical Error: Unable to open \'BiasLightSettings.ini\'. See log file for details.")
		return False

	return True

def setup_log(level):
	logging.basicConfig(filename='biasLightingLog.log',
			format='%(asctime)s:%(levelname)s: %(message)s', level=level)

def main():
	global LEDController
	# Main control area - interfaces for brightness and color settings
	if setup():
		random.seed()
		j = 1
		LEDController.ser.reset_input_buffer() # clear anything in input
		logging.info("Waiting for Arduino...")
		while(True):
			inReady = LEDController.ser.read(1).decode()
			if (inReady == '1'):
				data = [None] * (LEDController.LEDs * 4 + 1)
				data[0] = 240
				for i in range(1, 61):
					data[(i-1)*4+1] = i #LED number
					data[(i-1)*4+2] = 0 #Red
					data[(i-1)*4+3] = 0 #Green
					data[(i-1)*4+4] = 0 #Blue
				data[(j-1)*4+1] = j
				data[(j-1)*4+2] = 150 #Red
				data[(j-1)*4+3] = 150 #Green
				data[(j-1)*4+4] = 150 #Blue
				LEDController.ser.write(bytes(data))
				j += 1
				if (j > 60):
					j = 1
				# for i in range(1, LEDController.LEDs+1):
				# 	data[(i-1)*4+1] = i #LED number
				# 	data[(i-1)*4+2] = randint(0,20) #Red
				# 	data[(i-1)*4+3] = randint(0,0) #Green
				# 	data[(i-1)*4+4] = randint(0,20) #Blue
				# LEDController.ser.write(bytes(data))
				# logging.info("Sent Color Data!")
			else: 
				pass
	else:
		pass


def end_program(end_condition):
	global LEDController
	LEDController.ser.close()
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