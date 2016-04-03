# FbxSimpleUploader

Script for uploading files to a Freebox based on fbxosctrl script from Christophe Lherieau (aka Skimpax)

Write in Python 2.7.  
Tested on Debian and Windows.

### How to use

1. **Register application to your freebox**
    1. Type `python fbxsimpleuploader.py --regapp`
    2. Complete registration by choosing 'Yes' on Freebox server's screen.
    3. *(Optional)* Configure rights access on Freebox web interface.
2. **Upload files**
    1. Upload all **testfiles** with any extensions in the current folder to Freebox root folder (aka **/Disque 1**)  
For example : `python fbxsimpleuploader.py --uploadfile testfiles.*`  

With `-d` option, each filenames will be completed with a date & time extension.  
For example : `python fbxsimpleuploader.py -d --uploadfile testfiles.*`  

Type `python fbxsimpleuploader.py -h` for more information.  

### Dependencies
- python-requests
- python-simplejson

### Freebox SDK documentation
http://dev.freebox.fr/sdk/os/
