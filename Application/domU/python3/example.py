# example app with pacer
#to run: starts: monitor_singleVM.py in Dom0 first, then exec this file on VM1
# create heartbeat
import heartbeat
window_size_hr=5
sharedmem_id_for_heartbeat = 1024
buffer_depth = 100
log_name = "heartbeat.log"
min_heart_rate = 10 # this is from the original heartbeat module, not used in Pacer
max_heart_rate = 100 # this is from the original heartbeat module, not used in Pacer
hb = heartbeat.Heartbeat(sharedmem_id_for_heartbeat,window_size_hr,buffer_depth,log_name,min_heart_rate,max_heart_rate)

# establish communication with Dom0
import domU_comm
monitoring_items = ["heart_rate"]
comm = domU_comm.DomU(monitoring_items)


# matmult app
import time
import numpy as np
matsize = 500
a= np.random.rand(matsize, matsize)
b= np.random.rand(matsize, matsize)	

# loop

for i in range(100):

	# processing
	c= np.matmul(b,a.T)


	# record heartbeat
	hb.heartbeat_beat()
	instant_heartrate = hb.get_instant_heartrate()
	print("get_instant_heartrate:",instant_heartrate)
	# send heart rate to Dom0
	comm.write("heart_rate", instant_heartrate)




comm.write("heart_rate", "done")
hb.heartbeat_finish()