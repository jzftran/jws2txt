#%%
import jws2txt
import matplotlib.pyplot as plt

test_file = jws2txt.JWSFile(r'sample_CD_HT_Abs.jws')


x, cd, ht, abs = test_file.unpacked_data


# %%

# %%
fig, ax = plt.subplots(3,1)
#%%
ax[0].plot(x, cd)
ax[1].plot(x, ht)
ax[2].plot(x, abs)
plt.show()
# %%

