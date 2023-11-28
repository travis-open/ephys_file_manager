from tkinter import *
from tkinter import ttk
from pathlib import Path
from metadata_upload import *
from pycromanager import Core
import tifffile
import json
import time





class ImageGUI(object):
	def __init__(self, root, parent):
		self.core = Core()
		self.parent = parent
		root.title("image control")
		mainframe = ttk.Frame(root, padding = "3 3 12 12")
		mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
		root.columnconfigure(0, weight=1)
		root.rowconfigure(0, weight=1)
		ttk.Label(mainframe, text='objective:').grid(column=0, row=0)
		self.ObjectiveVar = StringVar()
		objective = ttk.Combobox(mainframe, textvariable=self.ObjectiveVar, width=5)
		objective.grid(column=0, row=1)
		objective['values'] = ('5X', '40X')
		objective.set('5x')
		ttk.Label(mainframe, text='magnifier:').grid(column=1, row=0)
		self.MagVar = StringVar()
		mag = ttk.Combobox(mainframe, textvariable=self.MagVar, width=5)
		mag.grid(column=1, row=1)
		mag['values'] = ('0.5x', '0.63x', '0.8x', '1.0x', '1.25x', '1.6x', '2.0x', '2.5x', '3.2x', '4.0x')
		mag.set('1.0x')
		ttk.Label(mainframe, text='illumination:').grid(column=2, row=0)	
		self.IlluminationVar = StringVar()
		ill = ttk.Combobox(mainframe, textvariable=self.IlluminationVar, width=5)
		ill.grid(column=2, row=1)
		ill['values'] = ('DIC', 'GFP', 'RFP', 'YFP')
		ill.set('DIC')

		objective.bind("<<ComboboxSelected>>", self.update_micromanager)
		mag.bind("<<ComboboxSelected>>", self.update_micromanager)
		ill.bind("<<ComboboxSelected>>", self.update_micromanager)

		ttk.Button(mainframe, text="capture, save meta", command=self.snap_and_save).grid(column=0, row=2, columnspan=3)

	def update_micromanager(self, event):
		obj_val=self.ObjectiveVar.get()
		self.core.set_property("DObjective","Label", obj_val)
		mag_val=float(self.MagVar.get()[:-1])
		self.core.set_property("DOptovar","Zoom", mag_val)
		ill_val = self.IlluminationVar.get()
		self.core.set_property("DWheel","Label", ill_val)

	def im_md_up(self, dst_file): ##image metadata upload
		mag_val = float(self.MagVar.get()[:-1])
		obj_val = float(self.ObjectiveVar.get()[:-1])
		ill_val = self.IlluminationVar.get()
		active_directory = self.parent.active_dir.get()
		image_meta_dict = {
		'objective': obj_val,
		'magnification': mag_val,
		'illumination': ill_val,
		'full_path':dst_file
		}
		upload_md('image', image_meta_dict, force_append=True)

	def snap_and_save(self):#, manual_meta_dict={}):
		active_directory = self.parent.active_dir.get()
		self.core.snap_image()
		tagged_image=self.core.get_tagged_image()
		image_height = tagged_image.tags['Height']
		image_width = tagged_image.tags['Width']
		image = tagged_image.pix.reshape((image_height, image_width))
		md = tagged_image.tags
		filename="img_"+str(int(time.time()))
		active_dir=Path(self.parent.active_dir.get())
		tfile=filename+'.tif'
		jsonfile=filename+'.json'
		tifffile.imwrite(active_dir/tfile, image)
		with open(active_dir/jsonfile, 'a') as f:
			f.write(json.dumps(md, indent=4))
			f.close()

		self.im_md_up(str(active_dir/tfile))

	def camera_button_func(self):
		##TODO check latest file before capture, check for new file before preceding? replace sleep
		self.capture_image()
		time.sleep(2)
		latest_file, img_name=self.find_recent_image()
		dst_file=self.move_image(latest_file, img_name)
		self.im_md_up(dst_file)



if __name__ == '__main__':
	root = Tk()
	app=ImageGUI(root)
	root.mainloop()