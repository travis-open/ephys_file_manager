from tkinter import ttk, N, W, E, S, IntVar, StringVar
from pathlib import Path
from metadata_upload import upload_md
from config import obj_list, mag_list, ill_list
from umanager import core, studio, snap_save_image

class ImageGUI(object):
	def __init__(self, root, parent):
		self.core = core
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
		objective['values'] = obj_list
		objective.set('5X')
		ttk.Label(mainframe, text='magnifier:').grid(column=1, row=0)
		self.MagVar = StringVar()
		mag = ttk.Combobox(mainframe, textvariable=self.MagVar, width=5)
		mag.grid(column=1, row=1)
		mag['values'] = mag_list
		mag.set('1.0x')
		ttk.Label(mainframe, text='illumination:').grid(column=2, row=0)	
		self.IlluminationVar = StringVar()
		ill = ttk.Combobox(mainframe, textvariable=self.IlluminationVar, width=5)
		ill.grid(column=2, row=1)
		ill['values'] = ill_list
		ill.set('DIC')

		objective.bind("<<ComboboxSelected>>", self.update_micromanager)
		mag.bind("<<ComboboxSelected>>", self.update_micromanager)
		ill.bind("<<ComboboxSelected>>", self.update_micromanager)

		ttk.Button(mainframe, text="capture, save meta", command=self.snap_and_save_to_ad).grid(column=0, row=2, columnspan=3)

		root.bind_all('<F5>', self.change_objective)
		root.bind_all('<F6>', self.change_mag)
		root.bind_all('<F7>', self.change_illumination)

	def change_illumination(self, event):
		current_ill = self.IlluminationVar.get()
		current_index = ill_list.index(current_ill)
		if current_index < len(ill_list)-1:
			next_ill = ill_list[current_index+1]
		else:
			next_ill = ill_list[0]
		self.IlluminationVar.set(next_ill)
		self.update_micromanager(event)

	def change_mag(self, event):
		current_mag = self.MagVar.get()
		current_index = mag_list.index(current_mag)
		if current_index < len(mag_list)-1:
			next_mag = mag_list[current_index+1]
		else:
			next_mag = mag_list[0]
		self.MagVar.set(next_mag)
		self.update_micromanager(event)

	def change_objective(self, event):
		current_obj = self.ObjectiveVar.get()
		current_index = obj_list.index(current_obj)
		if current_index < len(obj_list)-1:
			next_obj = obj_list[current_index+1]
		else:
			next_obj = obj_list[0]
		self.ObjectiveVar.set(next_obj)
		self.update_micromanager(event)

	def update_micromanager(self, event):
		obj_val = self.ObjectiveVar.get()
		self.core.set_property("DObjective","Label", obj_val)
		mag_val = float(self.MagVar.get()[:-1])
		self.core.set_property("DOptovar","Zoom", mag_val)
		ill_val = self.IlluminationVar.get()
		self.core.set_property("DWheel","Label", ill_val)

	def im_md_up(self, dst_file): ##image metadata upload
		mag_val = float(self.MagVar.get()[:-1])
		obj_val = float(self.ObjectiveVar.get()[:-1])
		ill_val = self.IlluminationVar.get()
		active_directory = self.parent.dm.active_directory
		animal_id = self.parent.dm.animal_id
		#slice_id = self.parent.sliceIDvar.get()
		slice_id = self.parent.dm.slice_id
		site_id = self.parent.dm.site_id
		image_meta_dict = {
		'objective': obj_val,
		'magnification': mag_val,
		'illumination': ill_val,
		'full_path':dst_file,
		'site_id':site_id,
		'slice_id':slice_id,
		'animal_id':animal_id
		}
		upload_md('image', image_meta_dict, force_append=True)

	def snap_and_save_to_ad(self):
		active_directory = self.parent.dm.active_directory
		tfile = snap_save_image(active_directory)
		self.im_md_up(str(tfile))


if __name__ == '__main__':
	root = Tk()
	app=ImageGUI(root)
	root.mainloop()