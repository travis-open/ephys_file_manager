from pycromanager import Core, JavaObject, Studio
import tifffile
import json
import time
import numpy as np
from igor import IgorZmq
import math
import cv2
from matplotlib import pyplot as plt

core = Core()
igor = IgorZmq()
studio = Studio()

images_1d = JavaObject('java.util.ArrayList')

def split_with_numpy(numbers, chunk_size):
	indices = np.arange(chunk_size, len(numbers), chunk_size)
	return np.array_split(numbers, indices)

class DMD():

	def __init__(self, core)
		self.core = core
		self.dmd_name = self.core.get_slm_device()
		self.h = self.core.get_slm_height(self.dmd_name)
		self.w = self.core.get_slm_width(self.dmd_name)
		self.dmd_shape = (self.h,self.w)
		self.sd = self.core.get_shutter_device() ##shutter used for other things in future? inherit from elsewhere?
		self.stim_id=0
		self.homography_inverse = np.array([[ 6.53313277e-01, -7.48067857e-03,  1.09582335e+01],
       [ 1.63915770e-02,  1.32567470e+00, -1.68140354e+02],
       [ 1.68963875e-05, -2.47554547e-06,  1.00057329e+00]])

	def collect_dmd_params(image_seq, stim_amp=50, stim_duration=50000, repeatCnt=1, t3=50000):
		'''
		assembles parameters of dmd stimulation into one dictionary. Add fetching from GUI here(?)
		'''
		##t1 - t3 and i1 - i3 correspond to time and amplitude of analog output for Mightex BLS device
		t1, t2, t3 = 1000, stim_duration, t3 #t1 = 1000 us, lag shutter to ensure mirror movement 
		##i2 and t2 correspond to stimulus pulse
		##t3 use in trains, only relevant when repeatCnt > 1
		i1, i2, i3 = 0, stim_amp, 0
		next_sweep = igor.get_next_sweep()
		param_list = [t1, t2, t3, i1, i2, i3, repeatCnt, next_sweep, self.stim_id]
		param_name_list = ["t1", "t2", "t3", "i1", "i2", "i3", "repeatCnt", "sweep", "stim_id"]
		stim_dict = {param_name_list[i]: param_list[i] for i in range(len(param_name_list))}
		return stim_dict

	def set_shutter_properties(stim_dict, core):
		shutter_list=["t1", "t2", "t3", "i1", "i2", "i3", "repeatCnt"]
		## channel and mode should always be 1 and TRIGGER barring major hardware change...
		self.core.set_property(sd, "channel", 1)
		self.core.set_property(sd, "mode", "TRIGGER")
		for k, v in stim_dict.items():
			if k in shutter_list:
				self.core.set_property(sd, k, v)
				self.core.wait_for_device(sd)		
		self.core.set_shutter_open(True) ##required for changes to take effect and BLS device to be responsive

	def dmd_prep(image_seq, stim_amp=50, stim_duration=50000):
		##TODO collect and save reference image. Ask user to confirm scope hardware.
		stim_dict = collect_dmd_params(image_seq, stim_amp, stim_duration)
		self.stim_id+=1 ##iterate for next round
		set_shutter_properties(stim_dict)
		
		igor.dmd_ephys_prep()
		self.core.stop_slm_sequence(dmd_name)

		if image_seq.ndim == 2:
			image_inv = self.convert_image(image_seq)
			self.core.set_slm_image(dmd_name, image_inv)
			self.core.display_slm_image(dmd_name)

	
		if image_seq.shape[2] > 24: ##bad DMD behavior when sequence >24. :<( work around
			split_sets = np.split(image_seq, np.arange(24, 60, 24), axis = 2)
			for set_i in split_sets:
				self.invert_set = convert_set(set_i)
				self.core.load_slm_sequence(dmd_name, invert_set)
				self.core.start_slm_sequence(dmd_name)
				self.core.set_shutter_open(sd, True)

		else:
			self.invert_set = convert_set(image_seq)
			self.core.load_slm_sequence(dmd_name, invert_set)
			self.core.start_slm_sequence(dmd_name)
			self.core.set_shutter_open(sd,True)
		
	def convert_image(image):
		image_inv = cv2.warpPerspective(image, self.homography_inverse, self.dmd_shape[::-1])
		return image_inv

	def convert_set(dmd_stims):
	'''input 3d numpy array of x, y, stim_number, convert to dmd coordinates, make Java object,
	load sequence to DMD'''
		n_stims=dmd_stims.shape[2]
		images_1d = JavaObject('java.util.ArrayList')
		for i in range(n_stims):
			image = dmd_stims[:,:,i]
			image_inv = self.convert_image(image)
			images_1d.add(image_inv.ravel())
		return images_1d

def draw_rect(n_cols, n_rows, i_col, i_row, img_w=1024, img_h=1024):
	'''
	Draws a single rectangle at column and row indexes.
	Intended to be used in camera coordinates, then translated to DMD.
	'''
    ##margins correspond to region of camera image covered by DMD. Only relevant for 1024x1024.
    ##maybe require 1024x1024 image until better solution determined
    left_margin = 20 
    right_margin =120 
    upper_margin =120 
    lower_margin = 397
    sub_w = img_w - left_margin - right_margin
    sub_h = img_h - upper_margin - lower_margin
    rect_width = math.floor(sub_w/n_cols) - 1
    rect_height = math.floor(sub_h/n_rows) - 1
    x0 = left_margin + i_col*rect_width
    y0 = upper_margin + i_row*rect_height
    stim = cv2.rectangle(
    img = np.zeros((img_w, img_h), dtype = np.uint8),
    rec = (x0, y0, rect_width, rect_height),
    color = 255, 
    thickness = -1)
    ##plt.imshow(stim)
    return stim

def draw_all_grid_rects(img_w, img_h, n_cols, n_rows):
	'''
	Creates 3d numpy array of all possible grid locations
	'''
	n_stims = n_cols * n_rows
	grid_stims = np.zeros((img_w, img_h, n_stims), dtype=np.uint8)
	grid_i=0
	for nc in np.arange(n_cols):
		for nr in np.arange(n_rows):
			stim = draw_rect(img_w, img_h, n_cols, n_rows, nc, nr)
			grid_stims[:,:,grid_i] = stim
			grid_i += 1
	return grid_stims





