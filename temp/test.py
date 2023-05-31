#%%
import jws2txt
import matplotlib.pyplot as plt
from io import StringIO
test_file = jws2txt.JWSFile(r'001Hg.jws')




x, cd, ht, abs = test_file.unpacked_data

outfile = StringIO()
test_file.write_data(outfile)
outfile.seek(0)
content = outfile.read()
print(content)


#%%
# %%

# %%
fig, ax = plt.subplots(3,1)
#%%
ax[0].plot(x, cd)
ax[1].plot(x, ht)
ax[2].plot(x, abs)
plt.show()
# %%


test_file.decode_sample_info()
# %%
test_file = jws2txt.JWSFile(r'../tests/files/sample_fluorescence.jws')
test_file = jws2txt.JWSFile(r'../tests/files/2022_05_14-1.jwb')


# %%


from jws2txt.helpers.helpers import frange


tuple(frange(2, 0.9, -0.1))
# %%
