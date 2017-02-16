# python-LEDSerialController
Controller (and GUI?) for talking with an Arduino running some NeoPixel RGB LEDs or some DotStar RGB LEDs - depending on the arduino code that you're running. 
## Current development(s)
This is currently split into 2 repositories - one for the Arduino code, and this one for the desktop host software.
Arduino code can currently be found here: https://github.com/shadowimmage/Arduino-NeoPixel-Serial
## Dependencies and Thanks
Below I'm listing a collection of resources that I've used to help figure out how to implement this project. 
### CmdMessenger
I've made pretty heavy use of CmdMessenger to facilitate my computer talking over serial - a lot of work was still trial and error, but less that it would have taken, had I had to create my own protocol.
- https://github.com/harmsm/PyCmdMessenger
- https://github.com/thijse/Arduino-CmdMessenger
### Adafruit
Always helpful/useful.
- https://github.com/adafruit/Adafruit_NeoPixel
- https://github.com/adafruit/Adafruit_DotStar
- https://learn.adafruit.com/multi-tasking-the-arduino-part-3?embeds=allow&view=all#using-neopatterns
- https://learn.adafruit.com/adafruit-neopixel-uberguide/power?view=all#overview
### Others
For inspriation:
- https://wp.josh.com/category/neopixel/
