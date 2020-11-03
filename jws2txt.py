#Jozef Tran

import sys
import olefile as ofio
from struct import unpack
import numpy as np
import glob, os


#from jwsprocessor
DATAINFO_FMT = '<LLLLLLdddLLLLdddd'
#from jwsprocessor

class DataInfo:
    def __init__(self, data):

        if len(data) < 96:
            raise Exception ("DataInfo should be at least 96 bytes!")

        data = data[:96]
        data_tuple = unpack(DATAINFO_FMT, data)
        self.npoints = data_tuple[5]
        self.x_for_first_point = data_tuple[6]
        self.x_for_last_point = data_tuple[7]
        self.x_increment = data_tuple[8]

def main(fn, output=None):

#defines variable ellipticity outside loop
    ellipticity =[]
#defines variable HT outside loop
    HT =[]
#defines variable abs outside loop
    Abs =[]
#defines variable xdata outside loop
    xdata =[]


    doc = ofio.OleFileIO(fn)
    #print doc.listdir()
    if doc.exists('DataInfo'):
        str = doc.openstream('DataInfo')
        data = str.read()
        DI = DataInfo(data)
    else:
        return
    if doc.exists('Y-Data'):
        #opens (Y-Data string(
        str = doc.openstream('Y-Data')
        data = str.read()
        try:
            fmt = 'f' * DI.npoints
            values = unpack(fmt, data)
            Abs = list(values)
        except:
            #cut data into slices to get Abs, HT and ellipticity,
            data_3 = data[int(2 * len(data) / 3):len(data)]
            data_2 = data[int(len(data)/3):int(2*len(data)/3)]
            data = data[:int(len(data)/3)]
            #generate  format character for struct
            fmt = 'f'*DI.npoints
            #get values for ellipticity in tuple form -- deciphers data string using struct
            values = unpack(fmt, data)
            # get values  for HT in tuple form
            values_2 = unpack(fmt, data_2)
            # get values  for Abs in tuple form
            values_3 = unpack(fmt, data_3)
            ellipticity=list(values)
            HT = list(values_2)
            Abs =list(values_3)



        #generate xdata
        x = DI.x_for_first_point
        x += DI.x_increment
        xdata = np.arange(DI.x_for_first_point,  # start
                              DI.x_for_last_point + DI.x_increment,  # end+incr.
                              DI.x_increment)  #

        if ellipticity:
            np.savetxt(jws_file+'.txt', np.c_[xdata, ellipticity, HT, Abs], header=" ellipticity HT absorbance")
        else:
            np.savetxt(jws_file+'.txt', np.c_[xdata, Abs], header=" absorbance")

    else:
        return


if __name__ == '__main__':
    if len(sys.argv) > 1:
        infn = sys.argv[1]
        outfn = sys.argv[2] if len(sys.argv) > 2 else None
        os.chdir(infn)

        matches = []
        for root, dirnames, filenames in os.walk(infn):
            for filename in filenames:
                if filename.endswith('.jws'):
                    matches.append(os.path.join(root, filename))

            for jws_file in matches:
                print(jws_file)
                main(jws_file)

    else:
        print ('USAGE:python jws2txt.py input_folder')
