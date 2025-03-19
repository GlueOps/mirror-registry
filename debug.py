import os

paths = [
    "/usr/src/app",
    "/github/workspace",
    "/"
]
for path in paths:
    dir_list = os.listdir(path) 
    print(dir_list)