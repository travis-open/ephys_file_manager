from tkinter import *
from tkinter import ttk
from pathlib import Path
import os

class NotepadGUI(object):
	def __init__(self, root, parent):
		self.parent = parent
		self.root = root
		self.root.title("notepad")
		self.save_dir = self.parent.dm.active_directory
		self.text_box = Text(self.root, height = 20, width = 30)
		self.text_box.pack(fill=BOTH, expand=True)
		#text ="""user notes     """
		text = self.find_notes_file()
		self.text_box.insert('end', text)
		

		save_button = Button(root, text="save", command=self.save_text_box)


		self.text_box.pack()
		save_button.pack()
		self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
	
	def save_text_box(self):
		directory = self.save_dir
		notes=self.text_box.get("1.0", "end-1c")
		with open(directory/'notes.txt', 'w') as f:
			f.write(notes)

	def find_notes_file(self):
		try:
			directory = self.save_dir
			notes_file=open(directory/"notes.txt","r")
			notes_text = notes_file.read()
			notes_file.close()
			return notes_text
		except IOError:
			print ("notes.txt not found")
			start_string = "user notes"
			return start_string

	def on_closing(self):
		self.save_text_box()
		self.root.destroy()






if __name__ == '__main__':
	root = Tk()
	app=NotepadGUI(root)
	root.mainloop()



