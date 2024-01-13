from datetime import date, time, datetime
from metadata_upload import upload_md

def save_sac(hour, minute, animal_id):
	today = date.today()
	sac_time = time(hour=hour, minute=minute)
	sac_time = datetime.combine(today, sac_time)
	sac_time = sac_time.isoformat()
	print (sac_time)
	animal_dict = {'animal_ID': animal_id,
	'date_sac':sac_time}
	upload_md('animal', animal_dict, force_append=True)

if __name__ == '__main__':
	save_sac(4, 21, "A41252")