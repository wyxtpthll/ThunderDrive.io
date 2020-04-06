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

search file "filename" and download to current directory:
 - thunderdrive.py --search filename --list

search file "filename" and download to current directory, stop before download:
 - thunderdrive.py --search --list --prompt

file ulpoad:
- thunderdrive.py --uploadfile file.txt --tdir ThunderDriveUploadDir
