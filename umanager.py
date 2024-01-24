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

def snap_image():
	'''snap image and return 2d numpy array and metadata (image tags)'''

	##can't snap if live mode is on. Check current mode, stop, snap, process, save, reset mode
	live_mode = studio.live().get_is_live_mode_on()
	studio.live().set_live_mode(False)
	core.snap_image()
	tagged_image = core.get_tagged_image()
	image_height = tagged_image.tags['Height']
	image_width = tagged_image.tags['Width']
	image = tagged_image.pix.reshape((image_height, image_width))
	md = tagged_image.tags
	studio.live().set_live_mode(live_mode) #reset live mode
	return image, md

def snap_save_image(dir_path):
	'''
	Snap micro-manager image with all current settings. Save as tiff and save json with associated metadata.
	Returns the name of the tiff file.
	'''
	##can't snap if live mode is on. Check current mode, stop, snap, process, save, reset mode
	image, md = snap_image()
	filename = "img_"+str(int(time.time()))
	tfile = filename+'.tif'
	jsonfile = filename+'.json'
	dir_path = Path(dir_path)
	tifffile.imwrite(dir_path/tfile, image)
	with open(dir_path/jsonfile, 'a') as f:
		f.write(json.dumps(md, indent=4))
		f.close()
	return dir_path/tfile

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
		self.homography_inverse = np.array([[-6.54221369e-01,  2.80235275e-03,  6.32726262e+02],
       [-1.00271597e-02, -1.33515581e+00,  9.19894155e+02],
       [-1.49952232e-05, -7.57511198e-06,  1.01971023e+00]])
		self.current_stim_sequence = None
		self.current_ss_order = None
		self.current_stim_dict = None
		self.sequence_loaded = False

	def update_stim_sequence(self, filename):
		stim_sequence_set = load_stim_sequence_file(filename)
		self.current_stim_sequence = stim_sequence_set

	def update_stim_dict(self, stim_dict):
		self.current_stim_dict = stim_dict

	def collect_dmd_params(self, stim_sequence_set, order_name='default', stim_amp=50, stim_duration=50, repeatCnt=1, isi=100, seq_int=100):
		'''
		assembles parameters of dmd stimulation into one dictionary. 
		'''
		##shutter params
		##t1 - t3 and i1 - i3 correspond to time and amplitude of analog output for Mightex BLS device, time in us
		t1 = 10000 #t1 = 10 ms, lag shutter to ensure mirror movement 
		t2 = int(stim_duration * 1000) ##t2 convert stim duration to us
		if repeatCnt == 1:
			t3 = 0
		else:
			t3 = int(isi * 1000 - (t1 + t2)) ##convert isi to us, subtract t1 and t2 so that time is start to start
		i1, i2, i3 = 0, stim_amp, 0
		
		##dmd sequence params
		sequence_name = stim_sequence_set.name
		if self.current_ss_order.any():
			order = self.current_ss_order.tolist()
		else:
			order = stim_sequence_set.sequence_dict[order_name].tolist()
		
		##timing and alignment info
		now = str(datetime.datetime.now())
		next_sweep = [igor.get_next_sweep()]
		mies_name = igor.get_mies_name()
		stim_id = self.stim_id
		
		param_list = [t1, t2, t3, i1, i2, i3, repeatCnt, seq_int,
		next_sweep, stim_id, sequence_name, order_name, order, now, mies_name]
		
		param_name_list = ["t1", "t2", "t3", "i1", "i2", "i3", "repeatCnt", "sequence_interval",
		"sweep", "stim_id", "sequence_name", "order_name", "order", "time_stim", "mies_name"]
		
		stim_dict = dict(zip(param_name_list, param_list))
		return stim_dict


	def prep_and_load(self, order, target_n=120):
		'''
		Prepare an ordered sequence of images by expanding to match target_n (if needed), convert to DMD pixel space, and load to DMD.
		'''
		image_seq = self.current_stim_sequence.get_ordered_seq(order)
		if len(order) < target_n:
			expanded_set, order = self.pad_sequence(image_seq, order, target_n, with_reps=True)
			inv_image_seq = self.convert_set(expanded_set)
		else:
			inv_image_seq = self.convert_set(image_seq)

		if self.current_stim_dict:
			self.current_stim_dict['order'] = order.tolist()
		self.load_sequence_to_dmd(inv_image_seq)
		self.current_ss_order = order

	def load_sequence_to_dmd(self, inv_image_seq):
		'''
		load image sequence (should be in DMD dimensions) to DMD, set trigger
		'''
		self.core.stop_slm_sequence(self.name)
		self.core.set_property(self.name, "TriggerType", "2")
		self.core.load_slm_sequence(self.name, inv_image_seq)
		self.core.wait_for_device(self.name)
		self.core.start_slm_sequence(self.name)
		self.sequence_loaded = True

	def run_current_sequence(self, stim_dict, sweep_reps=1, start_mies=False):
		'''
		Run the image sequence currently loaded to the DMD with the shutter params specificied in stim_dict.
		'''
		self.core.stop_slm_sequence(self.name) ##stop and restart ongoing sequence so that first frame is as expected
		self.core.start_slm_sequence(self.name)
		self.shutter.set_properties(stim_dict)
		next_sweep = igor.get_next_sweep()
		next_sweep_list = list(range(next_sweep, next_sweep+sweep_reps))
		stim_dict['sweep'] = next_sweep_list
		order = self.current_ss_order
		seq_int = stim_dict['sequence_interval']
		n_images = len(order)
		if n_images == 1:
			igor.dmd_frame_ephys_prep(stimset_name=stim_dict['sequence_name'], 
			order=order, order_name=stim_dict['order_name'], sweep_reps=sweep_reps)
		else:
			igor.dmd_sequence_ephys_prep(stimset_name=stim_dict['sequence_name'], 
			order=order, order_name=stim_dict['order_name'], sweep_reps=sweep_reps, n_images=n_images, seq_int=seq_int)
		update_photostim_log(stim_dict)
		if start_mies:
			igor.start_DAQ()
		self.stim_id += 1

	def run_current_img(self, stim_dict, start_mies=False):
		'''
		Run the image currently loaded to the DMD with shutter params specified in stim_dict.
		'''
		order = np.array(stim_dict['order'])
		assert len(order) == 1, f"length of order is {len(order)}. Expected length==1"
		self.shutter.set_properties(stim_dict)
		next_sweep = [igor.get_next_sweep()]
		igor.dmd_frame_ephys_prep(stimset_name=stim_dict['sequence_name'], 
			order=order, order_name=stim_dict['order_name'])
		update_photostim_log(stim_dict)
		if start_mies:
			igor.start_DAQ()
		self.stim_id += 1

		
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

	def set_image(self, image):
		assert image.shape == self.shape, f"dimensions of image {image.shape} and dmd {self.shape} do not match"
		self.core.set_slm_image(self.name, image)

	def all_pixels_on(self):
		image = np.ones((1024, 1024), dtype=np.uint8) * 255
		inv_image = self.convert_image(image)
		self.set_image(inv_image)

	def stop_sequence(self):
		self.core.stop_slm_sequence(self.name)

	def _point_img(self, xy):

		return cv2.circle(
            img = np.zeros(self.shape, dtype=np.uint8),
            center = xy,
            radius = 3,
            color=255,
            thickness=cv2.FILLED
            )

	def point_images(self, margin=50, points_x=7, points_y=5):
		"""
		Get list of arrayed points images, for calibration

		Parameters
		----------
		margin : int, optional
			Minimum XY values. The default is 50.
		points_x : int, optional
			Number of points to show along X. The default is 7.
		points_y : int, optional
			Number of points along Y. The default is 5.

		Returns
		-------
		images : list of 2D arrays of uint8
			The images to shine onto the sample for calibration.
		fixed_points : list of tuples
			The center of the dots in each image.

		"""
        
		grid_x = np.linspace(margin,self.shape[0]-margin,points_x).astype(int)
		grid_y = np.linspace(margin,self.shape[1]-margin,points_y).astype(int)

		fixed_points = []
		images = []
        
		for x in grid_x:
			for y in grid_y:
				fixed_points.append((x,y))
				images.append(self._point_img((x,y)))
		
		return images, fixed_points


	def _find_point(self, img, threshold):
		"""
		Find center of dot in acquired image

		Parameters
		----------
		img : 2D array of uint16
			Acquired snap of single-dot image as projected by DMD.
		threshold : int
			Value to threshold image to identify dot.

		Returns
		-------
		Tuple[Int, Int]
		Coordinates of the center of the dots.

		"""
        
		# Find point blob(s):
		contours, _ = cv2.findContours(
			(img>=threshold).astype(np.uint8),
			cv2.RETR_EXTERNAL, 
			cv2.CHAIN_APPROX_NONE
			)
		 
		# If no blob detected, return None:
		if len(contours)==0:
			return None
        
		# In unlikely event that more than 1 blob is detected, keep biggest:
		elif len(contours)>1:
			areas = [cv2.contourArea(cnt) for cnt in contours]
			contours = [contours[areas.index(max(areas))]]
        
		return centroid(contours[0])


def centroid(contour, im_height=1024):
	'''
	Get centroid of cv2 contour

	Parameters
	----------
	contour : 3D numpy array
		Blob contour generated by cv2.findContours().
	im_height : int, optional
		Height of the original image, in pixels. The default is 2048.

	Returns
	-------
	cx : int
		X-axis coordinate of centroid.
	cy : int
		Y-axis coordinate of centroid.

	'''
    
	if contour.shape[0]>2: # Looks like cv2.moments treats it as an image
		# Calculate moments for each contour
		M = cv2.moments(contour)
		# Calculate x,y coordinate of center
		if M["m00"] != 0:
			cx = int(M["m10"] / M["m00"])
			cy = int(M["m01"] / M["m00"])
		else:
			cx, cy = 0, 0
	else:
		cx = int(np.mean(contour[:,:,0]))
		cy = int(np.mean(contour[:,:,1]))
        
	# cy = im_height-cy
    
	return cx,cy


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







