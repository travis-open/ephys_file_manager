from pydantic import BaseModel, Field, AliasChoices
from datetime import date as date_type
from datetime import datetime
from typing import Optional
from enum import Enum
from pathlib import Path
from metadata_upload import upload_md


class Animal(BaseModel):
	animal_id: str = Field(..., title="Animal ID")
	species: str = Field(..., title="Species")
	sex: Optional[str] = Field(None, title="Sex")
	date_of_birth: Optional[date_type] = Field(None, title="Date of birth")
	genotype: Optional[str] = Field(None, title="Species")

	def gs_upload(self):
		upload_md('animal', self.dict(), force_append=True)

	
class SliceRecDay(BaseModel):
	animal_id: str = Field(..., title="Animal ID")
	animal: Optional[Animal] = Field(None, title="Animal")
	project: Optional[str] = Field(None, title="Project")
	rig_id: str = Field("slice_rig_1", title="Rig ID")
	date: date_type = Field(..., title="Date of recording")
	day_id: str = Field(..., title="Recording day ID")
	day_directory: Optional[Path] = Field(None, title="directory of Day ephys data")

	def gs_upload(self):
		upload_md('day', self.dict(), col_match='day_id')


class BrainSlice(BaseModel):
	animal_id: str = Field(..., title="Animal ID")
	day_id: str = Field(..., title="Recording day ID")
	slice_id: str = Field(..., title="Slice ID")
	slice_rec_day: Optional[SliceRecDay] = Field(None, title="Slice recording day")
	slice_rig_time: Optional[datetime] = Field(None, title="Time of slice on rig")
	slice_directory: Optional[Path] = Field(None, title="directory of Slice ephys data")
	fixation_well_id: str = Field("not fixed", title="Fixation well ID")
	fixed_orientation: Optional[str] = Field("unknown", title="Fixed slice orientation")
	plane: Optional[str] = Field(None, title="Anatomical plane")

	def gs_upload(self):
		upload_md('slice', self.dict(), col_match='slice_id')


class RecordingSite(BaseModel):
	site_id: str = Field(..., title="Site ID")
	slice_id: str = Field(..., title="Slice ID")
	brain_slice: Optional[BrainSlice] = Field(None, title="Brain slice")
	site_directory: Optional[Path] = Field(None, title="directory of Site ephys data")
	region: Optional[str] = Field(None, title="Region of recording")
	external_solution: str = Field(..., title="External recording solution")
	def gs_upload(self):
		upload_md('site', self.dict(), col_match='site_id')

class RecordedCell(BaseModel):
	cell_id: str = Field(..., title="Cell ID")
	site_id: str = Field(..., title="Site ID")
	site_directory: Optional[Path] = Field(None, title="directory of Site ephys data")
	recording_site: Optional[RecordingSite] = Field(None, title="Recording site")
	headstage: int = Field(..., title="Headstage")
	target_region: Optional[str] = Field(None, title="Targeted region or structure", 
		validation_alias=AliasChoices('target_region', 'subregion_0', 'subregion_1'))
	pipette_solution: str = Field(..., title="Pipette solution",
		validation_alias=AliasChoices('pipette_solution', 'pip_sol_0', 'pip_sol_1'))
	reporter_status: Optional[str] = Field(None, title="Status of genetic reporter expression",)
	cell_class: Optional[str] = Field(None, title="Presumed cell class")

	def gs_upload(self):
		upload_md('cell', self.dict(), col_match='cell_id')






