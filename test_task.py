import subprocess

def open_calculator():
    """Open Windows Task Manager"""
    try:
        subprocess.Popen('calc.exe')
    except Exception as e:
        print(f"Error opening Task Manager: {e}")
    


open_calculator()