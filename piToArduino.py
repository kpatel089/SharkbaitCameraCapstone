#!/usr/bin/#!/usr/bin/env python3
import serial # imports serial library
import time # imports time library

def sendToArduino(data):
    if __name__ == '__main__':
        ser = serial.Serial('/dev/ttyACM0', 9600, timeout=1) # initializes serial communication
        ser.reset_input_buffer() # flushes bytes

        command = data + "\n"
        ser.write(command.encode('utf-8')) # sends the data through serial
        line = ser.readline().decode('utf-8').rstrip() # reading back anything it sends
        print(line) # prints message
        # time.sleep(1) # might be needed

