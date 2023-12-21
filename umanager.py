from pycromanager import Core, JavaObject, Studio
import tifffile
import json
import time
import numpy as np
from igor import IgorZmq
import math
import cv2
from pathlib import Path
from scipy import ndimage
from stimset_builder import StimSequenceSet
import pickle
import datetime
import json

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

def load_stim_sequence_file(filename):
    with open(filename, 'rb') as file:
        stim_sequence_set = pickle.load(file)
        return stim_sequence_set

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

	def collect_dmd_params(self, stim_sequence_set, order_name='default', stim_amp=50, stim_duration=50, repeatCnt=1, isi=100):
		'''
		assembles parameters of dmd stimulation into one dictionary. Add fetching from GUI here(?)
		'''
		##shutter params
		##t1 - t3 and i1 - i3 correspond to time and amplitude of analog output for Mightex BLS device, time in us
		t1 = 10000 #t1 = 10 ms, lag shutter to ensure mirror movement 
		t2 = int(stim_duration * 1000) ##t2 convert stim duration to us
		t3 = int(isi * 1000 - (t1 + t2)) ##convert isi to us, subtract t1 and t2 so that time is start to start
		i1, i2, i3 = 0, stim_amp, 0
		
		##dmd sequence params
		sequence_name = stim_sequence_set.name
		order = stim_sequence_set.sequence_dict[order_name].tolist()
		
		##timing and alignment info
		now = str(datetime.datetime.now())
		next_sweep = [igor.get_next_sweep()]
		stim_id = self.stim_id
		
		param_list = [t1, t2, t3, i1, i2, i3, repeatCnt, 
		next_sweep, stim_id, sequence_name, order_name, order, now]
		
		param_name_list = ["t1", "t2", "t3", "i1", "i2", "i3", "repeatCnt", 
		"sweep", "stim_id", "sequence_name", "order_name", "order", "time_stim"]
		
		stim_dict = dict(zip(param_name_list, param_list))
		#stim_dict = {param_name_list[i]: param_list[i] for i in range(len(param_name_list))}
		return stim_dict

	def load_sequence(self, inv_image_seq):
		'''
		load image sequence (should be in DMD dimensions) to DMD, set trigger
		'''
		assert inv_image_seq.size() <=24, "image sequence too long, may cause unexpected DMD projection sequence"
		self.core.stop_slm_sequence(self.name)
		self.core.set_property(self.name, "TriggerType", "3")
		self.core.load_slm_sequence(self.name, inv_image_seq)
		self.core.wait_for_device(self.name)
		self.core.start_slm_sequence(self.name)

	def dmd_run(self, stim_sequence_set, order_name='default', stim_amp=50, stim_duration=50):
		##TODO collect and save reference image. Ask user to confirm scope hardware.
		##grab_image()

		image_seq = stim_sequence_set.get_ordered_seq_by_name(order_name)

		stim_dict = self.collect_dmd_params(stim_sequence_set, order_name, stim_amp, stim_duration)
		
		self.shutter.set_properties(stim_dict)
		
		igor.dmd_ephys_prep()
		self.core.stop_slm_sequence(self.name)  ##stop any ongoing sequence

		if image_seq.ndim == 2:  ##if one image
			inv_image = self.convert_image(image_seq)
			self.core.set_property(self.name, "TriggerType", "3")
			self.core.set_slm_image(self.name, inv_image)
			self.core.display_slm_image(self.name)
			DAQ_started = igor.start_DAQ()

	
		if image_seq.shape[2] > 24: ##bad DMD behavior when sequence >24. :<( work around
			n_images = image_seq.shape[2]
			split_sets = np.split(image_seq, np.arange(24, n_images, 24), axis = 2)
			sweep_list =[]
			for set_i in split_sets:
				ns = igor.get_next_sweep()
				sweep_list.append(ns)
				invert_set = self.convert_set(set_i)
				self.load_sequence(invert_set)
				self.shutter.set_open()
				DAQ_started = igor.start_DAQ()
				while igor.get_DAQ_status() != 0:
					time.sleep(0.5)
			stim_dict['sweep'] = sweep_list ##update sweep metadata to include all sweeps

		else:
			invert_set = self.convert_set(image_seq)
			self.load_sequence(invert_set)
			self.shutter.set_open()
			DAQ_started = igor.start_DAQ()

		update_photostim_log(stim_dict)
		self.stim_id += 1 ##iterate for next round
		
		
	def convert_image(self, image):
		'''
		convert image from camera space to DMD space
		'''
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

def save_photostim_params(stim_dict):
	filename = "photostim_log.json"
	stim_name = "photostim_"+str(stim_dict["stim_id"])
	main_dict = {stim_name:stim_dict}
	with open(filename, 'w') as f:
		f.write(json.dumps(main_dict, indent=4))
		f.close

def update_photostim_log(stim_dict):
	filename = "photostim_log.json"
	try:
		with open(filename, 'r+') as f:
			existing_dict = json.load(f)
			stim_name = "photostim_"+str(stim_dict["stim_id"])
			existing_dict[stim_name] = stim_dict
			f.seek(0)
			json.dump(existing_dict, f, indent = 4)
	except:
		print(f"{filename} not found")
		save_photostim_params(stim_dict)

