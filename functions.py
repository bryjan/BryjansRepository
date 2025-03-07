import math

def compass_bearing(pointA, pointB):
    # LICENSE: public domain
    """
    Calculates the bearing between two points.
    The formulae used is the following:
        θ = atan2(sin(Δlong).cos(lat2),
                  cos(lat1).sin(lat2) − sin(lat1).cos(lat2).cos(Δlong))
    :Parameters:
      - `pointA: The tuple representing the latitude/longitude for the
        first point. Latitude and longitude must be in decimal degrees
      - `pointB: The tuple representing the latitude/longitude for the
        second point. Latitude and longitude must be in decimal degrees
    :Returns:
      The bearing in degrees
    :Returns Type:
      float
    """
    if (type(pointA) != tuple) or (type(pointB) != tuple):
        raise TypeError("Only tuples are supported as arguments")

    lat1 = math.radians(pointA[0])
    lat2 = math.radians(pointB[0])

    diffLong = math.radians(pointB[1] - pointA[1])

    x = math.sin(diffLong) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1)
            * math.cos(lat2) * math.cos(diffLong))

    initial_bearing = math.atan2(x, y)

    # Now we have the initial bearing but math.atan2 return values
    # from -180° to + 180° which is not what we want for a compass bearing
    # The solution is to normalize the initial bearing as shown below
    initial_bearing = math.degrees(initial_bearing)
    compass_bearing = (initial_bearing + 360) % 360

    return compass_bearing

def neswDirection(pointA, pointB):
    
    bearing = compass_bearing(tuple(pointA), tuple(pointB))
    direction = f""

    if bearing >= 337.5 or bearing < 22.5:
        direction = f"North"
    elif bearing < 67.5:
        direction = f"North East"
    elif bearing < 112.5:
        direction = f"East"
    elif bearing < 157.5:
        direction = f"South East"
    elif bearing < 202.5:
        direction = f"South"
    elif bearing < 247.5:
        direction = f"South West"
    elif bearing < 292.5:
        direction = f"West"
    elif bearing < 337.5:
        direction = f"North West"

    return direction

def getCoordinateInput(matchInfo, inputQuery): #asks player for coordinates, inputQuery is a string of why they are entering coords
    playerInput= ""
    coordinate = []
    xyMax = len(matchInfo.map) - 1

    playerInput = input(inputQuery + '(eg. "xCoord,yCoord", or "x" to exit): ')
    while len(playerInput) == 0:
        playerInput = input(inputQuery + '(eg. "xCoord,yCoord", or "x" to exit): ')

    if playerInput == "x": #exit
        return

    seperatorCount = 0
    acceptedChars = ["1","2","3","4","5","6","7","8","9","0",","]
    for char in playerInput: #cleans up input
        if char == ",":
            seperatorCount += 1

        if char not in acceptedChars : 
            playerInput = playerInput.replace(char,"")

    #print("Test.... coord recieves as " + playerInput) #test

    if seperatorCount != 1:
        print("Did not use ',' to seperate coords, or used too many")
        return getCoordinateInput(matchInfo, inputQuery)

    if len(playerInput) < 3:
        print("Invalid Input")
        return getCoordinateInput(matchInfo, inputQuery)

    try:
        axisCoord = ""
        for char in playerInput: #seperates x and y using ',' as a seperator
            if char != ",": 
                axisCoord += char
            else:
                coordinate.append(int(str(axisCoord)))
                axisCoord = ""
        coordinate.append(int(str(axisCoord)))
    except:
        print("Invalid Input")
        return getCoordinateInput(matchInfo, inputQuery)


    for axis in coordinate:
        if axis > xyMax or axis < 0:
            print(str(coordinate) + " is not in the map.")
            return getCoordinateInput(matchInfo, inputQuery)

    return coordinate

