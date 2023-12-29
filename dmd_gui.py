from umanager import core, DMD, find_StimSequences
from tkinter import *
from tkinter import ttk

class DmdGUI(object):
	def __init__(self, root, parent):
		self.parent = parent
		self.root = root
		self.root.title("DMD control")
		self.dmd = DMD(core)
		self.StimSet_directory = 'C:/stimset_building/'
		mainframe = ttk.Frame(self.root, padding = "3 3 12 12")
		mainframe.grid(column=0, row=0, sticky=(N, W, E, S))

		self.root.columnconfigure(0, weight=2)
		self.root.columnconfigure(1, weight=1)
		
		spinbox_width = 5

		sp_row_start = 0 ##shutter params row start
		ttk.Label(mainframe, text='amp:').grid(column=0, row=sp_row_start+0)
		self.amp_var = IntVar(value=10)
		amp_spin = ttk.Spinbox(
			mainframe,
			from_=0,
			to=100,
			textvariable=self.amp_var,
			width=spinbox_width)
		amp_spin.grid(column=1, row=sp_row_start+0)

		ttk.Label(mainframe, text='dur:').grid(column=0, row=sp_row_start+1)
		self.dur_var = IntVar(value=1)
		dur_spin = ttk.Spinbox(
			mainframe, 
			from_=0,
			to=100,
			increment=0.5,
			textvariable=self.dur_var,
			width=spinbox_width)
		dur_spin.grid(column=1, row=sp_row_start+1)

		ttk.Label(mainframe, text='reps:').grid(column=0, row=sp_row_start+2)
		self.reps_var = IntVar(value=1)
		reps_spin = ttk.Spinbox(
			mainframe,
			from_=1,
			to=100,
			textvariable=self.reps_var,
			width=spinbox_width)
		reps_spin.grid(column=1, row=sp_row_start+2)

		ttk.Label(mainframe, text='ISI:').grid(column=0, row=sp_row_start+3)
		self.ISI_var = IntVar(value=100)
		ISI_spin = ttk.Spinbox(
			mainframe,
			from_=2,
			to=1000,
			textvariable=self.ISI_var,
			width=spinbox_width)
		ISI_spin.grid(column=1, row=sp_row_start+3)

		ss_list = find_StimSequences()
		ttk.Label(mainframe, text='stim sequence').grid(column=2, row=0)
		self.SSS_var = StringVar(value='stim sequence')
		ss_combo = ttk.Combobox(mainframe, textvariable=self.SSS_var)
		ss_combo.grid(column=3, row=0)
		ss_combo['values']=ss_list
		ss_combo.bind("<<ComboboxSelected>>", self.update_dmd_current_ss)

		ttk.Label(mainframe, text='order').grid(column=2, row=1)
		self.order_var = StringVar(value='default')
		self.order_combo = ttk.Combobox(mainframe, textvariable=self.order_var, postcommand=self.get_orders)
		self.order_combo.grid(column=3, row=1)

		ttk.Button(mainframe, text='run', command=self.run_dmd_acq_gui).grid(column=3, row=4)

	def run_dmd_acq_gui(self):
		amp = self.amp_var.get()
		dur = self.dur_var.get()
		reps = self.reps_var.get()
		isi = self.ISI_var.get()
		order_name = self.order_var.get()
		self.dmd.dmd_run(self.dmd.current_stim_sequence, order_name=order_name, 
			stim_amp=amp, stim_duration=dur)



	def update_dmd_current_ss(self, event):
		StimSet_filepath = self.StimSet_directory+self.SSS_var.get()+'.pickle'
		self.dmd.update_stim_sequence(StimSet_filepath)

	def get_orders(self):
		#StimSet_filepath = self.StimSet_directory+self.SSS_var.get()+'.pickle'
		#stim_sequence_set = load_stim_sequence_file(StimSet_filepath)
		stim_sequence_dict = self.dmd.current_stim_sequence.sequence_dict
		order_list = list(stim_sequence_dict.keys())
		self.order_combo.configure(value=order_list)
		return order_list