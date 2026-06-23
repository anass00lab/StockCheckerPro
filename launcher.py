import subprocess
import sys
import os

# Get the directory where this launcher lives
app_dir = os.path.dirname(os.path.abspath(__file__))
main_script = os.path.join(app_dir, "main.py")

# Launch the app
subprocess.Popen([sys.executable, main_script], cwd=app_dir)
