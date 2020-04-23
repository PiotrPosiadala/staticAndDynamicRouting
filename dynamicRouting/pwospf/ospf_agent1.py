import sys
from scapy.all import *
import scapy_ospf
import threading
import time
import dijkstra

###---------------------------------###
### --------- CONFIG DATA --------- ###
###---------------------------------###
OSPF_VERSION = "2"
AREA_ID = "0.0.0.0"
LSUINT = 30
HELLOINT = 10
NEIGHBOR_TIMEOUT = 3*HELLOINT
ROUTER_INTERFACES =[
    { "name": "s1-eth0",    "address":"192.168.1.1",     "mask":"24",   "subnet":"192.168.1.0",   "mac":"00:00:00:00:01:00",  "neighbor_ip":"192.168.1.2"},
    { "name": "s1-eth1",    "address":"192.168.11.1",    "mask":"24",   "subnet":"192.168.11.0",   "mac":"00:00:00:00:01:01",  "neighbor_ip":"192.168.11.2"},
    { "name": "s1-eth2",    "address":"192.168.12.1",    "mask":"24",   "subnet":"192.168.12.0",   "mac":"00:00:00:00:01:02",  "neighbor_ip":"192.168.12.2"}]
ROUTER_CP_INTERFACE = {"name": "s1-eth4",    "address":"192.168.101.2",     "mask":"24",   "mac":"00:00:00:00:01:04"}
ROUTER_ID = ROUTER_INTERFACES[0].get("address")
ALLSPFRouters = "224.0.0.5"
AUTH_TYPE = "0"

###---------------------------------###
### --------- DEFINITIONS --------- ###
###---------------------------------###
def log(msg):
    print("{}   {}".format(time.strftime('%H:%M:%S'),msg))

class OspfInterface:
    def __init__(self, name, ip_address, mac, subnet, mask = "24",  helloint = HELLOINT, neighbor_ip = "0", neighbor_id = "0"):
        self.name = name
        self.ip_address = ip_address
        self.mac = mac
        self.mask = mask
        self.subnet = subnet
        self.helloint = helloint
        self.neighbor_ip = neighbor_ip
        self.neighbor_id = neighbor_id

class RouterClass:
    router_id = ROUTER_ID
    area_id = AREA_ID
    lsuint = LSUINT
    ospf_interfaces = []
    def __init__(self, router_interfaces):
        for interface in router_interfaces:
            self.ospf_interfaces.append(OspfInterface(
                name = interface["name"],
                ip_address = interface["address"],
                mac = interface["mac"],
                mask = interface["mask"],
                subnet = interface["subnet"],
                helloint = HELLOINT,
                neighbor_ip = "0",
                neighbor_id = "0"))
            print("{}: OSPF Interface = {} generated!".format(time.strftime('%H:%M:%S'), interface["name"]))

class DatabaseClass(list):
    def insert(self, hello):
        log("Database insert called")
        if hello not in self:
            self.append(hello)
            log("Hello appended to Database")
    def remove(self, hello):
        index_to_remove = self.index(hello)
        self.pop(index_to_remove)

class OspfHelloThread(threading.Thread):
    def __init__(self, router, *args, **kwargs):
        super(OspfHelloThread, self).__init__(*args, **kwargs)
        self._stop_event = threading.Event()
        self.router = router
    def run(self):
        while(True):
            if self.stopped():
                return
            self.generate_hello()
            time.sleep(HELLOINT)
    def stop(self):
        self._stop_event.set()
    def stopped(self):
        return self._stop_event.is_set()
    def generate_hello(self): #TODO
        for i in self.router.ospf_interfaces:
            p = scapy_ospf.Ether(src = ROUTER_CP_INTERFACE.get("mac"), dst = i.mac)/IP(src = i.ip_address, dst = i.neighbor_ip)/scapy_ospf.OSPF_Hdr(src=ROUTER_ID,area=AREA_ID)/scapy_ospf.OSPF_Hello()
            log("Hello generated")
            p.show()
            sendp(p, iface=i.name)
            log("Hello sent")
            
class OspfLSUThread(threading.Thread):
    def __init__(self, router, *args, **kwargs):
            super(OspfLSUThread, self).__init__(*args, **kwargs)
            self._stop_event = threading.Event()
            self.router = router
    def run(self):
        time.sleep(3)
        while(True):
            if self.stopped():
                return
            self.generate_lsu()
            time.sleep(LSUINT)
    def stop(self):
        self._stop_event.set()
    def stopped(self):
        return self._stop_event.is_set()
    def generate_lsu(self):
            for i in self.router.ospf_interfaces: #TODO
                p = scapy_ospf.Ether(src = ROUTER_CP_INTERFACE.get("mac"), dst = i.mac)/IP(src = i.ip_address, dst = i.neighbor_ip)/scapy_ospf.OSPF_Hdr(src=ROUTER_ID,area=AREA_ID)/scapy_ospf.OSPF_LSUpd()
                log("LSU generated")
                for k in self.router.ospf_interfaces:
                    if k is not i:
                        if k.mask == "24":
                            temp_mask = "255.255.255.0"
                        else
                            temp_mask = mask
                        p[scapy_ospf.OSPF_LSUpd].lsalist.append(scapy_ospf.OSPF_Network_LSA(id=k.subnet,adrouter=self.router.router_id, mask = k.mask))
                        log("LSA Appended")
                p.show()
                sendp(p, iface=i.name)
                log("LSU sent")


class OspfSnifferThread(threading.Thread):
    def __init__(self, Database, *args, **kwargs):
        super(OspfSnifferThread, self).__init__(*args, **kwargs)
        self._stop_event = threading.Event()
        self.Database_Topo = Database
    def run(self):
        t = AsyncSniffer(iface=ROUTER_CP_INTERFACE.get("name"), prn=self.process_packet)
        t.start()
        while(True):
            if self.stopped():
                t.stop()
                return
            time.sleep(0.5)
    def stop(self):
        self._stop_event.set()
    def stopped(self):
        return self._stop_event.is_set()
    def process_packet(self, packet):
        if(self.validate_packet(packet)):
            log("Packet Validated")
            packet.show()
            msg_router_id = packet[scapy_ospf.OSPF_Hdr].src
            msg_hello_int = packet[scapy_ospf.OSPF_Hello].hellointerval
            msg = {"router_id" : msg_router_id, "hello_int" : msg_hello_int}
            self.Database_Topo.insert(msg)
            print(msg)
            
        #packets.append(packet)
    def validate_packet(self, packet):
        is_packet_valid = True
        if( packet[scapy_ospf.OSPF_Hdr].version == OSPF_VERSION and packet[scapy_ospf.OSPF_Hdr].area == AREA_ID and packet[scapy_ospf.OSPF_Hdr].authtype == AUTH_TYPE):
            is_packet_valid = False
        return is_packet_valid

###---------------------------------###
### ----------- RUNNING ----------- ###
###---------------------------------###

def main():
    Router = RouterClass(ROUTER_INTERFACES)
    Database_Topo = DatabaseClass()
    
    OspfHello = OspfHelloThread(Router)
    OspfLSU = OspfLSUThread(Router)
    OspfHello.start()
    print("{} OSPF_Hello_Thread started!".format(time.strftime('%H:%M:%S')))
    OspfLSU.start()
    print("{} OSPF_LSU_Thread started!".format(time.strftime('%H:%M:%S')))
    #OspfSniffer = OspfSnifferThread()
    #OspfSniffer.start()
    #log("OSPF_Sniffer_Thread started!")

    time.sleep(25)

    OspfHello.stop()
    OspfHello.join()
    OspfLSU.stop()
    OspfLSU.join()
    #OspfSniffer.stop()
    #OspfSniffer.join()
    
if __name__ == "__main__":
    main()




