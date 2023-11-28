from pycromanager import Core
import tifffile
import json
import time


core = Core()

manual_meta_dict={'objective':'40X','mag':'2.0X', 'channel':'TL'}

def snap_and_save(core, saveloc=):#, manual_meta_dict={}):
	core.snap_image()
	tagged_image=core.get_tagged_image()
	image_height = tagged_image.tags['Height']
	image_width = tagged_image.tags['Width']
	image = tagged_image.pix.reshape((image_height, image_width))
	md = tagged_image.tags
	
	filename="img_"+str(int(time.time()))
	tfile=filename+'.tif'
	jsonfile=filename+'.json'
	#tifffile.imwrite('test8.ome.tif', image, metadata=md)#{"important":"detail"})
	tifffile.imwrite(tfile, image)
	with open(jsonfile, 'a') as f:
		f.write(json.dumps(md, indent=4))
		f.close()
snap_and_save(core)


