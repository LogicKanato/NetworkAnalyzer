def Pares(line):
    result = []
    print(line)
    line = line.split()
    result.append(line[2][:line[2].index(".")])
    result.append(line[6][line[6].index("[")+1:line[6].index("]")].replace("."," ACK"))

    if("seq" in line):
        temp = line[line.index("seq")+1]
        temp = "seq: " + temp
        result.append(temp)
    else:
        result.append("seq:?")

    if("ack" in line):
        temp = line[line.index("ack")+1]
        temp = "ack: " + temp
        result.append(temp)
    else:
        result.append("ack:?")

    if("win" in line):
        temp = line[line.index("win")+1]
        temp = "win: " + temp
        result.append(temp)
    else:
        result.append("win:?")

    if("length" in line):
        temp = line[line.index("length")+1]
        temp = "length: " + temp
        result.append(temp)
    else:
        result.append("length:?")

    for i in result:
        print(str(i) + " ", end = "")
    print()




with open("input.txt","r") as file:
    for line in file:
        Pares(line.strip())
        input()
