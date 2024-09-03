
fnames_by_dt = dict((dt_from_fname(fname), fname) for fname in os.listdir())

In [44]: dts = list(fnames_by_dt.keys())

In [45]: dts.sort()
---------------------------------------------------------------------------
TypeError                                 Traceback (most recent call last)
Cell In[45], line 1
----> 1 dts.sort()

TypeError: '<' not supported between instances of 'datetime.datetime' and 'NoneType'

In [46]: fnames_by_dt.pop(None)
Out[46]: 'c2c12_contrast.jpg'

In [47]: dts = list(fnames_by_dt.keys())

In [48]: dts.sort()

In [49]: for d in dts:
    ...:     if (d - dt_curr).seconds >= 60*15:
    ...:         print(fnames_by_dt[d])
    ...:         dt_curr = d
    ...: 


for f in $FILES; do cp $f subsample/$f; done;
rabryan@rabryan-x1:~/Documents/lucid/experiments/c2c12-imaging$ convert -delay 20 -loop 0 subsample/*.jpg my_new.gif
