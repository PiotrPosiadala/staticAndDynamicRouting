/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4 = 0x800;

/*---------------------------------------/
/----------------HEADERS----------------/
/---------------------------------------*/

typedef bit<9>  egressSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;
}

header ipv4_t {
    bit<4>    version;
    bit<4>    ihl;
    bit<8>    diffserv;
    bit<16>   totalLen;
    bit<16>   identification;
    bit<3>    flags;
    bit<13>   fragOffset;
    bit<8>    ttl;
    bit<8>    protocol;
    bit<16>   hdrChecksum;
    ip4Addr_t srcAddr;
    ip4Addr_t dstAddr;
}


struct routing_metadata_t {
    ip4Addr_t nhop_ipv4;
}

struct metadata {
    routing_metadata_t routing;
}

struct headers {
    ethernet_t   ethernet;
    ipv4_t       ipv4;
}

/*--------------------------------------/
/----------------PARSER----------------/
/--------------------------------------*/

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            TYPE_IPV4: parse_ipv4;
            default: accept;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition accept;
    }

}

/*-------------------------------------------/
/-----------CHECKSUM VERIFICATION-----------/
/-------------------------------------------*/

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {   
    apply {  }
}


/*-------------------------------------------/
/------------------INGRESS------------------/
/-------------------------------------------*/

control MyIngress(inout headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata){

    action drop() {
        mark_to_drop(standard_metadata);
        }

    action ipv4_forward(ip4Addr_t nextHop, egressSpec_t port) {
        meta.routing.nhop_ipv4 = nextHop;
        standard_metadata.egress_spec = port;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    table routing_table {
        key = {
            hdr.ipv4.dstAddr: lpm;
        }
        actions = {
            ipv4_forward;
            drop;
            NoAction;
        }
        default_action = NoAction();
    }

    apply {
        routing_table.apply();
    }

}


/*-------------------------------------------/
/------------------EGRESS-------------------/
/-------------------------------------------*/


control MyEgress(inout headers hdr,
               inout metadata meta,
               inout standard_metadata_t standard_metadata){

    action drop() {
        mark_to_drop(standard_metadata);
    }

    action set_destmac(macAddr_t dstAddr) {
        hdr.ethernet.dstAddr = dstAddr;
    }

    action set_sourcemac(macAddr_t mac) {
        hdr.ethernet.srcAddr = mac;
    }

    table switching_table {
        key = {
            meta.routing.nhop_ipv4 : exact;
        }
        actions = {
            set_destmac;
            drop;
            NoAction;
        }
        default_action = NoAction();
    }

    table mac_rewriting_table {

        key = {
            standard_metadata.egress_port: exact;
        }

        actions = {
            set_sourcemac;
            drop;
            NoAction;
        }

        default_action = drop();
    }

    apply {
        switching_table.apply();
        mac_rewriting_table.apply();
    }


}



/*--------------------------------------------/
/-----------------DEPARSER-------------------/
/--------------------------------------------*/

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
    }
}



/*--------------------------------------------/
/--------------COMPUTE CHECKSUM--------------/
/--------------------------------------------*/

control MyComputeChecksum(inout headers  hdr, inout metadata meta) {
     apply {
	update_checksum(
	    hdr.ipv4.isValid(),
            { hdr.ipv4.version,
	      hdr.ipv4.ihl,
              hdr.ipv4.diffserv,
              hdr.ipv4.totalLen,
              hdr.ipv4.identification,
              hdr.ipv4.flags,
              hdr.ipv4.fragOffset,
              hdr.ipv4.ttl,
              hdr.ipv4.protocol,
              hdr.ipv4.srcAddr,
              hdr.ipv4.dstAddr },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16);
    }
}


/*--------------------------------------------/
/-------------------SWITCH-------------------/
/--------------------------------------------*/

V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;