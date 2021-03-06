
import apid
import time
# Resouce allocation helper for Pacer monitor thread
class ResourceAllocation:
	def __init__(self,static_alloc, timeslice_us,min_heart_rate,max_heart_rate,algo,domuid,other_domuid,shared_data,rtxen_or_credit):
		self.static_alloc = static_alloc
		self.timeslice_us = timeslice_us
		self.mid_heart_rate=(min_heart_rate+max_heart_rate)/2
		self.min_heart_rate=min_heart_rate
		self.max_heart_rate=max_heart_rate
		self.pid = apid.AdapPID(self.mid_heart_rate,1,min_heart_rate,max_heart_rate)
		self.algo = algo
		self.target_reached_cnt = 0
		self.step_size = int(timeslice_us * 0.01)
		self.shared_data = shared_data
		self.domuid = domuid
		self.other_domuid = other_domuid
		self.rtxen_or_credit = rtxen_or_credit

	# calcute the cpu resource needed base on current heartbeat
	def exec_allocation(self,heart_rate,cur_bw):

		if self.algo==0:
			# static allocation
			cur_bw = int(self.timeslice_us*self.static_alloc/100)


		elif self.algo==1:
			# linear -- slowly decrease to target value once hear rate is abover min_heart_rate
			if(heart_rate<self.min_heart_rate):
				if cur_bw<self.timeslice_us-self.step_size:
					cur_bw+=self.step_size
			if(heart_rate>self.max_heart_rate):
				if cur_bw>self.step_size:
					cur_bw-=self.step_size
			if heart_rate > self.min_heart_rate:
				self.target_reached_cnt+=1
				if self.target_reached_cnt==20:
					self.target_reached_cnt-=10
					if cur_bw>self.step_size:
						cur_bw-=self.step_size
			else:
				self.target_reached_cnt=0
			cur_bw=int(cur_bw)


		elif self.algo==2:
			# amid - target to stay at single value(mid_heart_rate)
			alpha=1
			beta=.9
			free = self.timeslice_us-cur_bw
			if(heart_rate<self.mid_heart_rate):
				if cur_bw<self.timeslice_us-self.step_size:
					free=free*beta
					cur_bw=self.timeslice_us-free
				else:
					cur_bw=self.timeslice_us-self.step_size
			if(heart_rate>self.mid_heart_rate):
				if cur_bw>self.step_size:
					free+=alpha*self.step_size
					cur_bw=self.timeslice_us-free
			cur_bw=int(cur_bw)

		elif self.algo==3:
			# amid_range - target to stay at a range [min_heart_rate,max_heart_rate]
			alpha=3.5
			beta=.95
			free = self.timeslice_us-cur_bw
			if(heart_rate<self.min_heart_rate):
				if cur_bw<self.timeslice_us-self.step_size:
					free=free*beta
					cur_bw=self.timeslice_us-free
				else:
					cur_bw=self.timeslice_us-self.step_size
			if(heart_rate>self.max_heart_rate):
				if cur_bw>self.step_size:
					free+=alpha*self.step_size
					cur_bw=self.timeslice_us-free
			cur_bw=int(cur_bw)


		elif self.algo==4:
			# apid algo - - target to stay at single value(mid_heart_rate)
			output = self.pid.update(heart_rate)
			# output+=self.timeslice_us/2
			if self.pid.start>0:
				tmp_cur_bw = output+cur_bw #int(output*cur_bw+cur_bw)-int(output*cur_bw+cur_bw)%100
				if tmp_cur_bw>=self.timeslice_us-self.step_size: #dummy
					cur_bw=self.timeslice_us-self.step_size
				elif tmp_cur_bw<=self.step_size:#self.timeslice_us/3:
					cur_bw=self.step_size#int(self.timeslice_us/3)
				else:
					cur_bw=tmp_cur_bw
			cur_bw=int(cur_bw)




		# force boudary if violated
		if cur_bw <= self.step_size :
			cur_bw = self.step_size
		if cur_bw >= self.timeslice_us-self.step_size:
			cur_bw = self.timeslice_us-self.step_size

		return(int(cur_bw))

	# force sharing of limited CPU resource between 2VMs
	def exec_stride_sharing(self,cur_bw,now_time):
		allowed_processing_time_per_contention=3

		other_info = self.shared_data[self.other_domuid]
		if self.rtxen_or_credit=="rtxen":
			for vcpu in other_info:
				if vcpu['pcpu']!=-1:
					other_cur_bw=vcpu['b']		
		elif self.rtxen_or_credit=="credit":
			for vcpu in other_info:
				if vcpu['pcpu']!=-1:
					other_cur_bw=vcpu['w']

		if cur_bw+other_cur_bw>self.timeslice_us:
			domu_index_in_pass_val = 0
			if self.domuid>self.other_domuid:
				domu_index_in_pass_val = 1
			my_pass_val = self.shared_data['pass_val'][domu_index_in_pass_val]
			other_pass_val = self.shared_data['pass_val'][(domu_index_in_pass_val+1)%2]
			last_time = self.shared_data['last_time_val']
			# now_time = time.time()
			if last_time==0:
				last_time = now_time
				self.shared_data['last_time_val'] = now_time
			self.shared_data["contention_time_passed"]+=now_time-last_time
			self.shared_data['last_time_val'] = now_time
			if my_pass_val<=other_pass_val:
				other_cur_bw=self.timeslice_us-cur_bw
			else:
				cur_bw=self.timeslice_us-other_cur_bw
				self.pid.reset()
			if self.shared_data["contention_time_passed"]>=allowed_processing_time_per_contention:
				self.shared_data["contention_time_passed"]=0
				if my_pass_val<=other_pass_val:
					self.shared_data['pass_val'][domu_index_in_pass_val]+=self.shared_data['stride_val'][domu_index_in_pass_val]
				else:
					self.shared_data['pass_val'][(domu_index_in_pass_val+1)%2]+=self.shared_data['stride_val'][(domu_index_in_pass_val+1)%2]
				with open("data.txt", "a") as myfile:
					myfile.write(self.domuid+" "+self.domuid+" stride turnover len 6"+ " "+str(now_time)+"\n")						
		else:
			self.shared_data['last_time_val'] = now_time#time.time()
		return (cur_bw,other_cur_bw)

