import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from multipletau import autocorrelate

file_name = "data-2018-06-12 15:42:26.npy"
data = np.load(file_name)


print(len(data))

plt.figure(1)
plt.plot(data)
"""
plt.figure(2)
plt.plot(data[1:]-data[:-1])
plt.figure()
occ,val,dummy=plt.hist(data,256,(0,256),log=True)
"""
G = autocorrelate(data[1:]-data[:-1], normalize=True, dtype=np.float_)
plt.figure()
plt.semilogx(G[5:,0], G[5:,1])
plt.show()

