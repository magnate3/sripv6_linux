#!/bin/bash
LB_IP=197
INF="/proj/PhantomNet/binh/simeca_scripts/get_interface_map.pl"


#NODE1
hn=$(hostname | awk -F'.' '{print $1}')
if [ "$hn" == "node1" ]; then
	echo "#Node $hn..."
	n1_a_dev=$($INF | grep neta | awk '{print $3}')
	n1_a_mac=$(ifconfig | grep $n1_a_dev | awk '{print $5}')
	n1_a=$(ifconfig | grep -A3 $n1_a_dev | grep inet6 | grep "fe80::" | awk '{print $3}' | awk -F'/' '{print $1}' | sed s/fe80::*:/2001::204:/ )
	let lb=$LB_IP+1
	echo "n1_lb=\"$lb::1\""
	echo "n1_a=\"$n1_a\""
	echo "n1_a_mac=\"$n1_a_mac\""
	echo "n1_a_dev=\"$n1_a_dev\""
fi


#NODE2
hn=$(hostname | awk -F'.' '{print $1}')
if [ "$hn" == "node2" ]; then
	echo "#Node $hn..."
	n2_a_dev=$($INF | grep neta | awk '{print $3}')
	n2_a_mac=$(ifconfig | grep $n2_a_dev | awk '{print $5}')
	n2_a=$(ifconfig | grep -A3 $n2_a_dev | grep inet6 | grep "fe80::" | awk '{print $3}' | awk -F'/' '{print $1}' | sed s/fe80::*:/2001::204:/ )

	n2_b_dev=$($INF | grep netb | awk '{print $3}')
	n2_b_mac=$(ifconfig | grep $n2_b_dev | awk '{print $5}')
	n2_b=$(ifconfig | grep -A3 $n2_b_dev | grep inet6 | grep "fe80::" | awk '{print $3}' | awk -F'/' '{print $1}' | sed s/fe80::*:/2001::205:/ )

	n2_c_dev=$($INF | grep netc | awk '{print $3}')
	n2_c_mac=$(ifconfig | grep $n2_c_dev | awk '{print $5}')
	n2_c=$(ifconfig | grep -A3 $n2_c_dev | grep inet6 | grep "fe80::" | awk '{print $3}' | awk -F'/' '{print $1}' | sed s/fe80::*:/2001::206:/ )

	let lb=$LB_IP+2
	echo "n2_lb=\"$lb::1\""
	echo "n2_a=\"$n2_a\""
	echo "n2_a_mac=\"$n2_a_mac\""
	echo "n2_a_dev=\"$n2_a_dev\""
	echo "n2_b=\"$n2_b\""
	echo "n2_b_mac=\"$n2_b_mac\""
	echo "n2_b_dev=\"$n2_b_dev\""
	echo "n2_c=\"$n2_c\""
	echo "n2_c_mac=\"$n2_c_mac\""
	echo "n2_c_dev=\"$n2_c_dev\""
fi


#NODE3
hn=$(hostname | awk -F'.' '{print $1}')
if [ "$hn" == "node3" ]; then
	echo "#Node $hn..."
	n3_b_dev=$($INF | grep netb | awk '{print $3}')
	n3_b_mac=$(ifconfig | grep $n3_b_dev | awk '{print $5}')
	n3_b=$(ifconfig | grep -A3 $n3_b_dev | grep inet6 | grep "fe80::" | awk '{print $3}' | awk -F'/' '{print $1}' | sed s/fe80::*:/2001::205:/ )

	n3_d_dev=$($INF | grep netd | awk '{print $3}')
	n3_d_mac=$(ifconfig | grep $n3_d_dev | awk '{print $5}')
	n3_d=$(ifconfig | grep -A3 $n3_d_dev | grep inet6 | grep "fe80::" | awk '{print $3}' | awk -F'/' '{print $1}' | sed s/fe80::*:/2001::207:/ )

	n3_e_dev=$($INF | grep nete | awk '{print $3}')
	n3_e_mac=$(ifconfig | grep $n3_e_dev | awk '{print $5}')
	n3_e=$(ifconfig | grep -A3 $n3_e_dev | grep inet6 | grep "fe80::" | awk '{print $3}' | awk -F'/' '{print $1}' | sed s/fe80::*:/2001::208:/ )

	let lb=$LB_IP+3
	echo "n3_lb=\"$lb::1\""
	echo "n3_b=\"$n3_b\""
	echo "n3_b_mac=\"$n3_b_mac\""
	echo "n3_b_dev=\"$n3_b_dev\""
	echo "n3_d=\"$n3_d\""
	echo "n3_d_mac=\"$n3_d_mac\""
	echo "n3_d_dev=\"$n3_d_dev\""
	echo "n3_e=\"$n3_e\""
	echo "n3_e_mac=\"$n3_e_mac\""
	echo "n3_e_dev=\"$n3_e_dev\""
fi


#NODE4
hn=$(hostname | awk -F'.' '{print $1}')
if [ "$hn" == "node4" ]; then
	echo "#Node $hn..."
	n4=$($INF)
	n4_c_dev=$($INF | grep netc | awk '{print $3}')
	n4_c_mac=$(ifconfig | grep $n4_c_dev | awk '{print $5}')
	n4_c=$(ifconfig | grep -A3 $n4_c_dev | grep inet6 | grep "fe80::" | awk '{print $3}' | awk -F'/' '{print $1}' | sed s/fe80::*:/2001::206:/ )

	n4_d_dev=$($INF | grep netd | awk '{print $3}')
	n4_d_mac=$(ifconfig | grep $n4_d_dev | awk '{print $5}')
	n4_d=$(ifconfig | grep -A3 $n4_d_dev | grep inet6 | grep "fe80::" | awk '{print $3}' | awk -F'/' '{print $1}' | sed s/fe80::*/2001::207:/ )

	let lb=$LB_IP+4
	echo "n4_lb=\"$lb::1\""
	echo "n4_c=\"$n4_c\""
	echo "n4_c_mac=\"$n4_c_mac\""
	echo "n4_c_dev=\"$n4_c_dev\""
	echo "n4_d=\"$n4_d\""
	echo "n4_d_mac=\"$n4_d_mac\""
	echo "n4_d_dev=\"$n4_d_dev\""
fi


#NODE5
hn=$(hostname | awk -F'.' '{print $1}')
if [ "$hn" == "node5" ]; then
	echo "#Node $hn..."
	n5_e_dev=$($INF | grep nete | awk '{print $3}')
	n5_e_mac=$(ifconfig | grep $n5_e_dev | awk '{print $5}')
	n5_e=$(ifconfig | grep -A3 $n5_e_dev | grep inet6 | grep "fe80::" | awk '{print $3}' | awk -F'/' '{print $1}' | sed s/fe80::*:/2001::208:/ )

	let lb=$LB_IP+5
	echo "n5_lb=\"$lb::1\""
	echo "n5_e=\"$n5_e\""
	echo "n5_e_mac=\"$n5_e_mac\""
	echo "n5_e_dev=\"$n5_e_dev\""
fi


