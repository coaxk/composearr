import time
import sys
import os

BLUE = "\033[38;5;33m"
CYAN = "\033[38;5;45m"
RESET = "\033[0m"

frames = [
f"""{BLUE}      ##         .{RESET}
{BLUE}## ## ##        =={RESET}
{BLUE}## ## ## ## ## ==={RESET}
{BLUE}/\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\\\___{RESET}{CYAN}/ ==={RESET}
{BLUE}{{                       /{RESET}{CYAN}  ===-{RESET}
{BLUE}\\______ O           __/{RESET}
{BLUE}  \\    \\         __/{RESET}
{BLUE}   \\____\\_______/{RESET}
""",
f"""{BLUE}      ##         :{RESET}
{BLUE}## ## ##        ==={RESET}
{BLUE}## ## ## ## ## ===={RESET}
{BLUE}/\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\\\___{RESET}{CYAN}/  ==={RESET}
{BLUE}{{                       /{RESET}{CYAN} -===-{RESET}
{BLUE}\\______ O           __/{RESET}
{BLUE}  \\    \\         __/{RESET}
{BLUE}   \\____\\_______/{RESET}
""",
f"""{BLUE}      ##         |{RESET}
{BLUE}## ## ##       ===={RESET}
{BLUE}## ## ## ## ## ===={RESET}
{BLUE}/\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\\\___{RESET}{CYAN}/ -==={RESET}
{BLUE}{{                       /{RESET}{CYAN} --==-{RESET}
{BLUE}\\______ O           __/{RESET}
{BLUE}  \\    \\         __/{RESET}
{BLUE}   \\____\\_______/{RESET}
""",
f"""{BLUE}      ##         *{RESET}
{BLUE}## ## ##        ==={RESET}
{BLUE}## ## ## ## ## ===={RESET}
{BLUE}/\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\\\___{RESET}{CYAN}/  ==={RESET}
{BLUE}{{                       /{RESET}{CYAN}   ===-{RESET}
{BLUE}\\______ O           __/{RESET}
{BLUE}  \\    \\         __/{RESET}
{BLUE}   \\____\\_______/{RESET}
"""
]

sys.stdout.write("\033[?25l")

try:
    while True:
        for frame in frames:
            os.system('cls')
            print(frame)
            time.sleep(0.2)
except KeyboardInterrupt:
    sys.stdout.write("\033[?25h")
    print(f"\n{RESET}Animation stopped.")
