from pycromanager import Core, JavaObject
import tifffile
import json
import time
import numpy as np
from igor import IgorZmq

core = Core()
igor = IgorZmq()

images_1d = JavaObject('java.util.ArrayList')

rng = np.random.default_rng()
dmd_name = core.get_slm_device()
h = core.get_slm_height(dmd_name)
w = core.get_slm_width(dmd_name)
dmd_shape = (h,w)
sd = core.get_shutter_device()

for _ in range(20):
    img = rng.random((h,w))>0.9
    img = img.astype(np.uint8)*255
    images_1d.add(img.ravel())

stim_id=0

def dmd_prep(image_seq, stim_amp=50, stim_duration=50000):
	t1, t2, t3 = 1000, stim_duration, 0 #t1 = 1000 us, time for shutter to wait after recieving trigger 
	##t3 use in future for trains
	i1, i2, i3 = 0, stim_amp, 0
	next_sweep = igor.get_next_sweep()
	stim_id=0
	param_list = [t1, t2, t3, i1, i2, i3, next_sweep, stim_id]
	shutter_list=["t1", "t2", "t3", "i1", "i2", "i3"]
	param_name_list = ["t1", "t2", "t3", "i1", "i2", "i3", "sweep", "stim_id"]
	stim_dict = {param_name_list[i]: param_list[i] for i in range(len(param_name_list))}
	for k, v in stim_dict.items():
		if k in shutter_list:
			core.set_property(sd, k, v)

	igor.dmd_ephys_prep()
	
	core.stop_slm_sequence(dmd_name)
	core.set_property(sd, "channel", 1)
	core.set_property(sd, "mode", "TRIGGER")
	core.set_property(dmd_name,"CommandTrigger",0)
	core.set_property(dmd_name,"TriggerType",3)
	core.load_slm_sequence(dmd_name, images_1d)
	core.start_slm_sequence(dmd_name)
	core.set_shutter_open(sd,True)
	stim_id+=1

