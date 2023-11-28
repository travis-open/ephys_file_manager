from tkinter import *
from tkinter import ttk
from pathlib import Path
from metadata_upload import *
from pywinauto.application import Application

import time


camera_save_path=Path(r"C:\HCImageData")

class ImageGUI(object):
	def __init__(self, root, parent):
		self.HCI_app = Application(backend='uia')
		self.HCI_app.connect(title_re='.* Display$', timeout=10)
		self.dlg = self.HCI_app.window(title_re='.* Display$')
		self.cap = self.dlg.child_window(title="Capture1", auto_id="413", control_type="Button").wrapper_object()

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
		objective['values'] = ('5x', '40x')
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
		ill['values'] = ('TL', 'GFP', 'RFP', 'YFP')
		ill.set('TL')

		ttk.Button(mainframe, text="capture, save meta", command=self.camera_button_func).grid(column=0, row=2, columnspan=3)

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

	def capture_image(self):
		
		self.cap.click()

	def find_recent_image(self):
		files = camera_save_path.glob("*tif")

		latest_file = max(files, key=lambda item: item.stat().st_ctime)
		
		img_name="img_"+str(int(latest_file.stat().st_ctime))+".tif"
		return latest_file, img_name

	def move_image(self, latest_file, img_name):
		
		dst_file=Path(self.parent.active_dir.get())/img_name
		latest_file.rename(dst_file)
		return str(dst_file)

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