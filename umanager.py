"""
Code for controlling Polygon 400 DMD largely based on: https://gitlab.com/dunloplab/pycromanager/-/blob/master/pycromanager_tessie/microscope/dmd.py?ref_type=heads
Thank you to Jean-Baptiste Lugagne and other contributors.
"""


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


def grab_image(dir_path):
	'''
	Snap micro-manager image with all current settings. Save as tiff and save json with associated metadata.
	Returns the name of the tiff file.
	'''
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
	return tfile

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
		##todo save homography_inverse to config or other external file
		self.homography_inverse = np.array([[ 6.53313277e-01, -7.48067857e-03,  1.09582335e+01],
       [ 1.63915770e-02,  1.32567470e+00, -1.68140354e+02],
       [ 1.68963875e-05, -2.47554547e-06,  1.00057329e+00]])
		self.current_stim_sequence = None
		self.current_stim_dict = None

	def update_stim_sequence(self, filename):
		stim_sequence_set = load_stim_sequence_file(filename)
		self.current_stim_sequence = stim_sequence_set

	def update_stim_dict(self, stim_dict):
		self.current_stim_dict = stim_dict

	def collect_dmd_params(self, stim_sequence_set, order_name='default', stim_amp=50, stim_duration=50, repeatCnt=1, isi=100):
		'''
		assembles parameters of dmd stimulation into one dictionary. 
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
		return stim_dict


	def prep_and_load(self, order, target_n=120):
		image_seq = self.current_stim_sequence.get_ordered_seq(order)
		expanded_set, expanded_order = self.pad_sequence(image_seq, order, target_n, with_reps=True)
		if self.current_stim_dict:
			self.current_stim_dict['order'] = expanded_order.tolist()
		inv_image_seq = self.convert_set(expanded_set)
		self.load_sequence_to_dmd(inv_image_seq)

	def load_sequence_to_dmd(self, inv_image_seq):
		'''
		load image sequence (should be in DMD dimensions) to DMD, set trigger
		'''
		self.core.stop_slm_sequence(self.name)
		self.core.set_property(self.name, "TriggerType", "2")
		self.core.load_slm_sequence(self.name, inv_image_seq)
		self.core.wait_for_device(self.name)
		self.core.start_slm_sequence(self.name)

	def run_current_sequence(self, stim_dict, start_mies=False):
		self.core.stop_slm_sequence(self.name) ##stop and restart ongoing sequence so that first frame is as expected
		self.core.start_slm_sequence(self.name)
		self.shutter.set_properties(stim_dict)
		next_sweep = [igor.get_next_sweep()]
		order = np.array(stim_dict['order'])
		igor.dmd_ephys_prep(stimset_name=stim_dict['sequence_name'], 
			order=order, order_name=stim_dict['order_name'])
		update_photostim_log(stim_dict)
		if start_mies:
			igor.start_DAQ()
		self.stim_id += 1

	def load_run(self, stim_sequence_set, order_name='default', stim_amp=50, stim_duration=50):
		##TODO collect and save reference image. Ask user to confirm scope hardware.
		##grab_image()

		##create sequence of images in desired order
		image_seq = stim_sequence_set.get_ordered_seq_by_name(order_name)
		n_images = stim_sequence_set.n_patterns
		order = stim_sequence_set.get_order_by_name(order_name)
		stim_dict = self.collect_dmd_params(stim_sequence_set, order_name,
		 stim_amp, stim_duration)
		
		self.shutter.set_properties(stim_dict)
		self.core.stop_slm_sequence(self.name)  ##stop any ongoing sequence

		if n_images==1:  ##if one image
			inv_image = self.convert_image(image_seq)
			self.core.set_property(self.name, "TriggerType", "2")
			self.core.set_slm_image(self.name, inv_image)
			self.core.display_slm_image(self.name)
			DAQ_started = igor.start_DAQ()

		elif n_images < 70: ##bad DMD behavior when sequence between 24 and 70 frames. :<( work around
			expanded_set, expanded_order = self.pad_sequence(image_seq, order, target_n=120, with_reps=True)
			stim_dict['order'] = expanded_order.tolist()
			igor.dmd_ephys_prep(stimset_name=stim_sequence_set.name, order=expanded_order, order_name=order_name)
			invert_set = self.convert_set(expanded_set)
			self.load_sequence_to_dmd(invert_set)
			self.shutter.set_open()
			DAQ_started = igor.start_DAQ()
			
		else:
			invert_set = self.convert_set(image_seq)
			self.load_sequence_to_dmd(invert_set)
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

	

	def pad_sequence(self, image_seq, order, target_n=120, with_reps=True):
		'''
		Increase length of photostim image_seq to match target_n. 
		Primarily used to match sequence length to number of ephys triggers.
		Padded with repeats of image_seq and/or blank stimuli.
		'''
		n_images = len(order)
		expanded_image_seq = np.zeros((image_seq.shape[0], image_seq.shape[1], target_n), dtype=np.uint8)
		if with_reps:
			reps = math.floor(target_n/n_images)	
		else:
			reps = 1
		expanded_order = np.zeros(reps*n_images, dtype=np.uint)
		for i in range(reps):
			start_i = i * n_images
			stop_i = (i+1) * n_images
			expanded_image_seq[:, :, start_i:stop_i] = image_seq
			expanded_order[start_i:stop_i] = order
		return expanded_image_seq, expanded_order


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

def find_StimSequences(directory = 'C:/stimset_building/'):
	files = [x.stem for x in Path(directory).glob('*pickle') if x.is_file()]
	return files







