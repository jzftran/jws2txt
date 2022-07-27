import sys
import olefile as ofio
from struct import unpack
import numpy as np
import os

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

def main(fn, channels_num, output=None):

    doc = ofio.OleFileIO(fn)

    if doc.exists('Y-Data'):
        DI = DataInfo(doc.openstream('DataInfo').read())
        str = doc.openstream('Y-Data')
        data = str.read()
        fmt = 'f'*DI.npoints
        chunk_size = int(len(data)/channels_num)
        data_chunked = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
        try:
            unpacked_data = [unpack(fmt, data_chunk) for data_chunk in data_chunked]
            #generate xdata
            x = DI.x_for_first_point
            x += DI.x_increment
            xdata = np.arange(DI.x_for_first_point,  # start
                                DI.x_for_last_point + DI.x_increment,  # end+incr.
                                DI.x_increment)  #

            unpacked_data.insert(0, xdata)

            np.savetxt(jws_file+'.txt', np.c_[unpacked_data].transpose())
        except:
            print("Incorrect number of channels.")
    else:
        return


if __name__ == '__main__':
    if len(sys.argv) > 1:
        try:
            channels_num = int(input("Enter the number of channels:"))
        except:
            print('Enter the proper number of channels.')
            sys.exit(1)


        infn = sys.argv[1]
        outfn = sys.argv[2] if len(sys.argv) > 2 else None
        os.chdir(infn)
        matches = []
        for root, dirnames, filenames in os.walk(infn):
            for filename in filenames:
                if filename.endswith(('.jwb','.jws')):
                    matches.append(os.path.join(root, filename))

        for jws_file in matches:
            print(jws_file)
            main(jws_file, channels_num)

    else:
        print ('USAGE:python jws2txt.py input_folder')
