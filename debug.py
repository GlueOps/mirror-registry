import os
import sys
if len(sys.argv) < 2:
    print("❌ Error: No YAML file path provided!")
    sys.exit(1)

config_path = sys.argv[1]  # Get the file path from GitHub Actions input

if not os.path.isfile(config_path):
    print(f"❌ Error: Config file '{config_path}' not found!")
    sys.exit(1)
paths = [
    "/usr/src/app",
    "/github/workspace",
    "/"
]
for path in paths:
    dir_list = os.listdir(path) 
    print(dir_list)