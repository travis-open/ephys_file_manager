import os
from datetime import date
from tkinter import *
from tkinter import ttk
import time
import shutil
from metadata_upload import *
from image_gui import *
from abf_meta import *
from nwb_info import process_nwb_in_dir
from pathlib import Path
from config import src_list, species_list, project_list, ext_soln_list, brain_region_list, subregion_list, pip_soln_list
import subprocess
from notepad import NotepadGUI

def make_new_day(base_dir=r"C:\Data", i=0):
	"""
	Makes a new directory with today's date. Sets it as working directory.

	"""
	today = str(date.today())+f"-{i:03}"
	newpath = Path(base_dir)/today
	if not newpath.exists():
		newpath.mkdir()
		os.chdir(newpath)
	else:
		i+=1
		make_new_day(base_dir=base_dir, i=i)
	
def make_new_slice(i=0):
	"""
	Makes a new slice directory. 
	If called when working directory is a slice or site folder, moves up to 'day'.
	Sets new slice folder as working directory.

	Arguments:
		i (iterative integer): defaults to 0. If a folder already exists with passed value, iterate to next integer

	"""
	if i>999:  ##should not have 1000 slices
		raise ValueError('slice i greater than 1000 not supported')
	cwd=Path.cwd()
	if cwd.parts[-1][-8:-4]=='site': ##if currently in site folder move up to day folder to make new slice 
		os.chdir('../../')
	if cwd.parts[-1][-9:-4]=='slice': ##if currently in slice folder move up to day
		os.chdir('../')
	newpath = Path(f"slice-{i:03}") ##slice number padded to 3 digits
	if not newpath.exists(): #make new directory and set path if it doesn't exist
		newpath.mkdir()
		os.chdir(newpath)
	else:					#if path exists, increase slice number
		i+=1
		make_new_slice(i)

def make_new_site(i=0):
	"""
	Makes a new site directory. 
	If called when working directory is a site folder, moves up to 'site'.
	Sets new site folder as working directory.

	Arguments:
		i (iterative integer): defaults to 0. If a folder already exists with passed value, iterate to next integer

	"""
	if i>999:
		raise ValueError('site i greater than 1000 not supported')
	cwd = Path.cwd()
	if cwd.parts[-1][-8:-4]=='site': ##if currently in site folder move up to day folder to make new slice
		os.chdir('../')
	newpath = Path(f"site-{i:03}")
	if not newpath.exists(): #make new directory and set path if it doesn't exist
		newpath.mkdir()
		os.chdir(newpath)
	else:
		i += 1
		make_new_site(i)

animal_ID_list = fetch_existing_values('animal', 'animal_ID')

class DirectoryGUI(object):
	def __init__(self, root):
		self.root = root
		self.root.title("directory control")
		mainframe = ttk.Frame(root, padding = "3 3 12 12")
		mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
		self.root.columnconfigure(0, weight=1)
		self.root.rowconfigure(0, weight=1)

		self.base_dir = StringVar()
		self.base_dir.set(r"C:\Data")
		self.active_dir = StringVar()
		self.new_dir_time = time.time()
		ttk.Label(mainframe, text="base").grid(column=0, row=0)
		ttk.Label(mainframe, text="active").grid(column=0, row=1)
		ttk.Button(mainframe, text="new day", command=self.new_day_up).grid(column=0, row=2)
		
		ttk.Label(mainframe, text="animal ID:").grid(column=0,row=3)
		self.animalIDvar = StringVar()
		animalID = ttk.Combobox(mainframe, textvariable=self.animalIDvar, width=10)
		animalID.grid(column=0, row=4)
		animalID['values'] = animal_ID_list

		ttk.Label(mainframe, text="species:").grid(column=0, row=5)
		self.speciesvar = StringVar()
		species = ttk.Combobox(mainframe, textvariable=self.speciesvar, width=10)
		species.grid(column=0,row=6)
		species['values'] = species_list
		
		ttk.Label(mainframe, text="project:").grid(column=0, row=7)
		self.projectvar = StringVar()
		project = ttk.Combobox(mainframe, textvariable=self.projectvar, width=10)
		project.grid(column=0,row=8)
		project['values'] = project_list

		base_entry = ttk.Entry(mainframe, textvariable=self.base_dir, width=38)
		base_entry.grid(column=1, row=0, sticky=(W,E), columnspan=3)
		ttk.Entry(mainframe, textvariable=self.active_dir, width=38).grid(column=1, row=1, columnspan=3)
		ttk.Button(mainframe, text="new slice", command=self.new_slice_up).grid(column=1, row=2)
		ttk.Label(mainframe, text="slice ID:").grid(column=1,row=3)
		self.sliceIDvar = StringVar()
		sliceID = ttk.Combobox(mainframe, textvariable=self.sliceIDvar, width=10)
		sliceID.grid(column=1, row=4)
		ttk.Label(mainframe, text="PFA well:").grid(column=1, row=5)
		self.wellIDvar = StringVar()
		wellID = ttk.Combobox(mainframe, textvariable=self.wellIDvar, width=10)
		wellID.grid(column=1, row=6)
		wellID['values'] = ('not fixed', 'A1', 'A2', 'A3', 'A4', 'B1', 'B2', 'B3', 'B4', 'C1', 'C2', 'C3', 'C4')
		ttk.Label(mainframe, text="orientation:").grid(column=1, row=7)
		self.orientationvar = StringVar()
		orientation = ttk.Combobox(mainframe, textvariable=self.orientationvar, width=10)
		orientation.grid(column=1, row=8)
		orientation['values'] = ('not flipped', 'flipped', 'unsure')


		ttk.Label(mainframe, text="external:").grid(column=2, row=5)
		self.externalIDvar = StringVar()
		external = ttk.Combobox(mainframe, textvariable=self.externalIDvar, width=10)
		external.grid(column=2, row=6)
		external['values'] = ext_soln_list

		ttk.Label(mainframe, text="region:").grid(column=2, row=7)
		self.regionVar = StringVar()
		region = ttk.Combobox(mainframe, textvariable=self.regionVar, width=10)
		region.grid(column=2, row=8)
		region['values'] = brain_region_list

		ttk.Button(mainframe, text="set base", command=self.base_up).grid(column=4, row=0)
		
		self.HS0_var=IntVar()
		self.HS1_var=IntVar()
		HS0_cb=ttk.Checkbutton(mainframe, text='HS0', variable=self.HS0_var).grid(column=2,row=3)
		HS1_cb=ttk.Checkbutton(mainframe, text='HS1', variable=self.HS1_var).grid(column=2,row=4)
		
		ttk.Button(mainframe, text="new site", command=self.new_site_up).grid(column=2, row=2)
		ttk.Label(mainframe, text="pipette:").grid(column=3,row=2)
		ttk.Label(mainframe, text="subregion:").grid(column=4, row=2)
		ttk.Label(mainframe, text="reporter:").grid(column=5, row=2)
		self.pip_sol_0 = StringVar()
		self.pip_sol_1 = StringVar()
		pipette0_cb = ttk.Combobox(mainframe, textvariable=self.pip_sol_0, width=5)
		pipette0_cb.grid(column=3, row=3)
		pipette1_cb = ttk.Combobox(mainframe, textvariable=self.pip_sol_1, width=5)
		pipette1_cb.grid(column=3, row=4)
		pipette0_cb['values'] = pip_soln_list
		pipette1_cb['values'] = pip_soln_list

		self.subregion_0 = StringVar()
		self.subregion_1 = StringVar()
		subregion0_cb = ttk.Combobox(mainframe, textvariable=self.subregion_0, width=5)
		subregion0_cb.grid(column=4, row=3)
		subregion1_cb = ttk.Combobox(mainframe, textvariable=self.subregion_1, width=5)
		subregion1_cb.grid(column=4, row=4)
		
		subregion0_cb['values'] = subregion_list
		subregion1_cb['values'] = subregion_list

		self.reporter_0 = StringVar()
		self.reporter_1 = StringVar()
		reporter_list = ('negative', 'positive')
		reporter0_cb = ttk.Combobox(mainframe, textvariable=self.reporter_0, width = 5)
		reporter0_cb.grid(column=5, row=3)
		reporter0_cb['values'] = reporter_list
		reporter1_cb = ttk.Combobox(mainframe, textvariable=self.reporter_1, width = 5)
		reporter1_cb.grid(column=5, row=4)
		reporter1_cb['values'] = reporter_list
		
		ttk.Button(mainframe, text="man. update", command = self.set_cwd_manual).grid(column=4, row=1)
		ttk.Button(mainframe, text="save metadata", command = self.save_meta_button).grid(column=5, row=0)
		ttk.Button(mainframe, text="move files", command = self.copy_files_button).grid(column=5, row=1)
		ttk.Button(mainframe, text="notepad", command = self.launch_np).grid(column=5, row=8)
		self.directory_level='base' ##can be 'base', 'day', 'slice', 'site'

	def launch_np(self):
		notepad_window=Toplevel(self.root)
		NotepadApp=NotepadGUI(notepad_window, self)

	def return_slice_ID(self):
		"""
		Returns full sliceID (with animal ID preceeding)
		"""
		slice_ID=self.animalIDvar.get()+'.slice-'+self.sliceIDvar.get()
		return slice_ID

	def return_site_ID(self):
		"""
		Returns full siteID (with animal ID and slice ID preceding)
		"""
		slice_ID=self.return_slice_ID()
		site_ID=slice_ID+'.'+self.active_dir.get()[-8:]
		return site_ID

	def save_meta_button(self):
		slice_ID=self.return_slice_ID()
		site_ID=self.return_site_ID()
		phys_file_path=self.active_dir.get()
		site_dict=self.collect_site_data()
		upload_md('site', site_dict)
		update_md('site.json', site_dict)
		if self.HS0_var.get():
			cell0_dict={
			'site_ID': site_ID,
			'cell_ID': site_ID+'.HS0',
			'headstage': 0,
			'phys_file_path': phys_file_path,
			'target_region': self.subregion_0.get(),
			'pipette_solution': self.pip_sol_0.get(),
			'reporter_status': self.reporter_0.get()
			}
			update_md('cell0.json', cell0_dict)
			upload_md('cell', cell0_dict, col_match='cell_ID')
		if self.HS1_var.get():
			cell1_dict={
			'site_ID': site_ID,
			'cell_ID': site_ID+'.HS1',
			'headstage': 1,
			'phys_file_path': phys_file_path,
			'target_region': self.subregion_1.get(),
			'pipette_solution': self.pip_sol_1.get(),
			'reporter_status': self.reporter_1.get()
			}
			update_md('cell1.json', cell1_dict)
			upload_md('cell', cell1_dict, col_match='cell_ID')
		slice_dict=self.collect_slice_data()
		slice_json_path=self.slice_directory+r"\slice.json"
		update_md(slice_json_path, slice_dict)
		upload_md('slice', slice_dict)
				
	def base_up(self):
		target_base=self.base_dir.get()
		target_base=target_base.strip('\"')
		os.chdir(target_base)
		self.directory_level='base'	
	
	def new_day_up(self):
		make_new_day(base_dir=self.base_dir.get().strip('\"'))
		self.update_active()
		self.day_directory=os.getcwd()
		self.directory_level='day'
	
	def new_slice_up(self):
		if self.directory_level=='day':
			day_dict=self.collect_day_data()
			day_json_path=self.day_directory+r"\day.json"
			upload_md('day', day_dict)
			update_md(day_json_path, day_dict)
			animal_dict = self.collect_animal_data()
			upload_md('animal', animal_dict, col_match='animal_ID')
		
		if self.directory_level=='slice':
			slice_dict=self.collect_slice_data()
			upload_md('slice', slice_dict)
			update_md('slice.json', slice_dict)

		if self.directory_level=='site':
			slice_dict=self.collect_slice_data()
			upload_md('slice', slice_dict)
			slice_json_path=self.slice_directory+r"\slice.json"
			update_md(slice_json_path, slice_dict)
			site_dict=self.collect_site_data()
			upload_md('site', site_dict)
			update_md('site.json', site_dict)

		self.sliceIDvar.set('')
		self.wellIDvar.set('')
		self.orientationvar.set('')

		self.reset_cell_info()
		
		make_new_slice()
		self.update_active()
		self.slice_rig_time=self.new_dir_time
		self.slice_directory=os.getcwd()
		self.directory_level='slice'

	def new_site_up(self):
		##slice information may have been updated, collect and store
		slice_dict=self.collect_slice_data()
		upload_md('slice', slice_dict)
		slice_json_path=self.slice_directory+r"\slice.json"
		update_md(slice_json_path, slice_dict)
		if self.directory_level=='site':
			site_dict=self.collect_site_data()
			upload_md('site', site_dict)
			update_md('site.json', site_dict)
		self.reset_cell_info()
		make_new_site()
		self.update_active()
		site_ID=self.return_site_ID()
		phys_file_path=self.active_dir.get()
		site_dict=self.collect_site_data()
		upload_md('site', site_dict)
		update_md('site.json', site_dict)
		self.directory_level='site'
		

	def collect_day_data(self):
		day_dict={
		'animal_ID': self.animalIDvar.get(),
		'species': self.speciesvar.get(),
		'phys_file_path': self.day_directory,
		'project': self.projectvar.get()
		}
		return day_dict

	def collect_animal_data(self):
		animal_dict={
		'animal_ID': self.animalIDvar.get(),
		'species': self.speciesvar.get(),
		}
		return animal_dict
	
	def collect_slice_data(self):
		slice_ID=self.return_slice_ID()
		##make slice_rig_time human format
		t=time.localtime(self.slice_rig_time)
		slice_time=time.strftime("%Y-%m-%d %H:%M:%S", t)
		slice_dict={
		'slice_ID': slice_ID,
		'animal_ID': self.animalIDvar.get(),
		'well_ID': self.wellIDvar.get(),
		'phys_file_path': self.slice_directory,
		'slice_rig_time': slice_time,
		'well_ID': self.wellIDvar.get(),
		'orientation' :self.orientationvar.get()
		}
		return slice_dict

	def collect_site_data(self):
		slice_ID=self.return_slice_ID()
		site_ID=self.return_site_ID()
		phys_file_path=self.active_dir.get()
		site_dict={
		'slice_ID':slice_ID ,
		'phys_file_path': phys_file_path,
		'site_ID': site_ID,
		'external_solution':self.externalIDvar.get(),
		'region':self.regionVar.get()
		}
		return site_dict
	
	def update_active(self):
		self.active_dir.set(os.getcwd())
		self.new_dir_time = time.time()
	
	def set_cwd_manual(self):
		target_wd=self.active_dir.get()
		target_wd=target_wd.strip('\"')
		os.chdir(target_wd)
		self.new_dir_time = time.time()
		target_wd=Path(target_wd)
		warn=True
		if target_wd.parts[-1][-8:-4]=='site':
			self.slice_directory=target_wd.parents[0]
			self.day_directory=target_wd.parents[1]
			warn=False
		if target_wd.parts[-1][-9:-4]=='slice':
			self.slice_directory=target_wd
			self.day_directory=target_wd.parents[0]
			warn=False
		if warn:
			print("warning - manual directory not recognized as slice or site folder")

	def copy_files_button(self):
		dst = os.getcwd()
		for src in src_list:
			copy_files_since_tstamp(self.new_dir_time, src, dst)
		parse_abf_in_dir(dst, site_ID=self.return_site_ID())
		process_nwb_in_dir()

	def reset_cell_info(self):
		self.HS0_var.set(0)
		self.HS1_var.set(0)
		self.subregion_0.set('')
		self.pip_sol_0.set('')
		self.reporter_0.set('')
		self.subregion_1.set('')
		self.pip_sol_1.set('')
		self.reporter_1.set('')

def last_mod_time(fname):
	return os.path.getmtime(fname)

def copy_files_since_tstamp(tstamp, src, dst):
	src=os.path.abspath(src)
	for fname in os.listdir(src):
		src_fname = os.path.join(src, fname)
		if last_mod_time(src_fname) > tstamp:
			print(f"{src_fname} is recent")
			dst_fname = os.path.join(dst, fname)
			shutil.copy(src_fname, dst_fname)





if __name__ == '__main__':
	root = Tk()
	app=DirectoryGUI(root)
	image_window=Toplevel(root)
	ImageApp=ImageGUI(image_window, app)
	
	root.mainloop()




