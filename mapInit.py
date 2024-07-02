import random as r
import gameClasses as C
import gameObjects as O

#variable initialization
mapArray=[]
xRow=[]

#TODO ensure odd 
mapSize=21

#to track (x,y) postitions
x=0
y=0

#function to add a list of neighbors to a tile
def updateNeighbors():
    for rows in mapArray:
        for i in rows:
            i.neighborList=[]
            if i.xPos>0 and i.yPos>0 and i.xPos<mapSize and i.yPos<mapSize:
                i.neighborList.append(mapArray[i.xPos-1][i.yPos+1])#north west
                i.neighborList.append(mapArray[i.xPos][i.yPos+1])#north
                i.neighborList.append(mapArray[i.xPos+1][i.yPos+1])#north east
                i.neighborList.append(mapArray[i.xPos-1][i.yPos])#west
                i.neighborList.append(mapArray[i.xPos+1][i.yPos])#east
                i.neighborList.append(mapArray[i.xPos-1][i.yPos-1])#south west
                i.neighborList.append(mapArray[i.xPos][i.yPos-1])#south
                i.neighborList.append(mapArray[i.xPos+1][i.yPos-1])#south east

#initial map population
#populates a list that will serve as a horizontal row then appends it to mapArray
while y <= mapSize-1:
    x=0
    while x <= mapSize-1:
        tile= C.TerrainTile(O.desert,x,y)
        xRow.append(tile)
        x+=1
    mapArray.insert(0,xRow)
    y+=1
    xRow=[]
y=0
x=0

#reduce mapSize by 1 to make counting from 0 easier
mapSize-=1

#TODO tile seeding and generation
#Seed ratios|pains 10 in 100| forest 7 in 100
mapSize-=1
tileCount= mapSize*mapSize
mapSize+=1

#initial seeding
l=0
while l<= int(tileCount*.1):
    mapArray[r.randint(1,mapSize-1)][r.randint(1,mapSize-1)].terrainType= O.plains
    l+=1
l=0
updateNeighbors()
#TODO simulate growth by making neighbors potentially switch

#adding map borders
for y in mapArray:
    for x in y:
        if x.yPos==0 or x.yPos==mapSize or x.xPos==0 or x.xPos==mapSize:
            x.terrainType= O.border

#for testing
for y in mapArray:
    for x in y:
        x.displayTile()
        print(" ",end='')
    print()