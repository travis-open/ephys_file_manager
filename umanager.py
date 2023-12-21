from pycromanager import Core, JavaObject, Studio
import tifffile
import json
import time
import numpy as np
from igor import IgorZmq
import math
import cv2
from matplotlib import pyplot as plt
from pathlib import Path
from scipy import ndimage
from stimset_builder import StimPatternSet
import pickle

core = Core()
igor = IgorZmq()
studio = Studio()

images_1d = JavaObject('java.util.ArrayList')

def split_with_numpy(numbers, chunk_size):
	indices = np.arange(chunk_size, len(numbers), chunk_size)
	return np.array_split(numbers, indices)


def grab_image(dir_path):
	##can't snap if live mode is on. Check current mode, stop, snap, process, save, reset mode
	live_mode = studio.live().get_is_live_mode_on()
	studio.live().set_live_mode(False)
	core.snap_image()
	tagged_image = core.get_tagged_image()
	image_height = tagged_image.tags['Height']
	image_width = tagged_image.tags['Width']
	image = tagged_image.pix.reshape((image_height, image_width))
	md = tagged_image.tags
	filename = "img_"+str(int(time.time()))
	tfile = filename+'.tif'
	jsonfile = filename+'.json'
	dir_path = Path(dir_path)
	tifffile.imwrite(dir_path/tfile, image)
	with open(dir_path/jsonfile, 'a') as f:
		f.write(json.dumps(md, indent=4))
		f.close()
	studio.live().set_live_mode(live_mode)

def load_stim_pat_file(filename):
    with open(filename, 'rb') as file:
        stim_pat = pickle.load(file)
        return stim_pat

class Shutter():
	def __init__(self, core):
		self.core = core
		self.name = self.core.get_shutter_device()

	def set_prop(self, prop, value):
		self.core.set_property(self.name, prop, value)

	def set_properties(self, stim_dict):
		shutter_list = ["t1", "t2", "t3", "i1", "i2", "i3", "repeatCnt"]
		## channel and mode should always be 1 and TRIGGER barring major hardware change...
		self.set_prop("channel", 1)
		self.set_prop("mode", "TRIGGER")
		for k, v in stim_dict.items():
			if k in shutter_list:
				self.set_prop(k, v)
				self.core.wait_for_device(self.name)		
		self.core.set_shutter_open(True) ##required for changes to take effect and BLS device to be responsive

	def set_open(self):
		self.core.set_shutter_open(self.name, True)

class DMD():

	def __init__(self, core):
		self.core = core
		self.name = self.core.get_slm_device()
		self.h = self.core.get_slm_height(self.name)
		self.w = self.core.get_slm_width(self.name)
		self.shape = (self.h,self.w)

		
		self.shutter = Shutter(core)
		self.stim_id = 0
		self.homography_inverse = np.array([[ 6.53313277e-01, -7.48067857e-03,  1.09582335e+01],
       [ 1.63915770e-02,  1.32567470e+00, -1.68140354e+02],
       [ 1.68963875e-05, -2.47554547e-06,  1.00057329e+00]])

	def collect_dmd_params(self, image_seq, stim_amp=50, stim_duration=50000, repeatCnt=1, t3=50000, sequence_name="unknown"):
		'''
		assembles parameters of dmd stimulation into one dictionary. Add fetching from GUI here(?)
		'''
		##t1 - t3 and i1 - i3 correspond to time and amplitude of analog output for Mightex BLS device
		t1, t2, t3 = 10000, stim_duration, t3 #t1 = 10 ms, lag shutter to ensure mirror movement 
		##i2 and t2 correspond to stimulus pulse
		##t3 use in trains, only relevant when repeatCnt > 1
		i1, i2, i3 = 0, stim_amp, 0
		next_sweep = [igor.get_next_sweep()]
		param_list = [t1, t2, t3, i1, i2, i3, repeatCnt, next_sweep, self.stim_id, sequence_name]
		param_name_list = ["t1", "t2", "t3", "i1", "i2", "i3", "repeatCnt", "sweep", "stim_id", "sequence_name"]
		stim_dict = {param_name_list[i]: param_list[i] for i in range(len(param_name_list))}
		return stim_dict

	def load_sequence(self, inv_image_seq):
		assert inv_image_seq.size() <=24, "image sequence too long, may cause unexpected DMD projection sequence"
		self.core.stop_slm_sequence(self.name)
		self.core.set_property(self.name, "TriggerType", "3")
		self.core.load_slm_sequence(self.name, inv_image_seq)
		self.core.wait_for_device(self.name)
		self.core.start_slm_sequence(self.name)

	def dmd_prep(self, image_seq, stim_amp=50, stim_duration=50000):
		##TODO collect and save reference image. Ask user to confirm scope hardware.
		##grab_image()
		stim_dict = self.collect_dmd_params(image_seq, stim_amp, stim_duration)
		self.stim_id += 1 ##iterate for next round
		self.shutter.set_properties(stim_dict)
		
		igor.dmd_ephys_prep()
		self.core.stop_slm_sequence(self.name)

		if image_seq.ndim == 2:
			inv_image = self.convert_image(image_seq)
			self.core.set_property(self.name, "TriggerType", "3")
			self.core.set_slm_image(self.name, inv_image)
			self.core.display_slm_image(self.name)

	
		if image_seq.shape[2] > 24: ##bad DMD behavior when sequence >24. :<( work around
			n_images = image_seq.shape[2]
			split_sets = np.split(image_seq, np.arange(24, n_images, 24), axis = 2)
			for set_i in split_sets:
				ns = igor.get_next_sweep()
				invert_set = self.convert_set(set_i)
				self.load_sequence(invert_set)
				self.shutter.set_open()
				DAQ_started = igor.start_DAQ()
				while igor.get_DAQ_status() != 0:
					time.sleep(0.5)

		else:
			invert_set = self.convert_set(image_seq)
			self.load_sequence(invert_set)
			self.shutter.set_open()
		
	def convert_image(self, image):
		inv_image = cv2.warpPerspective(image, self.homography_inverse, self.shape[::-1])
		return inv_image

	def convert_set(self, dmd_stims):
		'''
		input 3d numpy array of x, y, stim_number, convert to dmd coordinates, make Java object,
		load sequence to DMD
		'''
		n_stims = dmd_stims.shape[2]
		images_1d = JavaObject('java.util.ArrayList')
		for i in range(n_stims):
			image = dmd_stims[:,:,i]
			inv_image = self.convert_image(image)
			images_1d.add(inv_image.ravel())
		return images_1d


