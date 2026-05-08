"""
Code for controlling and calibrating Polygon 400 DMD largely based on: https://gitlab.com/dunloplab/pycromanager/-/blob/master/pycromanager_tessie/microscope/dmd.py?ref_type=heads
With some mods for hardware and application differences. Thank you to Jean-Baptiste Lugagne and other contributors.
"""


from pycromanager import Core, JavaObject, Studio
import tifffile
import json
import time
import numpy as np
import math
import cv2
from pathlib import Path
from scipy import ndimage
from stimset_builder import StimSequenceSet
import pickle
import datetime
from file_manager import get_next_abf
import tkinter as tk
from tkinter import messagebox


core = None
studio = None


def connect_micromanager():
    """Attempt to connect to a running Micro-Manager instance.

    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    global core, studio
    try:
        core = Core()
        studio = Studio()
        return True, None
    except Exception as e:
        core = None
        studio = None
        return False, str(e)


# Attempt connection at import time; failure is non-fatal
connect_micromanager()

def pop_warning(warning):
	# Initialize a hidden root window
	root = tk.Tk()
	root.withdraw()

	# Create the warning popup
	messagebox.showwarning("Warning Title", warning)

	# Cleanup
	root.destroy()


def pulse_train_info(num_pulses: int, pulse_width_ms: float, period_ms: float) -> dict:
    """
    Calculate the total duration and frequency of a pulse train.

    Args:
        num_pulses: Number of pulses in the train
        pulse_width_ms: Width of each pulse in milliseconds
        period_ms: Time between pulse onsets (inter-pulse period) in milliseconds

    Returns:
        Dictionary with total_duration_ms and frequency_hz
    """
    if num_pulses < 1:
        raise ValueError("Number of pulses must be at least 1")
    if pulse_width_ms <= 0:
        raise ValueError("Pulse width must be positive")
    if period_ms <= 0:
        raise ValueError("Period must be positive")
    if pulse_width_ms > period_ms:
        raise ValueError(f"Pulse width ({pulse_width_ms} ms) exceeds period ({period_ms} ms)")

    total_duration_ms = num_pulses * period_ms + pulse_width_ms
    frequency_hz = 1000.0 / period_ms

    return {
        "total_duration_ms": total_duration_ms,
        "frequency_hz": frequency_hz,
    }

def snap_image():
	'''snap image and return 2d numpy array and metadata (image tags)'''
	if core is None or studio is None:
		raise RuntimeError("Not connected to Micro-Manager")
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

def spectra_shut_off():
	prop_list = ["White_Level", "Cyan_Level", "Green_Level", "Red_Level", "Violet_Level"]
	for prop in prop_list:
		core.set_property("Spectra", prop, 0)
	

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
				assert v >= 0, f"All shutter parameters must be >=0. Param {k} has value {v}"
				self.set_prop(k, v)
				self.core.wait_for_device(self.name)		
		self.core.set_shutter_open(True) ##required for changes to take effect and BLS device to be responsive

	def set_open(self):
		self.core.set_shutter_open(self.name, True)

class DMD():

	def __init__(self, core, directory_manager=None):
		self.dm = directory_manager
		self.stim_id = 0
		self.current_stim_sequence = None
		self.current_ss_order = None
		self.current_stim_dict = None
		self.sequence_loaded = False
		self.current_objective = None
		self.current_magnifier = None
		self.reference_image = None
		# Default homography matrix (5x objective). Per-objective overrides loaded from config.
		self._default_homography = np.array([[-2.30059278e-01,  4.32048634e-03,  5.20033114e+02],
		   [-1.52866544e-03, -4.66341985e-01,  4.99621839e+02],
		   [-4.08769248e-06,  1.14840265e-05,  9.97103894e-01]])
		try:
			from config import homography_matrices
			self.homography_matrices = {k: np.array(v) for k, v in homography_matrices.items()}
		except (ImportError, AttributeError):
			self.homography_matrices = {}
		# Hardware-dependent attributes; populated by _init_hardware
		self.core = None
		self.name = None
		self.h = None
		self.w = None
		self.shape = None
		self.shutter = None
		if core is not None:
			self._init_hardware(core)

	def _init_hardware(self, core):
		"""Initialize attributes that require a live Micro-Manager connection."""
		self.core = core
		self.name = self.core.get_slm_device()
		self.h = self.core.get_slm_height(self.name)
		self.w = self.core.get_slm_width(self.name)
		self.shape = (self.h, self.w)
		self.shutter = Shutter(core)
		self.get_objective()

	def reinitialize(self, core):
		"""Re-establish connection to Micro-Manager after a restart."""
		self._init_hardware(core)
		self.sequence_loaded = False

	def get_objective(self):
		objective = self.core.get_property('DObjective','Label')
		self.current_objective = objective

	def update_stim_sequence(self, filename):
		stim_sequence_set = load_stim_sequence_file(filename)
		self.current_stim_sequence = stim_sequence_set
		stim_sequence_set.save_binary_array(self.dm.active_directory)

	def update_stim_dict(self, stim_dict):
		self.current_stim_dict = stim_dict

	def collect_dmd_params(self, stim_sequence_set, order_name='default', stim_amp=50, 
		stim_duration=5, repeatCnt=1, isi=100, seq_int=100):
		'''
		assembles parameters of dmd stimulation into one dictionary. 
		'''
		##shutter params
		##t1 - t3 and i1 - i3 correspond to time and amplitude of analog output for Mightex BLS device, time in us
		print ("collect_dmd_params started")
		trig_delay = 1000 #1 ms, lag shutter to ensure mirror movement 
		trig_width = 1000 #1 ms trigger to BLS device, if t
		t1 = 1000 #1 ms t1 value (off)

		##triggerin directly, us int(stim_duration * 1000) #convert stim duration to us
		
		t2 = int(stim_duration * 1000) ##on pulse duration, converted to us
		if repeatCnt == 1:
			t3 = 1 ##shutter misbehaves when t3=0
		else:
			t3 = int(isi * 1000 - (t1 + t2)) ##convert isi to us, subtract t1 and t2 so that time is start to start
			assert t3 > 0, f"Calculated value of t3 <= 0. Pulse interval/ISI incompatible with duration."
		i1, i2, i3 = 0, 600, 0 ##600 is sufficient to trigger LED

		##dmd sequence params
		sequence_name = stim_sequence_set.name
		if self.current_ss_order is not None and self.current_ss_order.size > 0:
			order = self.current_ss_order.tolist()
		else:
			order = stim_sequence_set.sequence_dict[order_name].tolist()
		
		

		self.get_objective()
		objective = self.current_objective
		
		
		##timing and alignment info
		now = str(datetime.datetime.now())
		next_abf, next_abf_path = get_next_abf()
		
		stim_id = self.stim_id

		param_list = [trig_delay, trig_width, stim_amp, 
		next_abf, next_abf_path, stim_id, sequence_name, 
		order_name, order, now, objective,
		t1, t2, t3, i1, i2, i3, repeatCnt, seq_int
		]

		param_name_list = ["trig_delay", "trig_width", "stim_amp", 
		"abf_file", "abf_path", "stim_id", "sequence_name", 
		"order_name", "order", "time_stim", "objective",
		"t1", "t2", "t3", "i1", "i2", "i3", "repeatCnt", "sequence_interval"
		]
		
		stim_dict = dict(zip(param_name_list, param_list))
		return stim_dict


	def prep_and_load(self, order, target_n=120):
		'''
		Prepare an ordered sequence of images by expanding to match target_n (if needed), convert to DMD pixel space, and load to DMD.
		'''
		image_seq = self.current_stim_sequence.get_ordered_seq(order)
		print (f"order length {len(order)}")
		if len(order) < target_n:
			print ("order too short")
			expanded_set, order = self.pad_sequence(image_seq, order, target_n, with_reps=True)
			print (f"new order length {len(order)}")
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

	def run_current_sequence(self, stim_dict, sweep_reps=1):
		'''
		Run the image sequence currently loaded to the DMD with the shutter params specificied in stim_dict.
		'''
		print(stim_dict)
		self.core.stop_slm_sequence(self.name) ##stop and restart ongoing sequence so that first frame is as expected
		
		try:
			self.core.set_property(self.name, "OutputTriggerEnable", "1")
		except Exception:
			print ("intermittent dmd integer error, set OutTriggerEnable manually")
		self.core.set_property(self.name, "OutputTriggerDelay", stim_dict['trig_delay'])
		self.core.set_property(self.name, "OutputTriggerWidth", stim_dict['trig_width'])
		self.core.start_slm_sequence(self.name)
		self.core.set_property("pE300", "IntensityB", stim_dict['stim_amp'])
		self.core.set_property("pE300", "SelectionB", "1")
		shutter_name = "Mightex_BLS"
		shutter_list = ["t1", "t2", "t3", "i1", "i2", "i3", "repeatCnt"]
		self.core.set_property(shutter_name, "channel", 1)
		self.core.set_property(shutter_name, "mode", "TRIGGER")
		for k, v in stim_dict.items():
			if k in shutter_list:
				assert v >= 0, f"All shutter parameters must be >=0. Param {k} has value {v}"
				self.core.set_property(shutter_name, k, v)
				self.core.wait_for_device(shutter_name)
		self.core.set_shutter_open("Mightex_BLS", True)
		#self.core.set_property("Spectra", "Cyan_Level", stim_dict['stim_amp'])
		
		order = self.current_ss_order
		
		n_images = len(order)
		
		#print(f"load a clampex protocol with {n_images} triggers")
		
		pulse_train_res = pulse_train_info(n_images, 1, stim_dict["sequence_interval"])
		warning = f"load a clampex protocol with {n_images} triggers\nduration: {pulse_train_res['total_duration_ms']} ms. Frequency: {pulse_train_res['frequency_hz']} Hz"
		pop_warning(warning)
		self.update_photostim_log(stim_dict)
		
		self.stim_id += 1

	def run_current_img(self, stim_dict):
		'''
		Run the image currently loaded to the DMD with shutter params specified in stim_dict.
		'''
		order = np.array(stim_dict['order'])
		assert len(order) == 1, f"length of order is {len(order)}. Expected length==1"
		self.shutter.set_properties(stim_dict)
		self.update_photostim_log(stim_dict)
		self.stim_id += 1

		
	def convert_image(self, image):
		'''
		convert image from camera space to DMD space
		'''
		matrix = self.homography_matrices.get(self.current_objective, self._default_homography)
		inv_image = cv2.warpPerspective(image, matrix, self.shape[::-1])
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
		expanded_order = np.zeros(target_n, dtype=np.uint) - 1
		for i in range(reps):
			start_i = i * n_images
			stop_i = (i+1) * n_images
			expanded_image_seq[:, :, start_i:stop_i] = image_seq
			expanded_order[start_i:stop_i] = order
		return expanded_image_seq, expanded_order

	def set_image(self, image):
		assert image.shape == self.shape, f"dimensions of image {image.shape} and dmd {self.shape} do not match"
		self.core.set_slm_image(self.name, image)

	def all_field_pixels_on(self):
		image = np.ones((1024, 1024), dtype=np.uint8) * 255
		inv_image = self.convert_image(image)
		self.set_image(inv_image)

	def all_dmd_pixels_on(self):
		self.core.set_slm_pixels_to(self.name, 255)

	def all_dmd_pixels_off(self):
		self.core.set_slm_pixels_to(self.name, 0)

	def stop_sequence(self):
		self.core.stop_slm_sequence(self.name)

	def save_photostim_params(self, stim_dict):
		filename = "photostim_log.json"
		if self.dm != None:
			dir_path = self.dm.active_directory
		else:
			dir_path = Path.cwd()
		#stim_name = "photostim_"+str(stim_dict["stim_id"])
		stim_name = "run_" + str(stim_dict["stim_id"])
		main_dict = {stim_name:stim_dict}
		with open(dir_path/filename, 'w') as f:
			f.write(json.dumps(main_dict, indent=4))
			f.close()

	def update_photostim_log(self, stim_dict):
		filename = "photostim_log.json"
		
		if self.dm != None:
			dir_path = self.dm.active_directory
		else:
			dir_path = Path.cwd()
		print ("dir_path", dir_path)
		try:
			with open(dir_path/filename, 'r+') as f:
				existing_dict = json.load(f)
				#stim_name = "photostim_"+str(stim_dict["stim_id"])
				stim_name = "run_" + str(stim_dict["stim_id"])
				existing_dict[stim_name] = stim_dict
				f.seek(0)
				json.dump(existing_dict, f, indent=4)
		except:
			print(f"{dir_path/filename} not found")
			self.save_photostim_params(stim_dict)

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




def find_StimSequences(directory = 'C:/Users/tahage/photostim_generation/'):
	files = [x.stem for x in Path(directory).glob('*pickle') if x.is_file()]
	return files







