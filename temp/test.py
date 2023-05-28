#%%
import jws2txt
import matplotlib.pyplot as plt

test_file = jws2txt.JWSFile(r'001Hg.jws')


x, cd, ht, abs = test_file.unpacked_data

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
test_file.unpacked_data[0][2]
test_file.unpacked_data[1][2]
test_file.unpacked_data[2][2]
test_file.unpacked_data[3][2]