#%%
from helpers.helpers import *

import importlib
importlib.reload(helpers.helpers)
import olefile as ofio

 
#need def of main
fn = r'C:\Users\makro\OneDrive\Pulpit\repos\jws2txt\temp\001Hg.jws'
file = ofio.OleFileIO(fn)

DI = DataInfo(file.openstream('DataInfo').read())

#%%
s = file.openstream('Y-Data')
channels_num=3
data = s.read()
fmt = 'f'*DI.npoints
chunk_size = int(len(data)/channels_num)
data_chunked = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
       # if __name__ == "__main__":
#     main()


#%%
DI.npoints
DI.x_for_first_point
DI.x_for_last_point
DI.x_increment

DI.list_data
# %%
from struct import unpack


mdata = file.get_metadata()

