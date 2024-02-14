import gspread
import pandas as pd
from config import gsheet_key
import json
import numpy as np


gc = gspread.service_account(filename='mycredentials.json')

gsheet = gc.open_by_key(gsheet_key)

def update_md(filepath, meta_dict):
	"""
	Save metadata as a json to the indicated file path. 
	Check if file exists. If so, update.
	Otherwise, create new json
	"""
	
	try:
		with open(filepath) as f:
			existing_dict=json.load(f)
		existing_dict.update(meta_dict)
		with open(filepath, 'w') as f:
			f.write(json.dumps(existing_dict, indent=4))
	except:
		print(f"{filepath} not found. Making new file.")
		save_md(filepath, meta_dict)

def save_md(filepath, meta_dict):
	with open(filepath, 'a') as f:
		f.write(json.dumps(meta_dict, indent=4))
		f.close()

def upload_md(sheet_name, meta_dict, force_append=False, col_match='phys_file_path'):
	"""
	Upload metadata values to the Google spreadsheet. 
	Function first looks for a row containing the phys_file_path to place value into.
	If such a row doesn't exist, it adds data to the end

	Arguments:
		sheet_name: name of sheet. 
		meta_dict: dictionary of key:value pairs in which key is the target column name
		force_append: if True append even if file_path already found (used for cell sheet data entry)
		col_match: key in meta_dict used to find row in spreadsheet with matching value
	"""

	sheet = gsheet.worksheet(sheet_name)
	df = pd.DataFrame(sheet.get_all_records())
	
	if force_append is True:
		entry_row = df.shape[0]+2
	else:
		col_match_value = meta_dict[col_match]
		col_match_col = df.columns.get_loc(col_match)+1 ##+1 as gspread starts with 1
		existing_cell = sheet.find(col_match_value, in_column=col_match_col)
		matching_cells = df[col_match].values == col_match_value
		if np.sum(matching_cells) <1:
			entry_row = df.shape[0]+2
		else:
			entry_row=matching_cells.argmax()+2
	for key, value in meta_dict.items():
		if key in df.columns and value != '': ##don't overwrite existing data with missing data
			value = str(value)  ##convert objects like dates and Paths to str to please gspread
			col=df.columns.get_loc(key)+1
			sheet.update_cell(entry_row, col, value)



def fetch_existing_values(sheet_name, col_name):
	"""
	Find existing entries for a given sheet and column. e.g. animal_ID's.
	"""
	sheet = gsheet.worksheet(sheet_name)
	df = pd.DataFrame(sheet.get_all_records())
	return list(df[col_name].unique())

test_dict={'animal_ID':'X0022'}

if __name__ == '__main__':
	#upload_md('animal', test_dict, force_append=True)
	append_md('site.json', {'new5':'data5c'})