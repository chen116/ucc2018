import sys
import dom0_comm
import xen_interface
import threading
import time
import pprint
import res_alloc
from pyxs import Client

with open("data.txt", "w") as myfile:
	myfile.write("")

import argparse
ap = argparse.ArgumentParser()
ap.add_argument("-f", "--fps", type=float, default=10, help="target fps")
ap.add_argument("-a", "--algo", type=int, default=3, help="algorithm for both")
ap.add_argument("-s", "--static-alloc", type=int, default=20, help="static utilization percentage")
args = vars(ap.parse_args())


monitoring_items = ["heart_rate","frame_size"]
# monitoring_domU = (args["domUs"]).split(',')
monitoring_domU = ["VM1_id_placeholder","VM2_id_placeholder"]
dummy_domU = ["d1_id_placeholder","d2_id_placeholder"]

# find correct domUs id
with Client(xen_bus_path="/dev/xen/xenbus") as c:
	domu_ids=[]
	all_domuid_ids = []
	for uid in c.list('/local/domain'.encode()):
		all_domuid_ids.append(uid.decode())
	all_domuid_ids.pop(0)
	for uid in all_domuid_ids:
		name_path = ("/local/domain/"+uid+"/name").encode()
		if c[name_path].decode() == "VM1":
			monitoring_domU[0] = uid
		if c[name_path].decode() == "VM2":
			monitoring_domU[1] = uid
		if c[name_path].decode() == "d1":
			dummy_domU[0] = uid
		if c[name_path].decode() == "d2":
			dummy_domU[1] = uid


# create xenstore entry for DomU to write data
domUs = dom0_comm.Dom0(monitoring_items,monitoring_domU)

timeslice_us=10000#args["timeslice"]
min_heart_rate = float(args["fps"])
max_heart_rate = float(args["fps"])*1.5


# each thread monitor a VM
class MonitorThread(threading.Thread):
	def __init__(self, threadLock,shared_data,domuid,rtxen_or_credit,timeslice_us,min_heart_rate,max_heart_rate,keys=['test'],base_path='/local/domain'):
		threading.Thread.__init__(self)
		self.domuid=(domuid)
		self.other_domuid=dummy_domU[0]
		if self.domuid==monitoring_domU[1]:
			self.other_domuid=dummy_domU[1]

		self.algo = args["algo"]
		self.keys=keys
		self.base_path=base_path
		self.threadLock=threadLock
		self.shared_data=shared_data
		self.timeslice_us = timeslice_us
		self.rtxen_or_credit = rtxen_or_credit 
		self.allocMod = res_alloc.ResourceAllocation(args["static_alloc"],timeslice_us,min_heart_rate,max_heart_rate,self.algo,self.domuid,self.other_domuid,self.shared_data,rtxen_or_credit)

	def run(self):
		with Client(unix_socket_path="/var/run/xenstored/socket_ro") as c:
			# watch the xenstore entries and perform different functions accodingly 
			m = c.monitor()
			for key in self.keys:
				tmp_key_path = (self.base_path+'/'+self.domuid+'/'+key).encode()
				token = (key).encode()
				m.watch(tmp_key_path,token)
			msg=""
			while msg!='done':
				path,token=next(m.wait())
				msg=c.read(path).decode()
				self.threadLock.acquire()
				if "frame_size" in path.decode():
					if msg.isdigit():
						with open("data.txt", "a") as myfile:
							myfile.write(self.domuid+" "+(msg)+" frame size"+ " "+str(time.time())+"\n")
				if "heart_rate" in path.decode():
					heart_rate=-1
					try :
						heart_rate = float(msg)
						self.res_allocat(heart_rate)	
					except:
						heart_rate=-1				
				self.threadLock.release()
		return

	def res_allocat(self,heart_rate):

		# get current cpu resource
		cur_bw = 0
		myinfo = self.shared_data[self.domuid]
		if self.rtxen_or_credit=="rtxen":
			for vcpu in myinfo:
				if vcpu['pcpu']!=-1:
					cur_bw=int(vcpu['b'])
		elif self.rtxen_or_credit=="credit":
			for vcpu in myinfo:
				if vcpu['pcpu']!=-1:
					cur_bw=int(vcpu['w'])
		
		# calculate next cpu resource assignment
		cur_bw = self.allocMod.exec_allocation(heart_rate,cur_bw)
		other_cur_bw = self.timeslice_us - cur_bw

		# assign the new cpu resource to VM
		other_info = self.shared_data[self.other_domuid]
		if self.rtxen_or_credit=="rtxen":
			for vcpu in other_info:
				if vcpu['pcpu']!=-1:
					vcpu['b']=other_cur_bw
			for vcpu in myinfo:
				if vcpu['pcpu']!=-1:
					vcpu['b']=cur_bw
			xen_interface.sched_rtds(self.domuid,self.timeslice_us,cur_bw,[])
			xen_interface.sched_rtds(self.other_domuid,self.timeslice_us,other_cur_bw,[])
		elif self.rtxen_or_credit=="credit":
			for vcpu in other_info:
				if vcpu['pcpu']!=-1:
					vcpu['w']=other_cur_bw
			for vcpu in myinfo:
				if vcpu['pcpu']!=-1:
					vcpu['w']=cur_bw
			xen_interface.sched_credit(self.domuid,cur_bw)
			xen_interface.sched_credit(self.other_domuid,other_cur_bw)

		# write data to data.txt for realtime_plot.py for visulization
		time_now=str(time.time())
		info = self.domuid+" "+str(heart_rate)+" hr "+time_now+"\n"
		place_holder_for_graph = " x x x x x "
		info += self.domuid + " " +str(cur_bw/self.timeslice_us) + place_holder_for_graph+time_now
		with open("data.txt", "a") as myfile:
			myfile.write(info+"\n")
		return





# initializing data and setup inital cpu assignment
threadLock = threading.Lock()
threads = []
shared_data = xen_interface.get_global_info()
for i in range(len(monitoring_domU)):
	if monitoring_domU[i] in shared_data['rtxen']:
		xen_interface.sched_rtds(monitoring_domU[i],timeslice_us,timeslice_us/2,[])
		xen_interface.sched_rtds(dummy_domU[i],timeslice_us,timeslice_us/2,[])
	if monitoring_domU[i] in shared_data['credit']:
		xen_interface.sched_credit(monitoring_domU[i],timeslice_us/2)
		xen_interface.sched_credit(dummy_domU[i],timeslice_us/2)


# stdout ready status to inform user
shared_data = xen_interface.get_global_info()
pp = pprint.PrettyPrinter(indent=2)
pp.pprint(shared_data)
print('')
print('Experiment 1: RT-Xen vs Credit')
print('monitoring:')
for i in range(2):
	vmstr = 'VM'+str(i+1)
	if monitoring_domU[i] in shared_data['rtxen']:
		print("	rtxen",vmstr,'with domU ID=',monitoring_domU[i],", dummy domU d1 with ID=",dummy_domU[i])
	else:
		print("	credit",vmstr,'with domU ID=',monitoring_domU[i],", dummy domU d2 with ID=",dummy_domU[i])

# write out some init data for realtime_plot.py for visulization and vid_feed.py for fps
with open("misc.txt", "w") as myfile:
	myfile.write("minHeartRate "+str(args["fps"])+"\n")
	myfile.write("maxHeartRate "+str(args["fps"])+"\n")
	myfile.write("timeslice_us "+str(timeslice_us/1000)+"\n")
	myfile.write("VM1 "+str(monitoring_domU[0])+"\n")







# start monitoring thread for each VM
for domuid in monitoring_domU:
	rtxen_or_credit="rtxen"
	if domuid in shared_data['credit']:
		rtxen_or_credit="credit"
	tmp_thread = MonitorThread(threadLock,shared_data,domuid,rtxen_or_credit,timeslice_us,min_heart_rate,max_heart_rate, monitoring_items)
	tmp_thread.start()
	threads.append(tmp_thread)




# Wait for all MonitorThreads to complete
threads_cnt=0
for t in threads:
	t.join()
	threads_cnt+=1
print('Final domUs info:')
print("Exiting the Monitor, total",threads_cnt,"monitoring threads")
print('Exiting Experiment 1: RT-Xen vs Credit')

