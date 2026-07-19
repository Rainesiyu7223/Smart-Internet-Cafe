import time
from smbus2 import SMBus

DISPLAY_TEXT_ADDR = 0x3e
DISPLAY_RGB_ADDR = 0x62

def init_lcd():
    """Initialize the Grove RGB LCD Display."""
    try:
        with SMBus(1) as bus:
            # Initialize the display mode
            bus.write_byte_data(DISPLAY_TEXT_ADDR, 0x80, 0x01) # 清屏
            time.sleep(0.05)
            bus.write_byte_data(DISPLAY_TEXT_ADDR, 0x80, 0x0F) # 打开显示与光标
            bus.write_byte_data(DISPLAY_TEXT_ADDR, 0x80, 0x38) # 2行显示模式
            
            # (R=255, G=255, B=255)
            bus.write_byte_data(DISPLAY_RGB_ADDR, 0, 0)
            bus.write_byte_data(DISPLAY_RGB_ADDR, 1, 0)
            bus.write_byte_data(DISPLAY_RGB_ADDR, 0x08, 0xAA)
            bus.write_byte_data(DISPLAY_RGB_ADDR, 0x04, 255)
            bus.write_byte_data(DISPLAY_RGB_ADDR, 0x03, 255)
            bus.write_byte_data(DISPLAY_RGB_ADDR, 0x02, 255)
            print("Successfully initialized Grove RGB LCD via I2C.")
    except Exception as e:
        print(f"Failed to initialize LCD Display: {e}")

def set_lcd_backlight(r, g, b):
    """Set LCD backlight color via RGB values."""
    try:
        with SMBus(1) as bus:
            bus.write_byte_data(DISPLAY_RGB_ADDR, 0x04, r)
            bus.write_byte_data(DISPLAY_RGB_ADDR, 0x03, g)
            bus.write_byte_data(DISPLAY_RGB_ADDR, 0x02, b)
    except Exception:
        pass

def display_text(text):
    """Display a string text on the LCD (Max 16 chars per line)."""
    try:
        with SMBus(1) as bus:
            # Clear the screen and reset the cursor
            bus.write_byte_data(DISPLAY_TEXT_ADDR, 0x80, 0x01)
            time.sleep(0.05)
            
            # Writes the ASCII code of a character verbatim
            for char in text:
                bus.write_byte_data(DISPLAY_TEXT_ADDR, 0x40, ord(char))
    except Exception as e:
        print(f"[Actuator Error] LCD display error: {e}")
