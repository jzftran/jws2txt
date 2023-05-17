from struct import unpack


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

        self.list_data = data_tuple

        