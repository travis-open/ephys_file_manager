#pragma TextEncoding = "UTF-8"
#pragma rtGlobals=3				// Use modern global access method and strict wave access
#pragma DefaultTab={3,20,4}		// Set default tab width in Igor Pro 9 and later



Function Setup()
	ServerSide()
	make_received_data_folder()

end





Function ServerSide()
//from zmq demo experiment. Need to run for reliable zmq communication with python
	zeromq_stop()
	zeromq_server_bind("tcp://127.0.0.1:5555")
	//zeromq_pub_bind("tcp://127.0.0.1:6666")
	zeromq_handler_start()
End


	
	

Function getNextSweep() //return next sweep to be associated with photostim
	controlinfo/W=Dev1 setvar_sweep
	variable nextsweep=v_value
	//print (nextsweep)
	return nextsweep
end

Function isDAQhappening() //return 0 if acquisition is not taking place
	NVAR runmode = $GetDataAcqRunMode("Dev1")
	return runmode
end


Function startDAQ()
	variable runmode=isDAQhappening()
	if (runmode==0)
		PGC_SetAndActivateControl("Dev1","DataAcquireButton")
		return 1
	else
		print "DAQ already running, sweep not started"
		return 0
	endif
end

Function make_received_data_folder()
	DFREF saveDFR = GetDataFolderDFR()	
	if(DataFolderExists("root:received_data:")==0)
		newdatafolder root:received_data
		
		make/o/n=0/L root:received_data:dmd_sweeps
		make/o/n=0/T root:received_data:dmd_stimset
		make/o/n=0/T root:received_data:dmd_route
	endif
	SetDataFolder saveDFR
end

Function/S make_sweep_folder(sweep_num)
	variable sweep_num
	DFREF saveDFR = GetDataFolderDFR()
	string df_name = "root:received_data:"+"X_"+num2str(sweep_num)
	if(DataFolderExists(df_name)==0)
		newdatafolder $df_name
	endif
	SetDataFolder saveDFR
	return df_name
end



Function store_dmd_stimset_name(stimset_name, route_name, sweep_number)
	string stimset_name, route_name
	variable sweep_number
	DFREF saveDFR = GetDataFolderDFR()
	wave/T stimsets = root:received_data:dmd_stimset
	wave/T routes = root:received_data:dmd_route
	wave sweeps = root:received_data:dmd_sweeps
	InsertPoints/M=0 0, 1, stimsets
	InsertPoints/M=0/V=(sweep_number) 0, 1, sweeps
	InsertPoints/M=0 0, 1, routes
	stimsets[0] = stimset_name
	routes[0] = route_name
	

	SetDataFolder saveDFR
end

Function store_photostim_order(string_input, sweep_num)
	string string_input
	variable sweep_num
	DFREF saveDFR = GetDataFolderDFR()
	string sweep_folder = make_sweep_folder(sweep_num)
	SetDataFolder sweep_folder
	Make/o/T/N=(ItemsInList(string_input, ";")) photostim_sequence
	photostim_sequence = StringFromList(p, string_input, ";")
	SetDataFolder saveDFR
end

Function generic_dmd_prep(sweep_number, stimset_name, route, route_name, sweep_reps)
	variable sweep_number, sweep_reps
	string stimset_name, route, route_name
	variable sweep_i
	for (sweep_i=sweep_number; sweep_i<sweep_number+sweep_reps; sweep_i+=1)
		store_dmd_stimset_name(stimset_name, route_name, sweep_i)
		store_photostim_order(route, sweep_i)
	endfor
	PGC_setandactivatecontrol("Dev1", "Check_DataAcq_Indexing", val=0) //no indexing
	PGC_setandactivatecontrol("Dev1", "Check_DataAcq1_DistribDaq", val=0) //no distribution
	PGC_setAndActivateControl("Dev1", "SetVar_DataAcq_SetRepeats", val=sweep_reps)
end

Function dmd_sequence_ephys_prep(sweep_number, stimset_name, route, route_name, sweep_reps)
	variable sweep_number, sweep_reps
	string stimset_name, route, route_name
	generic_dmd_prep(sweep_number, stimset_name, route, route_name, sweep_reps)
	//set TTL channels
	PGC_setandactivatecontrol("Dev1", "Check_TTL_00", val=1) 
	PGC_setandactivatecontrol("Dev1", "Check_TTL_01", val=1)
	string all_TTLs=ST_GetStimsetList(channelType = CHANNEL_TYPE_TTL)
	variable TTL_num = whichListItem("ttlRep120_TTL_0", all_TTLs)+1
	PGC_setandactivatecontrol("Dev1", "Wave_TTL_00", val=TTL_num)
	PGC_setandactivatecontrol("Dev1", "Wave_TTL_01", val=TTL_num)
	//set DA channels
	string all_dacs = ST_GetStimsetList(channelType = CHANNEL_TYPE_DAC)
	variable stim_set_num = whichListItem("hold1s_DA_0", all_dacs)+1
	PGC_setandactivatecontrol("Dev1", "Wave_DA_00", val=stim_set_num) 
	PGC_setandactivatecontrol("Dev1", "Wave_DA_01", val=stim_set_num) 

end

Function dmd_frame_ephys_prep(sweep_number, stimset_name, route, route_name, sweep_reps)
	variable sweep_number, sweep_reps
	string stimset_name, route, route_name
	generic_dmd_prep(sweep_number, stimset_name, route, route_name, sweep_reps)
	PGC_setandactivatecontrol("Dev1", "Check_TTL_00", val=0) //don't trigger changes in frame
	PGC_setandactivatecontrol("Dev1", "Check_TTL_01", val=1)
	string all_TTLs=ST_GetStimsetList(channelType = CHANNEL_TYPE_TTL)
	variable TTL_num = whichListItem("sPulse1sPre_TTL_0", all_TTLs)+1
	PGC_setandactivatecontrol("Dev1", "Wave_TTL_01", val=TTL_num)
	//set DA channels
	string all_dacs = ST_GetStimsetList(channelType = CHANNEL_TYPE_DAC)
	variable stim_set_num = whichListItem("hold1s_DA_0", all_dacs)+1
	PGC_setandactivatecontrol("Dev1", "Wave_DA_00", val=stim_set_num) 
	PGC_setandactivatecontrol("Dev1", "Wave_DA_01", val=stim_set_num) 
end
