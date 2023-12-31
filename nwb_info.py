from neuroanalysis.data.loaders.mies_dataset_loader import MiesNwbLoader
from neuroanalysis.data.dataset import Dataset
import numpy as np
import glob
import os
from pathlib import Path
from metadata_upload import *
import json


def pull_hs_stimset(nwbfilename):
    dataset = Dataset(loader=MiesNwbLoader(nwbfilename))
    stim_list=set()
    HS_list=set()
    for rec in dataset.all_recordings:
        if rec.device_type=='MultiClamp 700':
            HS_list.add(rec.device_id)
            try:
                s=rec.stimulus.description
            except:
                s="unknown"
            stim_list.add(s)
    return {"HS_recorded":str(list(HS_list)), "protocols":str(list(stim_list))}

def process_nwb(nwbfilename):
    meta_dict=pull_hs_stimset(nwbfilename)
    full_path=str(Path(nwbfilename).absolute())
    meta_dict['full_path']=full_path
    try:
        with open('site.json') as json_file:
            site_dict=json.load(json_file)
            site_ID = site_dict['site_ID']
    except:
        site_ID = "unknown"
    meta_dict['site_ID']=site_ID
    upload_md('nwb', meta_dict, force_append=True)

def process_nwb_in_dir():
    directory = os.getcwd()
    nwb_list=Path(directory).glob('*.nwb')
    if not nwb_list:
        print("no nwb files found")
    else:
        for f in nwb_list:
            process_nwb(f)

if __name__ == '__main__':
    #hs_list, stim_list=pull_hs_stimset('basic_nwb_v2.nwb')
    #print(hs_list, stim_list)
    process_nwb_in_dir()