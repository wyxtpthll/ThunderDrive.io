# thunderdrive.io
Unofficial ThunderDrive.io python api

# login

Login data are stored in file config.txt.

File locations:
- ./config.txt (current dir)
- ~/config.txt (home dir)

Example: 

[thunderdrive]

username = xx@gmail.com

password = password


# Usage

file download:
- thunderdrive.py --downloadmode --list file1 file2 ....

file upload:
- thunderdrive.py --uploadmode --targetdir ThunderDriveUploadDir file1 file2 ....
