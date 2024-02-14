from tkinter import ttk, Tk, IntVar, StringVar, N, W, E, S, Toplevel
from notepad import NotepadGUI
from dmd_gui import DmdGUI
from image_gui import ImageGUI
from metadata_upload import fetch_existing_values
from file_manager import DirectoryManager
from config import default_base_dir, species_list, project_list, slice_id_list, fix_well_list, ext_soln_list, brain_region_list, subregion_list, pip_soln_list

class MetaComboBox(object):
	def __init__(self, mainframe, text, tkVar, loc, values_list=[], width=10):
		ttk.Label(mainframe, text=text).grid(column=loc[0], row=loc[1])
		self.combo_box = ttk.Combobox(mainframe, textvariable=tkVar, width=width)
		self.combo_box.grid(column=loc[0], row=loc[1]+1)
		self.combo_box['values'] = values_list

class ExpControlGUI(object):
	def __init__(self, root, directory_manager):
		
		self.dm = directory_manager
		self.root = root
		self.root.title("experiment control")
		mainframe = ttk.Frame(root, padding="3 3 12 12")
		mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
		self.root.columnconfigure(0, weight=1)
		self.root.rowconfigure(0, weight=1)

		self.base_dir = StringVar()
		self.base_dir.set(self.dm.base_directory)
		ttk.Label(mainframe, text="base").grid(column=0, row=0)
		base_entry = ttk.Entry(mainframe, textvariable=self.base_dir, width=38)
		base_entry.grid(column=1, row=0, sticky=(W,E), columnspan=3)
		ttk.Button(mainframe, text="set base", command=self.base_update).grid(column=4, row=0)

		self.active_dir = StringVar()
		ttk.Label(mainframe, text="active").grid(column=0, row=1)
		active_entry = ttk.Entry(mainframe, textvariable=self.active_dir, width=38)
		active_entry.grid(column=1, row=1, columnspan=3)
		ttk.Button(mainframe, text="man. update", command = self.manual_update_button).grid(column=4, row=1)

		ttk.Button(mainframe, text="new day", command=self.new_day_button).grid(column=0, row=2)
		ttk.Button(mainframe, text="new slice", command=self.new_slice_button).grid(column=1, row=2)
		ttk.Button(mainframe, text="new site", command=self.new_site_button).grid(column=2, row=2)
		
		self.animal_id_var = StringVar()
		ttk.Label(mainframe, text='animal ID:').grid(column=0, row=3)
		self.animal_cb = ttk.Combobox(mainframe, textvariable=self.animal_id_var, 
			width=10, postcommand=self.fetch_animals)
		self.animal_cb.grid(column=0, row=4)
		
		self.species_var = StringVar()
		self.project_var = StringVar()
		self.slice_id_var = StringVar()
		self.fix_well_id_var = StringVar()
		self.fix_orientation_var = StringVar()
		self.ext_soln_var = StringVar()
		self.region_var = StringVar()
		self.HS0_var = IntVar()
		self.HS1_var = IntVar()
		self.pip_sol_var0 = StringVar()
		self.pip_sol_var1 = StringVar()
		self.subregion_var0 = StringVar()
		self.subregion_var1 = StringVar()
		self.reporter_var0 = StringVar()
		self.reporter_var1 = StringVar()

		self.species_cb = MetaComboBox(mainframe, 'species:', self.species_var, 
			[0, 5], values_list=species_list)
		self.project_cb = MetaComboBox(mainframe, 'project:', self.project_var, 
			[0, 7], values_list=project_list)
		self.slice_id_cb = MetaComboBox(mainframe, 'slice ID:', self.slice_id_var,
			[1,3], values_list=slice_id_list)
		self.fix_well_cb = MetaComboBox(mainframe, 'PFA well:', self.fix_well_id_var,
			[1,5], values_list=fix_well_list)
		self.fix_o_cb = MetaComboBox(mainframe, 'PFA flip?', self.fix_orientation_var,
			[1,7], values_list=['not flipped', 'flipped', 'unsure'])
		self.ext_soln_cb = MetaComboBox(mainframe, 'external:', self.ext_soln_var,
			[2,5], values_list=ext_soln_list)
		self.region_cb = MetaComboBox(mainframe, 'region:', self.region_var,
			[2,7], values_list=brain_region_list)


		HS0_check = ttk.Checkbutton(mainframe, text='HS0', variable=self.HS0_var).grid(column=2,row=3)
		HS1_check = ttk.Checkbutton(mainframe, text='HS1', variable=self.HS1_var).grid(column=2,row=4)
		ttk.Label(mainframe, text="pipette:").grid(column=3,row=2)
		ttk.Label(mainframe, text="subregion:").grid(column=4, row=2)
		ttk.Label(mainframe, text="reporter:").grid(column=5, row=2)
		reporter_list = ('negative', 'positive')
		reporter0_cb = ttk.Combobox(mainframe, textvariable=self.reporter_var0, width = 5)
		reporter0_cb.grid(column=5, row=3)
		reporter0_cb['values'] = reporter_list
		reporter1_cb = ttk.Combobox(mainframe, textvariable=self.reporter_var1, width = 5)
		reporter1_cb.grid(column=5, row=4)
		reporter1_cb['values'] = reporter_list
		pipette0_cb = ttk.Combobox(mainframe, textvariable=self.pip_sol_var0, width=5)
		pipette0_cb.grid(column=3, row=3)
		pipette1_cb = ttk.Combobox(mainframe, textvariable=self.pip_sol_var1, width=5)
		pipette1_cb.grid(column=3, row=4)
		pipette0_cb['values'] = pip_soln_list
		pipette1_cb['values'] = pip_soln_list
		subregion0_cb = ttk.Combobox(mainframe, textvariable=self.subregion_var0, width=5)
		subregion0_cb.grid(column=4, row=3)
		subregion1_cb = ttk.Combobox(mainframe, textvariable=self.subregion_var1, width=5)
		subregion1_cb.grid(column=4, row=4)
		subregion0_cb['values'] = subregion_list
		subregion1_cb['values'] = subregion_list

		ttk.Button(mainframe, text="save metadata", command = self.save_meta_button).grid(column=5, row=0)
		ttk.Button(mainframe, text="move files", command = self.copy_files_button).grid(column=5, row=1)
		ttk.Button(mainframe, text="notepad", command = self.launch_np).grid(column=5, row=8)
		ttk.Button(mainframe, text="DMD", command=self.launch_dmd).grid(column=5, row=7)


		self.field_to_var = {'animal_id':self.animal_id_var, 'species':self.species_var,
								'project':self.project_var, 'slice_id':self.slice_id_var,
								'fixation_well_id':self.fix_well_id_var, 'fixed_orientation':self.fix_orientation_var,
								'region':self.region_var, 'external_solution':self.ext_soln_var}

	def save_meta_button(self):
		self.store_gui_data()
		dm.save_data_model(model_level="current", gsheet=True)
		if self.HS0_var.get():
			cell0_dict = {
			'target_region':self.subregion_var0.get(),
			'pipette_solution':self.pip_sol_var0.get(),
			'reporter_status':self.reporter_var0.get()}
			cell_model = dm.build_cell_model(0, ext_dict=cell0_dict)
			dm.build_and_save_cell_model(0, ext_dict=cell0_dict, gsheet=True)
		if self.HS1_var.get():
			cell1_dict = {
			'target_region':self.subregion_var1.get(),
			'pipette_solution':self.pip_sol_var1.get(),
			'reporter_status':self.reporter_var1.get()}
			dm.build_and_save_cell_model(1, ext_dict=cell1_dict, gsheet=True)


	def copy_files_button(self):
		self.dm.copy_files_src_list()

	def manual_update_button(self):
		target_dir = self.active_dir.get()
		self.dm.set_existing_dir(target_dir)
		self.update_gui_from_dir_manager()

	def base_update(self):
		target_base = self.base_dir.get()
		self.dm.set_base_dir(target_base)

	def fetch_animals(self):
		self.animal_ID_list = fetch_existing_values('animal', 'animal_id')
		self.animal_cb['values'] = self.animal_ID_list

	def new_day_button(self):
		self.dm.make_new_day(save_current=True)
		self.active_dir.set(dm.active_directory)
		self.update_gui_from_dir_manager()
	
	def new_slice_button(self):
		self.store_gui_data()
		self.dm.make_new_slice(save_current=True)
		self.active_dir.set(dm.active_directory)
		self.update_gui_from_dir_manager()
	
	def new_site_button(self):
		self.store_gui_data()
		self.dm.make_new_site(save_current=True)
		self.active_dir.set(dm.active_directory)
		self.update_gui_from_dir_manager()

	def store_gui_data(self):
		dir_dict = self.collect_all_dir_data()
		self.dm.set_meta_attr(dir_dict)
		

	def update_gui_from_dir_manager(self):
		for k, v in vars(self.dm).items():
			#if k in self.field_to_var.keys() and v !=None:
			if k in self.field_to_var.keys():
				if k == 'slice_id' and v != None:
					v = v.split('.')[1] ##remove animal_id from full slice_id for GUI
				if v is None:
					v = ''
				gui_var = self.field_to_var[k]
				gui_var.set(v)
		self.root.update_idletasks()

	##collect_xx_data functions gather user entered data from the GUI.
	##Other attributes/fields that ultimately go the model are handled by DirectoryManager
	def collect_level_data(self, d_level=None):
		if d_level is None:
			d_level = self.dm.directory_level
		if d_level == 'day':
			level_dict = self.collect_day_data()
		if d_level == 'slice':
			level_dict = self.collect_slice_data()
		if d_level == 'site':
			level_dict = self.collect_site_data()
		return level_dict

	def collect_day_data(self):
		day_dict = {
		"animal_id": self.animal_id_var.get(),
		"species": self.species_var.get(),
		"project": self.project_var.get()
		}
		return day_dict

	def collect_slice_data(self):
		slice_dict = {
		"slice_id":self.animal_id_var.get()+'.'+self.slice_id_var.get(),
		"fixation_well_id": self.fix_well_id_var.get(),
		"fixed_orientation": self.fix_orientation_var.get() 
		}
		return slice_dict

	def collect_site_data(self):
		site_dict = {
		"region": self.region_var.get(),
		"external_solution": self.ext_soln_var.get() 
		}
		return site_dict

	def collect_all_dir_data(self):
		day_dict = self.collect_day_data()
		slice_dict = self.collect_slice_data()
		site_dict = self.collect_site_data()
		dir_dict = day_dict | slice_dict | site_dict
		return dir_dict

	def collect_cell0_data(self):
		assert HS0_var.get(), "headstage 0/HS0_var not set as active"
		cell0_dict = {
		"recording_site": self.subregion_var0.get(),
		"pipette_solution": self.pip_sol_var0.get(),
		"reporter_status": self.reporter_var0.get()
		}
		return cell0_dict

	def collect_cell1_data(self):
		assert HS1_var.get(), "headstage 1/HS1_var not set as active"
		cell1_dict = {
		"recording_site": self.subregion_var1.get(),
		"pipette_solution": self.pip_sol_var1.get(),
		"reporter_status": self.reporter_var1.get()
		}
		return cell1_dict

	def launch_np(self):
		notepad_window = Toplevel(self.root)
		NotepadApp = NotepadGUI(notepad_window, self)

	def launch_dmd(self):
		dmd_window = Toplevel(self.root)
		dmdApp = DmdGUI(dmd_window, self)



if __name__ == '__main__':
	root = Tk()
	dm = DirectoryManager()
	app = ExpControlGUI(root, dm)
	image_window = Toplevel(root)
	ImageApp = ImageGUI(image_window, app)
	
	
	root.mainloop()