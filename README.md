# jws2txt

A program to convert binary JASCO SpectraManager (JWS and JWB) files to text files.

## Introduction
------------
jws2txt is a simple command line tool that allows for the conversion of JWS and JWB files from JASCO SpectraManager software to text files. These text files can be used in any data analysis workflows and software.

Unlike JASCO SpectraManager software, jws2txt enables batch conversion of JWS/JWB files.

Data unpacking is based on Víctor M. Hernández-Rocamora's jwsProcessor (https://github.com/vhernandez/jwsProcessor).

## Installation and Usage
------------
1. Download Python.
2. Run the `pip install jws2txt` command in the command line.
3. To convert the files, run the `jws2txt --in-path path_to_folder --out-dir output_folder_path` command, where path_to_folder is the folder containing the JWS or JWB files.
4. The converted files will be located in the folder containing the source JWS or JWB files.