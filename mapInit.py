import random as r
import gameClasses as C
import gameObjects as O

#function to add a list of neighbors to a tile

def updateNeighbors(cell,mapArray):
    cell.neighborList=[]
    if cell.xPos>0 and cell.yPos>0 and cell.xPos<len(mapArray[0])-1 and cell.yPos<len(mapArray)-1:
        cell.neighborList.append(mapArray[cell.yPos+1][cell.xPos-1])#north west
        cell.neighborList.append(mapArray[cell.yPos+1][cell.xPos])#north
        cell.neighborList.append(mapArray[cell.yPos+1][cell.xPos+1])#north east
        cell.neighborList.append(mapArray[cell.yPos][cell.xPos-1])#west
        cell.neighborList.append(mapArray[cell.yPos][cell.xPos+1])#east
        cell.neighborList.append(mapArray[cell.yPos-1][cell.xPos-1])#south west
        cell.neighborList.append(mapArray[cell.yPos-1][cell.xPos])#south
        cell.neighborList.append(mapArray[cell.yPos-1][cell.xPos+1])#south east


def updateNeighborsNeighbors(cell,mapArray):
    for n in cell.neighborList:
        updateNeighbors(n,mapArray)
        
def updateAllNeighbors(mapArray):
    for rows in mapArray:
        for i in rows:
            updateNeighbors(i,mapArray)

#initial map population
#populates a list that will serve as a horizontal row then appends it to mapArray
def mapInit(mapSize):
    mapArray=[]
    xRow=[]
    y=0
    while y <= mapSize-1:
        x=0
        while x <= mapSize-1:
            cellName= str(x)+","+str(y)
            xRow.append(C.Cell(O.desert,x,y,cellName))
            x+=1
        mapArray.insert(0,xRow)
        y+=1
        xRow=[]
    updateAllNeighbors(mapArray)
    
    mapSize-=1
    tileCount= mapSize*mapSize
    mapSize+=1
    
    #initial seeding
    l=0
    while l<= int(tileCount*O.plainsParam.seedingRatio):
        x=r.randint(1,mapSize-1)
        y=r.randint(1,mapSize-1)
        mapArray[y][x].terrainType= O.plains
        updateNeighborsNeighbors(mapArray[y][x],mapArray)
        l+=1
    l=0
    while l<= int(tileCount*O.forestParam.seedingRatio):
        x=r.randint(1,mapSize-1)
        y=r.randint(1,mapSize-1)
        mapArray[y][x].terrainType= O.forest
        updateNeighborsNeighbors(mapArray[y][x],mapArray)
        l+=1
        
    #TODO simulate growth by making neighbors potentially switch
    l=0
    while l<O.plainsParam.genLoops:
        for y in mapArray:
            for x in y:
                for n in x.neighborList:
                    if n.terrainType==O.plains:
                        if O.plainsParam.conversionRoll()==True:
                            x.terrainType= O.plains
                            updateNeighborsNeighbors(x,mapArray)
        l+=1
    l=0
    while l<O.forestParam.genLoops:
        for y in mapArray:
            for x in y:
                for n in x.neighborList:
                    if n.terrainType==O.forest:
                        if O.forestParam.conversionRoll()==True:
                            x.terrainType= O.forest
                            updateNeighborsNeighbors(x,mapArray)
        l+=1
                    
    
                    
                
                
        
    
    #adding map borders
    for y in mapArray:
        for x in y:
            if x.yPos==0 or x.yPos==mapSize-1 or x.xPos==0 or x.xPos==mapSize-1:
                x.terrainType= O.border
    #return map
    return mapArray
