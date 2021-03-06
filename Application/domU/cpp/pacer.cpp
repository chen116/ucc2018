#include <stdio.h>
#ifdef __cplusplus
extern "C" {
#endif
#include <xenstore.h>
#include "comm.h"
#ifdef __cplusplus
}
#endif


#include <stdlib.h>
#include <string.h>
#include <heartbeats/heartbeat.h>
#include <iostream>
#include <map>
using namespace std;

// C function declarations
extern "C" {
	char * xenstore_read(struct xs_handle*  ,xs_transaction_t , const char*  , unsigned int * );
	void xenstore_write(struct xs_handle *, xs_transaction_t , const char *, const void *);
	int xenstore_getDomid();
}

#include "pacer.h"
static const int64_t heartbeat_buf_depth = 1000;
static const char* heartbeat_log_file ="heartbeat.log"; //heartbeat information file
static const int64_t heartbeat_min_target = 100; // heartbeat module, not used in pacer
static const int64_t heartbeat_max_target = 1000; // heartbeat module, not used in pacer

// constructor: get xenstore handle with domUid, initiates default heart rate path in xenstore
Pacer::Pacer()
{
 	domid = xenstore_getDomid();
 	xs = xs_daemon_open();
	heart_rate_path = xs_get_domain_path(xs, domid);
	heart_rate_path = (char*)realloc(heart_rate_path, strlen(heart_rate_path) + strlen("/heart_rate") + 1);
	strcat(heart_rate_path, "/heart_rate");
}

// initiate heartbeat with user defined heartrate window size
void Pacer::setWindowSize(const int64_t heartbeat_win_size)
{
	heart = heartbeat_init(heartbeat_win_size, heartbeat_buf_depth, heartbeat_log_file, heartbeat_min_target, heartbeat_max_target);
}
// destructor
Pacer::~Pacer() {  


	// signaling dom0 monitor the application is finished
	xenstore_write(xs, th, heart_rate_path, "done");

	// clean up heartbeat and xenstore instance
	delete heart_rate_path;
	heartbeat_finish(heart);
	xs_daemon_close(xs);
	for (map<char *,char *>::iterator it=paths.begin(); it!=paths.end(); ++it)
	{
		delete it->second;
		paths.erase(it);
	}

}  
// read a paricular item from xenstore
char* Pacer::readItem(char * item)
{
	unsigned int len;
	for (map<char *,char *>::iterator it=paths.begin(); it!=paths.end(); ++it)
	{
    	if (strcmp(it->first,item)==0) return xenstore_read(xs,th,it->second,&len);
	}
	return (char*)"not found";
}

// record a heartbeat
void Pacer::beat()
{
	heartbeat(heart,1);
	return;
}
// write a instant heartbeat to xenstore
void Pacer::writeInstantHeartRate()
{
	char buffer[16];
	int ret = snprintf(buffer, sizeof buffer, "%f", hb_get_instant_rate(heart));
	xenstore_write(xs, th, heart_rate_path, buffer);
	return;
}
// write a window heartbeat to xenstore
void Pacer::writeWindowHeartRate()
{
	char buffer[16];
	int ret = snprintf(buffer, sizeof buffer, "%f", hb_get_windowed_rate(heart));
	xenstore_write(xs, th, heart_rate_path, buffer);
	return;
}
// write a global heartbeat to xenstore
void Pacer::writeGlobalHeartRate()
{
	char buffer[16];
	int ret = snprintf(buffer, sizeof buffer, "%f", hb_get_global_rate(heart));
	xenstore_write(xs, th, heart_rate_path, buffer);
	return;
}
// read hear_rate entry from xenstore
char * Pacer::readHeartRate()
{
	unsigned int len;
	return xenstore_read(xs,th,heart_rate_path,&len);
}
// write a particular item to xenstore
void Pacer::writeItem(char * item, const char * content)
{
	unsigned int len;
	for (map<char *,char *>::iterator it=paths.begin(); it!=paths.end(); ++it)
	{
    	if (strcmp(it->first,item)==0)
    	{
    		xenstore_write(xs, th, it->second, content);
    		return;
    	}
	}
	return;
}
// create a item entry in xenstore
void Pacer::setItem(char * item)
{
	char *path;
	path = xs_get_domain_path(xs, domid);
	path = (char*)realloc(path, strlen(path) + strlen(item) + 2);
	strcat(path, "/");
	strcat(path, item);
	paths[item]=path;
}
// print out all item's entry and path to xenstore 
void Pacer::getItems()
{
	for (map<char *,char *>::iterator it=paths.begin(); it!=paths.end(); ++it)
    cout << it->first << " => " << it->second << '\n';
}

int Pacer::getDomid()
{
  return domid;
}