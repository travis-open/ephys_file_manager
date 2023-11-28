import pyabf
from pathlib import Path
from metadata_upload import *

def parse_abf_in_dir(directory, site_ID=None):
	abf_list=Path(directory).glob('*abf')
	if not abf_list:
		print("no abf files found")
	else:
		for f in abf_list:
			#print (f)
			abf=pyabf.ABF(f, loadData=False)
			#print (abf.protocol)
			AD_chan = abf.adcNames
			HS_list=[]
			HS0_checklist=['Vm_primary', 'Im_primary']
			HS1_checklist=['Vm_p2', 'Im_p2']
			if any(item in AD_chan for item in HS0_checklist):
				HS_list.append(0)
			if any(item in AD_chan for item in HS1_checklist):
				HS_list.append(1)
			#print (abf.adcNames)
			#print (HS_list)
			
			abf_dict={
			'full_path':str(f.resolve()),
			'protocol':abf.protocol,
			'site_ID':site_ID,
			'HS_recorded':str(HS_list)
			}
			upload_md('abf', abf_dict, force_append=True)
			#print (abf_dict)


if __name__ == '__main__':
	parse_abf_in_dir(r"C:\pClampData")
