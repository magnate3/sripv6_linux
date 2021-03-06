#! /usr/bin/env python2.5

##     OSPFv3 monitor

##     OSPFv3 module: provides the OSPF listener and OSPF PDU parsers

##     Copyright (C) 2017 Binh Nguyen <binh@cs.utah.edu> University of Utah

##     This program is free software; you can redistribute it and/or
##     modify it under the terms of the GNU General Public License as
##     published by the Free Software Foundation; either version 2 of the
##     License, or (at your option) any later version.

##     This program is distributed in the hope that it will be useful,
##     but WITHOUT ANY WARRANTY; without even the implied warranty of
##     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
##     General Public License for more details.

##     You should have received a copy of the GNU General Public License
##     along with this program; if not, write to the Free Software
##     Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA
##     02111-1307 USA

# RFC 1584 -- MOSPF
# RFC ???? -- OSPF v3
# RFC 2676 -- QoS routing mechanisms
# RFC 3101 -- Not-so-stubby-area (NSSA) option
# RFC 3137 -- Stub routers (where metric == 0xffffff > LSInfinity, 0xffff)
# RFC 3623 -- Graceful restart
# RFC 3630 -- Traffic engineering extensions

## LSUPD/LSA notes:

# router id:
#    the IP address of the router that generated the packet
# advrtr:
#    the IP address of the advertising router
# src:
#    the IP address of the interface from which the LSUPD came

# link state id (lsid):
#    identifier for this link (interface) dependent on type of LSA:
#      1 (router)       ID of router generating LSA
#      2 (network)      IP address of DR for LAN
#      3 (summary IP)   IP address of link reported as dst
#      4 (summary ASBR) IP address of reachable ASBR
#      5 (external AS)  IP address of link reported as dst

# link id:
#    what is connected to this router by this link, dependent on type
#      1 (p2p)          ID of neighbour router
#      2 (transit)      IP address of DR for LAN
#      3 (stub)         IP address of LAN (no DR since a stub network)
#      4 (virtual)      ID of neighbour router
# link data:
#    subnet mask if lsid==3; else IP address of the router that
#    generated the LSA on the advertised link (~= advrtr?)

# summary LSA:
#    created by ASBR and flooded into area; type 3 report cost to
#    prefix outside area, type 4 report cost to ASBR

import struct, socket, sys, math, getopt, string, os.path, time, select, traceback
from mutils import *

import logging
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)
PARSE = [1,1,1,1,1] #[hello, dbdesc, req, update, ack]

#-------------------------------------------------------------------------------

INDENT          = "    "
VERSION         = "2.9"

RECV_BUF_SZ      = 8192
OSPF_LISTEN_PORT = 89
LS_INFINITY      = 0xffff
LS_STUB_RTR      = 0xffffff

IP_HDR     = "> BBH HH BBH LL"
IP_HDR_LEN = struct.calcsize(IP_HDR)

IPV6_HDR     = "> BBH HBB LLLL LLLL"
IPV6_HDR_LEN = struct.calcsize(IPV6_HDR)


OSPF_HDR     = "> BBH L L HH L L" #V2
OSPF_HDR_LEN = struct.calcsize(OSPF_HDR)

#V3 message structure: https://sites.google.com/site/amitsciscozone/home/important-tips/ipv6/ospfv3-messages
#V3
OSPFV3_HDR     = "> BBH L L HBB" #V3 
OSPFV3_HDR_LEN = struct.calcsize(OSPFV3_HDR)


OSPF_HELLO     = "> L HBB L L L"
OSPF_HELLO_LEN = struct.calcsize(OSPF_HELLO)

#V3
OSPFV3_HELLO     = "> L B3s HH L L"
OSPFV3_HELLO_LEN = struct.calcsize(OSPFV3_HELLO)


OSPF_DESC     = "> HBB L "
OSPF_DESC_LEN = struct.calcsize(OSPF_DESC)

#V3
OSPFV3_DESC     = "> B3s HBB L "
OSPFV3_DESC_LEN = struct.calcsize(OSPFV3_DESC)

OSPF_LSREQ     = "> L L L"
OSPF_LSREQ_LEN = struct.calcsize(OSPF_LSREQ)

#V3 LS request
OSPFV3_LSREQ     = "> HH L L"
OSPFV3_LSREQ_LEN = struct.calcsize(OSPFV3_LSREQ)


OSPF_LSUPD     = "> L"
OSPF_LSUPD_LEN = struct.calcsize(OSPF_LSUPD)

#V3 
OSPFV3_LSUPD     = "> L"
OSPFV3_LSUPD_LEN = struct.calcsize(OSPFV3_LSUPD)


OSPF_LSAHDR     = "> HBB L L L HH"
OSPF_LSAHDR_LEN = struct.calcsize(OSPF_LSAHDR)

#V3
OSPFV3_LSAHDR     = "> HH L L L HH"
OSPFV3_LSAHDR_LEN = struct.calcsize(OSPFV3_LSAHDR)


OSPF_LSARTR     = "> BBH"
OSPF_LSARTR_LEN = struct.calcsize(OSPF_LSARTR)

#V3
OSPFV3_LSARTR     = "> B3s"
OSPFV3_LSARTR_LEN = struct.calcsize(OSPFV3_LSARTR)
OSPFV3_LSARTR_INTERFACE     = "> BBH L L L"	#neighbor interface information in router LSA
OSPFV3_LSARTR_INTERFACE_LEN = struct.calcsize(OSPFV3_LSARTR_INTERFACE)




OSPF_LSANET     = "> L"
OSPF_LSANET_LEN = struct.calcsize(OSPF_LSANET)

#V3
OSPFV3_LSANET     = "> B3s"
OSPFV3_LSANET_LEN = struct.calcsize(OSPFV3_LSANET)


OSPF_LINK     = "> L L BBH"
OSPF_LINK_LEN = struct.calcsize(OSPF_LINK)

#V3
OSPFV3_LSALINK     = "> B3s LLLL L"
OSPFV3_LSALINK_LEN = struct.calcsize(OSPFV3_LSALINK)

#V3
OSPFV3_LSAINTRAPREFIX = "> HH L L "
OSPFV3_LSAINTRAPREFIX_LEN = struct.calcsize(OSPFV3_LSAINTRAPREFIX)

#TODO
OSPF_METRIC     = "> BBH"
OSPF_METRIC_LEN = struct.calcsize(OSPF_METRIC)

OSPF_LSASUMMARY     = "> L"
OSPF_LSASUMMARY_LEN = struct.calcsize(OSPF_LSASUMMARY)

OSPF_LSAEXT     = "> L"
OSPF_LSAEXT_LEN = struct.calcsize(OSPF_LSAEXT)

OSPF_LSAEXT_METRIC     = "> BBH L L"
OSPF_LSAEXT_METRIC_LEN = struct.calcsize(OSPF_LSAEXT_METRIC)

################################################################################

DLIST = []

ADDRS = { str2id("224.0.0.5"): "AllSPFRouters",
          str2id("224.0.0.6"): "AllDRouters",
          }
DLIST += [ADDRS]

AFI_TYPES = { 1L: "IP",
              2L: "IP6",
              }
DLIST += [AFI_TYPES]

MSG_TYPES = { 1L: "HELLO",
              2L: "DBDESC",
              3L: "LSREQ",
              4L: "LSUPD",
              5L: "LSACK",
              }
DLIST += [MSG_TYPES]

AU_TYPES = { 0L: "NULL",
             1L: "PASSWD",
             2L: "CRYPTO",
             }
DLIST += [AU_TYPES]

LSA_TYPES = { 1L: "ROUTER",             # links between routers in the area
              2L: "NETWORK",            # links between "networks" in the area
              3L: "SUMMARY (IP)",       # networks rechable outside area; gen. by ASBR
              4L: "SUMMARY (ASBR)",     # ASBRs reachable outside area; gen. by (local) ASBR
              5L: "EXTERNAL AS",        # prefixes reachable outside the AS; gen. by (local) ASBR

              6L: "MOSPF",
              7L: "NSSA",

              9L: "OPAQUE LINK LOCAL",
              10L: "OPAQUE AREA LOCAL",
              11L: "OPAQUE AS LOCAL",
              }
#V3
LSAV3_TYPES = { 8193: "ROUTER",             # links between routers in the area, 0X2001
              8194: "NETWORK",            # links between "networks" in the area, 0X2002
              8195: "INTER AREA PREFIX",       
              8196: "INTER AREA ROUTER",     
              16389: "EXTERNAL AS",   #0X4005     

              8198: "GROUP MEMBER", #0X2006
              8199: "NSSA",
	      8: "LINK LSA", #0X0008
              8201: "INTRA AREA PREFIX", #0X2009
              }

DLIST += [LSA_TYPES]

OPAQUE_TYPES = { 1L: "TRAFFIC ENGINEERING",
                 3L: "GRACEFUL RESTART",
                 }
DLIST += [OPAQUE_TYPES]

TE_TLV_TS = { 1L: "ROUTER ADDRESS",
              2L: "LINK",
              }
DLIST += [TE_TLV_TS]

TE_TLV_LS = { 1L: 4,
              2L: 0, ## variable
              }

TE_LINK_SUBTYPES = { 1L: "TYPE",
                     2L: "ID",
                     3L: "LOCAL IF",
                     4L: "REMOTE IF",
                     5L: "TE METRIC",
                     6L: "MAX BW",
                     7L: "MAX RSVBL BW",
                     8L: "UNRSVD BW",
                     9L: "ADMIN GROUP",
                     }
DLIST += [TE_LINK_SUBTYPES]

TE_LINK_SUBTYPE_LS = { 1L: 1,
                       2L: 4,
                       3L: 4,
                       4L: 4,
                       5L: 4,
                       6L: 4,
                       7L: 4,
                       8L: 32,
                       9L: 4,
                       }

GRACE_TLV_TS = { 1L: "PERIOD",
                 2L: "REASON",
                 3L: "IP ADDR",
                 }
DLIST += [GRACE_TLV_TS]

GRACE_REASONS = { 0L: "UNKNOWN",
                  1L: "SW RESTART",
                  2L: "SW RELOAD/UPGRADE",
                  3L: "SWITCH REDUNDANT RCP",
                  }
DLIST += [GRACE_REASONS]

GRACE_TLV_LS = { 1L: 4,
                 2L: 1,
                 3L: 4,
                 }

RTR_LINK_TYPE = { 1L: "P2P",
                  2L: "TRANSIT",
                  3L: "STUB",
                  4L: "VIRTUAL",
                  }

DLIST += [RTR_LINK_TYPE]

for d in DLIST:
    for k in d.keys():
        d[ d[k] ] = k

################################################################################

def parseIpHdr(msg, verbose=1, level=0):

    if verbose > 1: print prtbin(level*INDENT, msg[:IP_HDR_LEN])
    (verhlen, tos, iplen, ipid, frag, ttl, proto, cksum, src, dst) =\
              struct.unpack(IP_HDR, msg)

    ver  = (verhlen & 0xf0) >> 4
    hlen = (verhlen & 0x0f) * 4

    if verbose > 0:
        print level*INDENT +\
              "IP (len=%d)" % len(msg)
        print (level+1)*INDENT +\
              "ver:%s, hlen:%s, tos:%s, len:%s, id:%s, frag:%s, ttl:%s, prot:%s, cksm:%x" %\
              (ver, hlen, int2bin(tos), iplen, ipid, frag, ttl, proto, cksum)
        print (level+1)*INDENT +\
              "src:%s, dst:%s" % (id2str(src), id2str(dst))

    return { "VER"   : ver,
             "HLEN"  : hlen,
             "TOS"   : tos,
             "IPLEN" : iplen,
             "IPID"  : ipid,
             "FRAG"  : frag,
             "TTL"   : ttl,
             "PROTO" : proto,
             "CKSUM" : cksum,
             "SRC"   : src,
             "DST"   : dst
             }

def parseOspfHdr(msg, verbose=1, level=0):

    if verbose > 1: print prtbin(level*INDENT, msg[:OSPF_HDR_LEN])
    (ver, typ, len, rid, aid, cksum, instanceid, zero) = struct.unpack(OSPFV3_HDR, msg)
    if verbose > 1:
        print level*INDENT +\
              "OSPF: ver:%s, type:%s, len:%s, rtr id:%s, area id:%s, cksum:%x, instanceid:%s" %\
              (ver, MSG_TYPES[typ], len, id2str(rid), id2str(aid), cksum, instanceid,)

    return { "VER"    : ver,
             "TYPE"   : typ,
             "LEN"    : len,
             "RID"    : rid,
             "AID"    : aid,
             "CKSUM"  : cksum,
             "INSTANCEID"  : instanceid,
             }

def parseOspfOpts(opts, verbose=1, level=0):
    if verbose > 1: print "###parseOspfOpts not implemented.###"
    return None
    #TODO
    if verbose > 1: print level*INDENT + int2bin(opts)

    qbit  = (opts & 0x01) ## RFC 2676; reclaim original "T"-bit for TOS routing cap.
    ebit  = (opts & 0x02) >> 1
    mcbit = (opts & 0x04) >> 2
    npbit = (opts & 0x08) >> 3
    eabit = (opts & 0x10) >> 4
    dcbit = (opts & 0x20) >> 5
    obit  = (opts & 0x40) >> 6

    if verbose > 0:
        print level*INDENT + "options: %s %s %s %s %s %s %s" %(
            qbit*"Q", ebit*"E", mcbit*"MC", npbit*"NP", eabit*"EA", dcbit*"DC", obit*"O")

    return { "Q"  : qbit,
             "E"  : ebit,
             "MC" : mcbit,
             "NP" : npbit,
             "EA" : eabit,
             "DC" : dcbit,
             "O"  : obit,
             }

def parseOspfLsaHdr(hdr, verbose=1, level=0):

    if verbose > 1: print prtbin(level*INDENT, hdr)
    (age, typ, lsid, advrtr, lsseqno, cksum, length) = struct.unpack(OSPFV3_LSAHDR, hdr)

    if verbose > 0:
        print level*INDENT +\
              "age:%s, type:%s, lsid:%s, advrtr:%s, lsseqno:%s, cksum:%x, len:%s" %(
                  age, LSAV3_TYPES[typ], id2str(lsid), id2str(advrtr), lsseqno, cksum, length)

    return { "AGE"     : age,
             "T"       : typ,
             "LSID"    : lsid,
             "ADVRTR"  : advrtr,
             "LSSEQNO" : lsseqno,
             "CKSUM"   : cksum,
             "L"       : length,
             }

def parseOspfLsaRtr(lsa, verbose=1, level=0):

    if verbose > 1: print prtbin(level*INDENT, lsa[:OSPFV3_LSARTR_LEN])
    (veb, options) = struct.unpack(OSPFV3_LSARTR, lsa[:OSPFV3_LSARTR_LEN])
    v = (veb & 0x01)
    e = (veb & 0x02) >> 1
    b = (veb & 0x04) >> 2
    if verbose > 0:
        print level*INDENT + "rtr desc: %s %s %s" %(
            v*"VIRTUAL", e*"EXTERNAL", b*"BORDER")

    lsa = lsa[OSPFV3_LSARTR_LEN:] ; interfaces = []
    while len(lsa) >= OSPFV3_LSARTR_INTERFACE_LEN:
        if verbose > 1: print prtbin((level+1)*INDENT, lsa[:OSPFV3_LSARTR_INTERFACE_LEN])
        (type, _, metric, interfaceid, nbinterfaceid, nbrouterid) = struct.unpack(OSPFV3_LSARTR_INTERFACE, lsa[:OSPFV3_LSARTR_INTERFACE_LEN])
        if verbose > 0:
            print (level+1)*INDENT +\
                  "type:%s, metric:%s, interfaceid:%s, nbinterfaceid:%s, nbrouterid:%s" %(
                      type, metric, interfaceid, nbinterfaceid, nbrouterid)

        lsa = lsa[OSPFV3_LSARTR_INTERFACE_LEN:] 

        interfaces.append({ "TYPE"      : type,
                     "METRIC"    : metric,
                     "INTERFACEID"       : interfaceid,
                     "NBINTERFACEID"    : nbinterfaceid,
                     "NBROUTERID" : nbrouterid,
                     })

    return { "VIRTUAL"  : v,
             "EXTERNAL" : e,
             "BORDER"   : b,
             "OPTIONS"   : options,
             "INTERFACES"    : interfaces,
             }

def parseOspfLsaNet(lsa, verbose=1, level=0):

    if verbose > 1: print prtbin(level*INDENT, lsa[:OSPFV3_LSANET_LEN])
    (_, options) = struct.unpack(OSPFV3_LSANET, lsa[:OSPFV3_LSANET_LEN])

    lsa = lsa[OSPFV3_LSANET_LEN:] ; rt_len = struct.calcsize(">L") ; rtrs = []
    while len(lsa) > 0:
	
        if verbose > 1: print prtbin((level+1)*INDENT, lsa[:OSPFV3_LSANET_LEN])
        (rtr,) = struct.unpack('>L', lsa[:rt_len])
        if verbose > 0:
            print (level+1)*INDENT + "attached rtr:%s" % (id2str(rtr))

        rtrs.append(rtr)
        lsa = lsa[rt_len:]

    return { "options" : options,
             "RTRS" : rtrs
             }

def parseOspfLsaLink(lsa, verbose=1, level=0):

    if verbose > 1: print prtbin(level*INDENT, lsa[:OSPFV3_LSALINK_LEN])
    (prio, options, lcp1, lcp2, lcp3, lcp4, nprefix) = struct.unpack(OSPFV3_LSALINK, lsa[:OSPFV3_LSALINK_LEN])
    llprefix = int2ipv6(lcp1, lcp2, lcp3, lcp4)
    if verbose > 0: print (level+1)*INDENT + "link local prefix: %s" % (llprefix)

    lsa = lsa[OSPFV3_LSALINK_LEN:] ; cnt = 0; pr_len = struct.calcsize(">BBH LLL") ; prefixes = []
    while cnt < int(nprefix):
        if verbose > 1: print prtbin((level+1)*INDENT, lsa[:pr_len])
        (pl, popts, _, p1, p2, p3) = struct.unpack('>BBH LLL', lsa[:pr_len])
	prefix = int2ipv6(p1, p2, p3, 0)
        if verbose > 0:
            print (level+1)*INDENT + "prefix:%s" % prefix

        prefixes.append(prefix)
        lsa = lsa[pr_len:]
	cnt += 1

    return { "options" : options,
             "linklocaladdress" : llprefix,
	     "prefixes" : prefixes
             }

def parseOspfLsaIntraAreaPrefix(lsa, verbose=1, level=0):
    if verbose > 1: print prtbin(level*INDENT, lsa[:OSPFV3_LSAINTRAPREFIX_LEN])
    (nprefixes, reflstype, reflsid, refadvrouter) = struct.unpack(OSPFV3_LSAINTRAPREFIX, lsa[:OSPFV3_LSAINTRAPREFIX_LEN])
    if verbose > 1: print (level+1)*INDENT + "nprefixes:%s, reflstype:%s, reflsid:%s, refadvrouter:%s" % (nprefixes, reflstype, reflsid, refadvrouter)

    lsa = lsa[OSPFV3_LSAINTRAPREFIX_LEN:] ; cnt = 0; 
    prefixes = []
    while cnt < int(nprefixes):
    	(pr_len_bit,) = struct.unpack('>B', lsa[:struct.calcsize('>B')])
	pr_len = pr_len_bit/8
        if verbose > 1: print prtbin((level+1)*INDENT, lsa[:pr_len])
	prefix_cnt = pr_len/struct.calcsize('>L')
        (pl, popts, _) = struct.unpack('>BBH', lsa[:struct.calcsize('>BBH')])
	lsa = lsa[struct.calcsize('>BBH'):]
	p = [0,0,0,0]
	for i in range(0, prefix_cnt):
		(p[i],) = struct.unpack('>L', lsa[:struct.calcsize('>L')])
		lsa = lsa[struct.calcsize('>L'):]
	prefix = int2ipv6(p[0], p[1], p[2], p[3])
        if verbose > 0:
            print (level+1)*INDENT + "prefix:%s" % prefix

        prefixes.append(prefix)
	cnt += 1

    return { 
	     "nprefix": nprefixes,
	     "reflstype" : reflstype,
	     "reflsid" : reflsid,
	     "refadvrouter" : refadvrouter,
	     "prefixes" : prefixes
             }


    return None 

def parseOspfLsaSummary(lsa, verbose=1, level=0):

    if verbose > 1: print prtbin(level*INDENT, lsa[:OSPF_LSASUMMARY_LEN])
    (mask, ) = struct.unpack(OSPF_LSASUMMARY, lsa[:OSPF_LSASUMMARY_LEN])
    if verbose > 0:
        print level*INDENT + "mask:%s" % (id2str(mask), )

    lsa = lsa[OSPF_LSASUMMARY_LEN:] ; cnt = 0 ; metrics = {}
    while len(lsa) > 0:
        cnt += 1

        if verbose > 1: print prtbin((level+1)*INDENT, lsa[:OSPF_METRIC_LEN])
        (tos, stub, metric) = struct.unpack(OSPF_METRIC, lsa[:OSPF_METRIC_LEN])

        ## RFC 3137 "Stub routers": if (stub,metric) == (0xff, 0xffff)
        ## then this is a stub router and it is attempting to
        ## discourage other routers from using it to transit traffic,
        ## ie. forward traffic to any networks others than those
        ## connected directly

        metric = ((stub<<16) | metric)
        if verbose > 0:
            if metric == LS_STUB_RTR: mstr = "metric:STUB_ROUTER"
            elif metric > LS_INFINITY: mstr = "*** metric:%s > LS_INFINITY! ***" % metric
            elif metric == LS_INFINITY: mstr = "metric:LS_INFINITY"
            else: mstr = "metric:%d" % metric
            print (level+1)*INDENT + "%s: tos:%s, %s" % (cnt, tos, mstr)

        metrics[tos] = metric
        lsa = lsa[OSPF_METRIC_LEN:]

    return { "MASK"    : mask,
             "METRICS" : metrics
             }

def parseOspfLsaExt(lsa, verbose=1, level=0):

    if verbose > 1: print prtbin(level*INDENT, lsa[:OSPF_LSAEXT_LEN])
    (mask, ) = struct.unpack(OSPF_LSAEXT, lsa[:OSPF_LSAEXT_LEN])
    if verbose > 0: print level*INDENT + "mask:%s" % id2str(mask)

    lsa = lsa[OSPF_LSAEXT_LEN:] ; cnt = 0 ; metrics = {}
    while len(lsa) > 0:

        if verbose > 1: print prtbin((level+1)*INDENT, lsa[:OSPF_LSAEXT_METRIC_LEN])
        (exttos, stub, metric, fwd, tag, ) =\
           struct.unpack(OSPF_LSAEXT_METRIC, lsa[:OSPF_LSAEXT_METRIC_LEN])
        ext = ((exttos & 0xf0) >> 7) * "E"
        tos = exttos & 0x7f

        metric = ((stub<<16) | metric)
        if verbose > 0:
            if metric == LS_STUB_RTR: mstr = "metric:STUB_ROUTER"
            elif metric > LS_INFINITY: mstr = "*** metric:%s > LS_INFINITY! ***" % metric
            elif metric == LS_INFINITY: mstr = "metric:LS_INFINITY"
            else: mstr = "metric:%d" % metric
            print (level+1)*INDENT +\
                  "%s: ext:%s, tos:%s, %s, fwd:%s, tag:0x%x" %(
                      cnt, ext, int2bin(tos), mstr, id2str(fwd), tag)

        metrics[tos] = { "EXT"    : ext,
                         "METRIC" : metric,
                         "FWD"    : fwd,
                         "TAG"    : tag,
                         }

        lsa = lsa[OSPF_LSAEXT_METRIC_LEN:]
        cnt += 1

    return { "MASK": mask,
             "METRICS": metrics,
             }

def parseOspfLsas(lsas, verbose=1, level=0):

    rv = {}

    cnt = 0
    while len(lsas) > 0:
        cnt += 1
        rv[cnt] = {}

        if verbose > 0: print level*INDENT + "LSA %s" % cnt
        rv[cnt]["H"] = parseOspfLsaHdr(lsas[:OSPFV3_LSAHDR_LEN], verbose, level+1)
        t = rv[cnt]["H"]["T"]
        l = rv[cnt]["H"]["L"]
        rv[cnt]["T"] = t
        rv[cnt]["L"] = l

        if LSAV3_TYPES[t] == "ROUTER":
            rv[cnt]["V"] = parseOspfLsaRtr(lsas[OSPFV3_LSAHDR_LEN:l], verbose, level+1)
        elif LSAV3_TYPES[t] == "NETWORK":
            rv[cnt]["V"] = parseOspfLsaNet(lsas[OSPFV3_LSAHDR_LEN:l], verbose, level+1)
        elif LSAV3_TYPES[t] == "LINK LSA":
            rv[cnt]["V"] = parseOspfLsaLink(lsas[OSPFV3_LSAHDR_LEN:l], verbose, level+1)
        elif LSAV3_TYPES[t] == "INTRA AREA PREFIX":
            rv[cnt]["V"] = parseOspfLsaIntraAreaPrefix(lsas[OSPFV3_LSAHDR_LEN:l], verbose, level+1)

        else:
            error("[ *** unknown LSA type %d*** ]\n" % (t, ))
            error("%s\n" % prtbin(level*INDENT, msg))

        lsas = lsas[l:]

    return rv

def parseOspfHello(msg, verbose=1, level=0):

    if verbose > 1: 
	print prtbin(level*INDENT, msg)
		
    (interfaceid, prio, options, hellointerval, deadinterval, desig, bdesig) = struct.unpack(OSPFV3_HELLO, msg[:OSPFV3_HELLO_LEN])
    if verbose > 0:
        print level*INDENT +\
              "HELLO: interfaceid:%s, prio:%s, opts:%s, hello interval:%s, dead intvl:%s" %\
              (interfaceid, prio, options, hellointerval, deadinterval)
        print (level+1)*INDENT +\
              "designated rtr:%s, backup designated rtr:%s" %\
              (id2str(desig), id2str(bdesig))

    msg = msg[OSPFV3_HELLO_LEN:]  
    nbor_len = struct.calcsize(">L") ; 
    nbors = []
    while len(msg) > 0:
        if verbose > 1: print prtbin(level*INDENT, msg[:nbor_len])
        (nbor,) = struct.unpack(">L", msg[:nbor_len])
        if verbose > 0:
            print (level+1)*INDENT + "neighbour: %s" % (id2str(nbor),)
        nbors.append(nbor)
        msg = msg[nbor_len:]


    return { 
	     "INTERFACEID" : interfaceid, 
	     "PRIO"    : prio,
             "OPTS"    : parseOspfOpts(options, verbose, level),
             "HELLO"   : hellointerval,
             "DEAD"    : deadinterval,
             "DESIG"   : desig,
             "BDESIG"  : bdesig,
             "NBORS"   : nbors
             }

def parseOspfDesc(msg, verbose=1, level=0):

    if verbose > 1: print prtbin(level*INDENT, msg)
    (zero, opts, mtu, aopts, imms, ddseqno) = struct.unpack(OSPFV3_DESC, msg[:OSPFV3_DESC_LEN])
    init        = (imms & 0x04) >> 2
    more        = (imms & 0x02) >> 1
    masterslave = (imms & 0x01)
    if verbose > 0:
        print level*INDENT +\
              "DESC: mtu:%s, opts:%s, imms:%s%s%s%s, dd seqno:%s" %\
              (mtu, opts, init*"INIT", more*" MORE",
               masterslave*" MASTER" ,(1-masterslave)*" SLAVE",
               ddseqno)

    return { "MTU"         : mtu,
             "OPTS"        : parseOspfOpts(opts, verbose, level),
             "INIT"        : init,
             "MORE"        : more,
             "MASTERSLAVE" : masterslave,
             }

def parseOspfLSReq(msg, verbose=1, level=0):

    error("### LSREQ UNIMPLEMENTED ###\n")
    return None

def parseOspfLsUpd(msg, verbose=1, level=0):

    if verbose > 1: print prtbin(level*INDENT, msg[:OSPFV3_LSUPD_LEN])
    (nlsas, ) = struct.unpack(OSPFV3_LSUPD, msg[:OSPFV3_LSUPD_LEN])
    if verbose > 0:
        print level*INDENT + "LSUPD: nlsas:%s" % (nlsas)

    return { "NLSAS" : nlsas,
             "LSAS"  : parseOspfLsas(msg[OSPFV3_LSUPD_LEN:], verbose, level+1),
             }

def parseOspfLsAck(msg, verbose=1, level=0):

    if verbose > 0: print level*INDENT + "LSACK"

    cnt = 0 ; lsas = {}
    while len(msg) > 0:
        cnt += 1
        if verbose > 0: print (level+1)*INDENT + "LSA %s" % cnt
        lsas[cnt] = parseOspfLsaHdr(msg[:OSPF_LSAHDR_LEN], verbose, level+1)
        msg = msg[OSPF_LSAHDR_LEN:]

    return { "LSAS"  : lsas
             }

def parseOspfMsg(msg, verbose=1, level=0):

    ospfh = parseOspfHdr(msg[:OSPFV3_HDR_LEN], verbose, level)
    rv = { "T": ospfh["TYPE"],
           "L": len(msg),
           "V": ospfh,
           }

    if MSG_TYPES[ospfh["TYPE"]] == "HELLO" and (PARSE[0] == 1):
        rv["V"]["V"] = parseOspfHello(msg[OSPFV3_HDR_LEN:], verbose, level+1)

    elif MSG_TYPES[ospfh["TYPE"]] == "DBDESC" and (PARSE[1] == 1):
        rv["V"]["V"] = parseOspfDesc(msg[OSPFV3_HDR_LEN:], verbose, level+1)

    elif MSG_TYPES[ospfh["TYPE"]] == "LSREQ" and (PARSE[2] == 1):
        rv["V"]["V"] = parseOspfLSReq(msg[OSPFV3_HDR_LEN:], verbose, level)

    elif MSG_TYPES[ospfh["TYPE"]] == "LSUPD" and (PARSE[3] == 1):
        rv["V"]["V"] = parseOspfLsUpd(msg[OSPFV3_HDR_LEN:], verbose, level+1)

    elif MSG_TYPES[ospfh["TYPE"]] == "LSACK" and (PARSE[4] == 1):
        rv["V"]["V"] = parseOspfLsAck(msg[OSPFV3_HDR_LEN:], verbose, level+1)

    return rv

################################################################################

class OspfExc(Exception): pass

class Ospfv3:

    _version   = 2
    _holdtimer = 30

    #---------------------------------------------------------------------------

    class Adj:

        def __init__(self): pass
        def __repr__(self): pass

    #---------------------------------------------------------------------------

    def __init__(self, ADDRESS):

        ## XXX raw sockets are broken in Windows Python (some madness
        ## about linking against winsock1, etc); applied "patch" from
        ## https://sourceforge.net/tracker/?func=detail&atid=355470&aid=889544&group_id=5470,
        ## http://www.rs.fromadia.com/newsread.php?newsid=254,
        ## http://www.rs.fromadia.com/files/pyraw.exe to fix this

        #self._sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
        #self._sock = socket.socket(socket.AF_INET6, socket.SOCK_RAW, socket.IPPROTO_IPV6)
        #self._sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
	self._sock = socket.socket(socket.AF_INET6, socket.SOCK_RAW, 89)
	#res = socket.getaddrinfo("localhost", 2000, socket.AF_INET6, socket.SOCK_RAW, socket.IPPROTO_IPV6)
	#af, socktype, proto, canonname, sa = res[1]

        #self._sock = socket.socket(af, socktype, proto)
        self._addr = (ADDRESS, 0)
        self._sock.bind(self._addr)
        self._name = self._sock.getsockname()

        #self._sock.setsockopt(89, socket.IP_HDRINCL, 1)
	#self._sock.listen(1)
        #self._sock.ioctl(socket.SIO_RCVALL, 1)

        self._adjs = {}
        self._rcvd = ""
        self._mrtd = None
	

    def __repr__(self):

        rs = """OSPF listener, version %s:
        %s
        socket:  %s
        address: %s, name: %s""" %\
            (self._version, self._mrtd, self._sock, self._addr, self._name)

        return rs

    def close(self):

        self._sock.close()
        self._mrtd.close()

    #---------------------------------------------------------------------------

    def parseMsg(self, verbose=1, level=0):
	rv = None
        try:
            (msg_len, msg) = self.recvMsg(verbose, level)

        except OspfExc, oe:
            if verbose > 1: print "[ *** Non OSPF packet received *** ]"
            return

	if 1:
            ospfh = parseOspfHdr(msg[:OSPFV3_HDR_LEN], 0)

            if verbose > 2:
                print "%sparseMsg: len=%d%s" %\
                      (level*INDENT, msg_len, prthex((level+1)*INDENT, msg))

            rv = parseOspfMsg(msg, verbose, level)
		

            return rv

    def recvMsg(self, verbose=1, level=0):
        self._rcvd = self._sock.recv(RECV_BUF_SZ)
        if verbose > 2:
            print "%srecvMsg: recv: len=%d%s" %\
                  (level*INDENT,
                   len(self._rcvd), prthex((level+1)*INDENT, self._rcvd))

        return (len(self._rcvd), self._rcvd)


    def sendMsg(self, verbose=1, level=0):

        pass

    #---------------------------------------------------------------------------

################################################################################

if __name__ == "__main__":

    import mrtd

    global VERBOSE, DUMP_MRTD, ADDRESS

    VERBOSE   = 1
    DUMP_MRTD = 0
    ADDRESS   = None

    file_pfx  = mrtd.DEFAULT_FILE
    file_sz   = mrtd.DEFAULT_SIZE
    mrtd_type = None

    #---------------------------------------------------------------------------

    def usage():

        print """Usage: %s [ options ] ([*] options required):
        -h|--help     : Help
        -q|--quiet    : Be quiet
        -v|--verbose  : Be verbose
        -V|--VERBOSE  : Be very verbose

        -d|--dump     : Dump protocol MRTD file
        -f|--file     : Set file prefix for MRTd dump [def: %s]
        -z|--size     : Size of output file(s) [min: %d]
        -b|--bind <ipaddr> : local IP address for bind """ %\
            (os.path.basename(sys.argv[0]),
             mrtd.DEFAULT_FILE,
             mrtd.MIN_FILE_SZ)
        sys.exit(0)

    #---------------------------------------------------------------------------

    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "hqvVdf:z:",
                                   ("help", "quiet", "verbose", "VERBOSE",
                                    "dump", "file=", "size=", ))
    except (getopt.error):
        usage()

    for (x, y) in opts:
        if x in ('-h', '--help'):
            usage()

        elif x in ('-q', '--quiet'):
            VERBOSE = 0

        elif x in ('-v', '--verbose'):
            VERBOSE = 2

        elif x in ('-V', '--VERBOSE'):
            VERBOSE = 3

        elif x in ('-d', '--dump'):
            DUMP_MRTD = 1
            mrtd_type = mrtd.MSG_TYPES["PROTOCOL_OSPF2"]

        elif x in ('-f', '--file-pfx'):
            file_pfx = y

        elif x in ('-z', '--file-size'):
            file_sz = max(string.atof(y), mrtd.MIN_FILE_SZ)

        elif x in ('-b', '--bind'):
            ADDRESS = y

        else:
            usage()

    if not ADDRESS: usage()

    #---------------------------------------------------------------------------

    ospf       = Ospf()
    ospf._mrtd = mrtd.Mrtd(file_pfx, "w+b", file_sz, mrtd.MSG_TYPES["PROTOCOL_OSPF2"], ospf)

    if VERBOSE > 0: print ospf

    try:
        timeout = Ospf._holdtimer

        rv = None
        while 1:
            before = time.time()
            rfds, _, _ = select.select([ospf._sock], [], [], timeout)
            after = time.time()
            elapsed = after - before

            if len(rfds) > 0: rv = ospf.parseMsg(VERBOSE, 0)
            else:
                ## tx some pkts to form adjacency
                pass

    except (KeyboardInterrupt):
        ospf.close()
        sys.exit(1)

################################################################################
################################################################################
