import struct
import argparse
from basic_structures import *

def main():
    packet_headers = {} 
    packet_data = {}
    ether_headers = {}
    ipv4_headers = {}
    tcp_headers = {}
    tcp_status = {} # Store lists of length 2, which represents TCP connection status between two ports 
                    # (ie. tcp_status[key] = [2,1,0], which means the TCP connection contains 2 SYNs, 1 FIN, and 0 RST)
    c_seq_time = {}

    parser = argparse.ArgumentParser()
    parser.add_argument("CAP", help="Enter the name of cap file as an input")
    args = parser.parse_args()

    cap_file = args.CAP

    try:
        file = open(cap_file, "rb")
    except:
        print("Error: The file may not exist.")
        exit()

    split_packet(packet_headers,packet_data,file)

    split_data(packet_data,ether_headers,ipv4_headers,tcp_headers)

    analyze_connection(tcp_headers, tcp_status, ipv4_headers, packet_headers, c_seq_time)

    show_result(tcp_status)

# headers and data are dictionaries containing packet headers and packet data respectively.
def split_packet(headers,data,file):
    num = 1
    
    global_header = file.read(24)
    headers["global_header"] = global_header


    while True:
        key1 = "packet_header" + str(num)
        key2 = "packet_data" + str(num)

        packet_header = file.read(16)

        headers[key1] = packet_header
        
        if (packet_header == b''):
            break

        ts_sec = packet_header[:4]
        ts_usec = packet_header[4:8]
        incl_len = packet_header[8:12]
        orig_len = packet_header[12:]

        # incl_len = int.from_bytes(incl_len, "little") # Convert incl_len bytes to int 
        incl_len = struct.unpack("<I", incl_len)
        incl_len = incl_len[0]
        # print(incl_len)

        pd = file.read(incl_len)

        data[key2] = pd
        num += 1


def split_data(data,ether,ipv4,tcp):
    num = 1
    while True:
        try:
            key1 = "packet_data" + str(num)
            key2 = "ether_header" + str(num)
            key3 = "ipv4_header" + str(num)
            key4 = "tcp_header" + str(num)

            ether[key2] = data[key1][:14]                                               # Store Ether header info in the dictionary
            # IHL = int.from_bytes(data[key1][14:15],"little")  
            IHL = struct.unpack("<B", data[key1][14:15])[0]                          # Get IP Version Number and IHL
            IHL = IHL & 0x0f                                                            # But we need only IHL, so use mask to get IHL only
            IHL = 4*IHL
            
            ipv4[key3] = data[key1][14:14+IHL]                                          # Store IPv4 header info in the dictionary

            # offset = int.from_bytes(data[key1][14+IHL+12:14+IHL+12+1],"little")         # Get tcp data offset
            offset = struct.unpack("<B", data[key1][14+IHL+12:14+IHL+12+1])[0]
            offset = offset >> 4
            # print(offset)

            tcp_length = 4*offset                                                       # 4 x offset = tcp header size
            tcp[key4] = data[key1][14+IHL:14+IHL+tcp_length]                            # Store TCP header info in the dictionary
        
            num += 1
        except:
            break

def analyze_connection(tcp_headers, tcp_status, ipv4_headers, packet_headers, c_seq_time):
    num = 0

    # orig_time is time when the first packet is recorded in cap file
    orig_seconds = struct.unpack('I',packet_headers["packet_header1"][:4])[0]
    orig_microseconds = struct.unpack('<I',packet_headers["packet_header1"][4:8])[0]
    orig_time = orig_seconds + orig_microseconds  *0.000001

    while True:
        try:
            syn = 0
            fin = 0
            rst = 0
            init_ts = 0
            end_ts = 0
            packet_StoD = 0
            packet_DtoS = 0
            bytes_StoD = 0
            bytes_DtoS = 0

            num += 1
            
            key = "tcp_header" + str(num)
            key1 = "ipv4_header" + str(num)
            key2 = "packet_header" + str(num)
   

            tcp = TCP_Header()
            source_port = tcp_headers[key][:2]
            dest_port = tcp_headers[key][2:4]
            seq = tcp_headers[key][4:8]
            ack = tcp_headers[key][8:12]
            offset = tcp_headers[key][12:13]
            flag = tcp_headers[key][13:14]
            window1 = tcp_headers[key][14:15]
            window2 = tcp_headers[key][15:16]

            tcp.get_src_port(source_port)
            tcp.get_dst_port(dest_port)
            tcp.get_seq_num(seq)
            tcp.get_ack_num(ack)
            tcp.get_data_offset(offset)
            tcp_head = tcp.data_offset
            tcp.get_flags(flag)
            tcp.get_window_size(window1,window2)

            ip = IP_Header()
            ip.get_header_len(ipv4_headers[key1][0:1])
            ip_head = ip.ip_header_len
            ip.get_total_len(ipv4_headers[key1][2:4])
            total = ip.total_len
            source_address = ipv4_headers[key1][12:16]
            dest_address = ipv4_headers[key1][16:20]
            ip.get_IP(source_address, dest_address)


            # Check if the TCP connection is already open or not  
            key3 = str(tcp.src_port) + "-" + str(tcp.dst_port)     
            alt_key = str(tcp.dst_port) + "-" + str(tcp.src_port)

            # If key3 in tcp_status, packet is sent from Source to Destination (ie, port 1200 -> 80)
            if key3 in tcp_status:
                tcp_status[key3][7] += 1
                bytes_StoD = total - ip_head - tcp_head
                
                tcp_status[key3][9] += bytes_StoD

                p = packet()

                ts_sec = packet_headers[key2][:4]
                ts_usec = packet_headers[key2][4:8]
                
                p.timestamp_set(ts_sec, ts_usec, orig_time)

                c_seq_time[tcp.seq_num + bytes_StoD] = p.timestamp

                tcp_status[key3][12].append(tcp.window_size)

            # If alt_key in tcp_status, packet is sent from Destination to Source (ie, port 80 -> 1200)
            elif alt_key in tcp_status:
                bytes_DtoS = total - ip_head - tcp_head
                
                key3 = alt_key
                tcp_status[key3][8] += 1
                tcp_status[key3][10] += bytes_DtoS

                tcp_status[key3][12].append(tcp.window_size)

                if tcp.ack_num in c_seq_time:
                    p = packet()

                    ts_sec = packet_headers[key2][:4]
                    ts_usec = packet_headers[key2][4:8]
                    
                    p.timestamp_set(ts_sec, ts_usec, orig_time)

                    tcp_status[key3][11].append(p.timestamp - c_seq_time[tcp.ack_num])

                    c_seq_time.pop(tcp.ack_num)

                
            # If key3 and alt_key missing, it's a new connection, so store it in tcp_status
            else:
                rtt = []
                window = []
                tcp_status[key3] = [syn, fin, rst, ip.src_ip, ip.dst_ip, init_ts, end_ts, packet_StoD, packet_DtoS, bytes_StoD, bytes_DtoS, rtt, window]    # If the connection hasn't been open yet, store it as new connection 
                tcp_status[key3][7] = 1
                bytes_StoD = total - ip_head - tcp_head
            
                tcp_status[key3][9] = bytes_StoD

                p = packet()

                ts_sec = packet_headers[key2][:4]
                ts_usec = packet_headers[key2][4:8]
                
                p.timestamp_set(ts_sec, ts_usec, orig_time)

                c_seq_time[tcp.seq_num + bytes_StoD] = p.timestamp

                tcp_status[key3][12].append(tcp.window_size)

                
            # Store # of SYNs, FINs and RSTs in dictionary
            if tcp.flags["SYN"] == 1:
                tcp_status[key3][0] += 1
            
            if tcp.flags["FIN"] == 1:
                tcp_status[key3][1] += 1

                ## Keep updating end time when FIN frag is set
                p = packet()

                ts_sec = packet_headers[key2][:4]
                ts_usec = packet_headers[key2][4:8]
                
                p.timestamp_set(ts_sec, ts_usec, orig_time)
                
                tcp_status[key3][6] = p.timestamp 

            if tcp.flags["RST"] == 1:
                tcp_status[key3][2] += 1

            if tcp_status[key3][0] == 1:
                ## Set initial time when the first SYN frag is set for a connection
                p = packet()

                ts_sec = packet_headers[key2][:4]
                ts_usec = packet_headers[key2][4:8]
                
                p.timestamp_set(ts_sec, ts_usec, orig_time)
                tcp_status[key3][5] = p.timestamp 
            
        except:
            break

# Check if a connection is complete
def is_complete(key, tcp_status):
    if tcp_status[key][0] == 0 or tcp_status[key][1] == 0:
        return False
    return True

# Check if a connection includes RST
def is_return(key, tcp_status):
    if tcp_status[key][2] != 0:
        return True
    return False
    
# Count # of complete, imcomplete, reset connections
def num_complete(tcp_status):
    complete_count = 0
    incomplete_count = 0
    reset_count = 0

    for key in tcp_status:
        if tcp_status[key][0] == 0 or tcp_status[key][1] == 0:
            incomplete_count += 1

        if tcp_status[key][2] != 0:
            reset_count += 1

    complete_count = len(tcp_status) - incomplete_count
    return complete_count, incomplete_count, reset_count

# Calculate Min, Mean, Max duration of all the complete connections
def duration_observe(tcp_status):
    true_duration = []
    for key in tcp_status:
        if is_complete(key, tcp_status):
            true_duration.append(tcp_status[key][6] - tcp_status[key][5])

    
    Min_duration = min(true_duration)
    Mean_duration = calc_mean(true_duration)
    Max_duration = max(true_duration)

    return Min_duration, Mean_duration, Max_duration

# Calculate Min, Mean, Max RTT of all the complete connections
def RTT_ovserve(tcp_status):
    true_values = []
    for key in tcp_status:
        if is_complete(key, tcp_status):
            for rtt in tcp_status[key][11]:
                true_values.append(rtt)
    
    Min_RTT = min(true_values)
    Mean_RTT = calc_mean(true_values)
    Max_RTT = max(true_values)

    return Min_RTT, Mean_RTT, Max_RTT

# Calculate Min, Mean, Max window size of all the complete connections
def window_size_observe(tcp_status):
    true_windows = []
    for key in tcp_status:
        if is_complete(key, tcp_status):
            for ws in tcp_status[key][12]:
                true_windows.append(ws)
    
    Min_WS = min(true_windows)
    Mean_WS = calc_mean(true_windows)
    Max_WS = max(true_windows)

    return Min_WS, Mean_WS, Max_WS

# Calculate Min, Mean, Max # of packets of all the complete connections
def packet_observe(tcp_status):
    true_packets = []
    for key in tcp_status:
        if is_complete(key, tcp_status):
            true_packets.append(tcp_status[key][7])
            true_packets.append(tcp_status[key][8])

    
    Min_Packet = min(true_packets)
    Mean_Packet = calc_mean(true_packets)
    Max_Packet = max(true_packets)

    return Min_Packet, Mean_Packet, Max_Packet

def calc_mean(values):
    total = 0
    for i in values:
        total += i
    mean = total/len(values)
    return mean


# Show the result
def show_result(tcp_status):
    num = 1

    complete_count, incomplete_count, reset_count = num_complete(tcp_status)

    Min_duration, Mean_duration, Max_duration = duration_observe(tcp_status)
    Min_RTT, Mean_RTT, Max_RTT = RTT_ovserve(tcp_status)
    Min_Packet, Mean_Packet, Max_Packet = packet_observe(tcp_status)
    Min_WS, Mean_WS, Max_WS = window_size_observe(tcp_status)

    print("A) Total number of connections: " + str(len(tcp_status)))
    print("\n----------------------------------------------------------------\n")
    print("B) Connections' details:\n")

    for key in tcp_status:
        ports = key.split("-")
        print("Connection " + str(num))
        print("Source Address: " + str(tcp_status[key][3]))
        print("Destination Address: " + str(tcp_status[key][4]))
        print("Source Port: " + str(ports[0]))
        print("Destination Port: " + str(ports[1]))
        if is_complete(key, tcp_status):
            if is_return(key, tcp_status):
                print("Status: S" + str(tcp_status[key][0]) + "F" + str(tcp_status[key][1]) + "/R")
            else:
                print("Status: S" + str(tcp_status[key][0]) + "F" + str(tcp_status[key][1]))
            print("Start Time: " + str(tcp_status[key][5]))
            print("End Time: " + str(tcp_status[key][6]))
            print("Duration: " + str(tcp_status[key][6] - tcp_status[key][5]))
            print("Number of packets sent from Source to Destination: " + str(tcp_status[key][7]))
            print("Number of packets sent from Destination to Source: " + str(tcp_status[key][8]))
            print("Total number of packets: " + str(tcp_status[key][7] + tcp_status[key][8]))
            print("Number of data bytes sent from Source to Destination: " + str(tcp_status[key][9]))
            print("Number of data bytes sent from Destination to Source: " + str(tcp_status[key][10]))
            print("Total number of data bytes: " + str(tcp_status[key][9] + tcp_status[key][10]))
            print("END")
            print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++\n")
        
        else:
            print("Status: S" + str(tcp_status[key][0]) + "F" + str(tcp_status[key][1]))
            print("END")
            print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++\n")
        
        num += 1


    print("C) General\n")
    print("Total number of complete TCP connections: " + str(complete_count))
    print("Number of reset TCP connections: " + str(reset_count))
    print("Number of TCP connections that were still open when the trace capture ended: " + str(incomplete_count))
    print("\n----------------------------------------------------------------\n")

    print("D) Complete TCP connections:\n")

    print("Minimum time duration:  " + str(Min_duration) + " sec")
    print("Mean time duration: " + str(Mean_duration) + " sec")
    print("Maximum time duration: " + str(Max_duration) + " sec")

    print("\nMinimum RTT value: " + str(Min_RTT) + " sec")
    print("Mean RTT value: " + str(Mean_RTT) + " sec")
    print("Maximum RTT value: " + str(Max_RTT) + " sec")

    print("\nMinimum number of packets including both send/received: " + str(Min_Packet))
    print("Mean number of packets including both send/received: " + str(Mean_Packet))
    print("Maximum number of packets including both send/received: " + str(Max_Packet))

    print("\nMinimum receive window size including both send/received: " + str(Min_WS))
    print("Mean receive window size including both send/received: " + str(Mean_WS))
    print("Maximum receive window size including both send/received: " + str(Max_WS))


        



if __name__ == "__main__":
    main()   