# jws2txt
JASCO file to text file converter

jws2txt converts JASCO spectrophotometer *.jws files to *.txt files.


Introduction
------------
jws2txt is a simple command line tool allowing conversion
JWS and JWB files from Jasco SpectraManager software. jws2txt converts JWS and JWB files to
text files that can be used in any data analysis workflows and software.

Contrary to Jasco SpectraManager software jws2txt allows for batch conversion
of JWS/JWB files.

Data unpack is based on Víctor M. Hernández-Rocamora's jwsProcessor
(https://github.com/vhernandez/jwsProcessor).

Installation and usage
------------
1. Download python, preferentially in Anaconda distribution.
2. Download this repository, unzip it.
3. Run the 'pip install -r requirements.txt' command in the command line.
4. To convert the files run the 'python jws2txt.py path_to_folder' command, where path_to_folder
is a folder containing JWS or JWB files.
5. Input the number of channels the files have.
6. Converted files will be in the folder containing source JWS or JWB files
