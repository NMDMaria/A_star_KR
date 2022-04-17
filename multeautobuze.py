import cProfile
from copy import deepcopy
import time
import os
import sys
import stopit


class Bus:
    """Models a bus that moves at constant time in between the stations in its route

    Note:
        Every bus can be identified by an unique tuple (self.nr, self.leaveTime, self.type)
    """

    def __init__(self, nr, route, leaveTime, travelTime, ticketPrice, type):
        """__init__

        Note:
             routeIndex keeps track of the current station index in the list route

        Params:
            :param nr: The number for the bus
            :param route: a list of String, the stations for the bus
            :param leaveTime: the time the bus left the depot
            :param travelTime: the time it takes the bus to get from one station to another
            :param ticketPrice: the price for the ticket
            :param type: normal for left to right, reverse for right to left

        """
        self.leaveTime = leaveTime
        self.travelTime = travelTime
        self.route = route
        self.nr = nr
        self.person = None  # Name of person on bus
        self.currentStation = self.route[0]
        self.routeIndex = 0
        self.ticketPrice = ticketPrice
        self.type = type  # Normal or reverse

    def findStation(self, station):
        """Provides acces to the index in the route list

        :param station: a string with the name of the station
        :return: index or None if the station isn't in this route
        """
        for index in range(len(self.route)):
            if self.route[index] == station:
                return index
        return None

    def move(self, time):
        """ Moves this bus accordingly with the time.

        Note:
            At leaveTime bus is in station with index 0.
            At leaveTime + i * travelTime bus is in station[i].

        :param time: time in minutes
        :return: True if the bus moves, False if it doesn't
        """
        # If the current time matches, we can find out where the bus moves
        if (time - self.leaveTime) % self.travelTime == 0:
            self.routeIndex = int((time - self.leaveTime) / self.travelTime)
            self.currentStation = self.route[self.routeIndex]
            return True

        return False

    def __str__(self):
        string = f"Nr: {self.nr} plecat la {self.leaveTime} la locatia {self.currentStation}"
        if self.person is not None:
            string += f" cu persoana {self.person}"
        string += "\n"
        return string

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if self.nr != other.nr or self.leaveTime != other.leaveTime or self.currentStation != other.currentStation or \
                self.routeIndex != other.routeIndex or self.person != other.person:
            return False
        return True


class BusSchema:
    """ Keeps the schema of the bus, but doesn't represent an actual moving bus
    """

    def __init__(self, nr, ticketPrice, tplec, travelTime, route):
        """ __init__

        :param nr: the number for the bus
        :param ticketPrice: the price for the bus
        :param tplec: time in minutes that buses leave the depots
        :param travelTime: time it takes one bus to move in between two stations
        :param route: list of string with the station names
        """
        self.nr = nr
        self.ticketPrice = ticketPrice
        self.tplec = tplec
        self.travelTime = travelTime
        self.route = route

        self.busesOnRoute = 0  # Number of buses that left the depots with this number
        self.nrDisappearedBuses = 0  # Number of buses that finished their route

    def findStation(self, station):
        """Provides acces to the index in the route list

        :param station: a string with the name of the station
        :return: index or None if the station isn't in this route
        """
        for index in range(len(self.route)):
            if self.route[index] == station:
                return index
        return None

    def __repr__(self):
        return f"{self.nr}, tplec = {self.tplec}, price = {self.ticketPrice}, travelTime = {self.travelTime}, route = {self.route}\n"


class Person:
    """Models a person"""

    def __init__(self, name, budget, destinations):
        """__init__

        :param name: indentifier string for person
        :param budget: float/int of the money this person has
        :param destinations: list of string with stations they need to visit
        """
        self.name = name
        self.budget = budget
        self.destinations = destinations
        self.nr_destinations = len(destinations)  # Easy access
        self.location = self.destinations[0]  # The person starts at his very first destination

        self.waitingTime = 0  # Total time person waited
        self.travelTime = 0  # Total time person travelled

        self.bus = None  # Identifying tuple (bus.nr, bus.leaveTime, bus.type) or None if person is waiting
        self.visited = 0  # Index of the visited stations
        self.status = "waiting"  # Person starts waiting in station

        self.lastAction = (
        "start", self.location, 0, None)  # tuple (action, location) so the person won't try to board/unboard infinetly
        # at the same location
        self.banned = {}  # List of the bus nr this person can't take till it boards another bus

    def moveAt(self, newLocation):
        """Moves the person at the location provided

        :param newLocation:
        :return: True if person was moved, False if it wasn't
        """
        if self.status != "travelling" or self.bus is None:
            return False  # the person isn't travelling. shouldn't be moved

        self.location = newLocation
        return True

    def __str__(self):
        string = f"{self.name}"
        string += f" Stare: {self.status}"
        string += f" La statia: {self.location}"
        string += f" Mai are de parcurs: {self.nr_destinations - self.visited}/{self.nr_destinations}"
        string += f" Buget: {self.budget}\n"
        string += f" Autobuz: {self.bus if self.bus is not None else None}"
        return string

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if self.name != other.name or self.bus != other.bus or self.location != other.location or self.waitingTime + \
                self.travelTime != other.travelTime + other.waitingTime or self.status != other.status or self.budget != \
                other.budget or self.visited != other.visited:
            return False
        return True


class Information:
    """Models a state in the solution

    Note:
        The change that makes a new state is an action, a person either boarding or unboarding a bus. So we keep track
        of the person and bus that triggered this new state

    """

    def __init__(self, busSchemas, persons, buses, time, action=None, nextTimes=[], person=None, bus=None):
        """__init__

        :param busSchemas: list of BusSchema
        :param persons: list of Person, persons that didn't finish their destinations
        :param buses: list of Bus, buses that are now on route
        :param time: the time in minutes that this state occured
        :param action: either "up" for boarding a bus, "down" or "finalizing" for unboarding the bus
        :param nextTimes: list of Int, keeps the times an action can take place
        :param person: person that triggered the change of state
        :param bus: bus that triggered the change of state
        """
        self.action = action
        self.busSchemas = sorted(busSchemas, key=lambda x: (x.ticketPrice, x.travelTime, x.tplec))
        self.person = person  # Person that triggered the new state
        self.bus = bus  # The bus the person got up/down from
        self.persons = persons  # The list of all the current persons
        self.time = time  # The time the action took place
        self.buses = buses  # All the buses on the route at the moment
        self.nextTimes = nextTimes  # List of times we are certain an action could take place

        self.minimumTicketPrice = min([x.ticketPrice for x in self.busSchemas])
        self.minimumTravelTime = min([x.travelTime for x in self.busSchemas])

    def getBus(self, nr, leaveTime, type):
        """Gets the index in self.buses for the bus indentified by the tuple (nr, leaveTime, type)

        :param nr: bus number
        :param leave_time: bus leaveTime
        :param type: bus type
        :return: index or None if bus is not in list
        """
        for index in range(len(self.buses)):
            if (self.buses[index].nr, self.buses[index].leaveTime, self.buses[index].type) == (nr, leaveTime, type):
                return index
        return None

    def getBusSchema(self, nr):
        """Gets the index of the bus schema according to the provided number

        :param nr: bus nr
        :return: index or None if busSchema is not in list
        """
        for index in range(len(self.busSchemas)):
            if self.busSchemas[index].nr == nr:
                return index
        return None

    def busesAtLocation(self, location, time):
        """

        :param location:
        :param time:
        :return:
        """
        # Location the buses are at
        # The time the buses are there
        # Because there are buses on move that have the location the last station they were at

        busesList = []
        for index in range(len(self.buses)):
            if self.buses[index].currentStation == location and \
                    time == self.buses[index].leaveTime + self.buses[index].routeIndex * self.buses[index].travelTime:
                # This bus is exactly at this location at the current time
                busesList.append((self.buses[index].nr, self.buses[index].leaveTime, self.buses[index].type))

        if len(busesList) == 0:  # No buses at location at time
            return None
        return busesList

    def getPerson(self, name):
        """Gets the index of the person with the name provided

        :param name: unique identifier for person
        :return: index or None if there is no person with that name
        """
        for index in range(len(self.persons)):
            if self.persons[index].name == name:
                return index
        return None

    def getPersonWaitingAt(self, location):
        """Gets the name of the person waiting at the location provided

        :param location: string of the station name
        :return: person name(string) or None if there's no person waiting in that location
        """
        personWaiting = None
        for index in range(len(self.persons)):
            if self.persons[index].status == "waiting" and self.persons[index].location == location:
                personWaiting = self.persons[index].name
                break
        return personWaiting

    def stopGenerating(self):
        """With different methods, tests if there's no possible state change from this state

        Test 1:
            checks if there's any person that can unboard a bus or a person that is waiting can get up the bus with the
            minimum ticket price

        Test 2:
            checks if all the persons have tried to board all the types of buses available

        Test 3:
            checks if there's at least one person that hasn't finished their destinations

        :return: True if there's no new state possible or False
        """
        if len(self.persons) == 0:  # Final state, should stop generating
            return True

        answer1 = True
        for index in range(len(self.persons)):
            if (self.persons[index].status == "waiting" and self.persons[index].budget - self.minimumTicketPrice >= 0 \
                and self.persons[index].visited != self.persons[index].nr_destinations - 1) \
                    or (self.persons[index].status == "travelling" \
                        and self.persons[index].visited != self.persons[index].nr_destinations - 1):
                # There is at least one person that can get up or down from a bus
                answer1 = False
                break
        if answer1:  # Hasn't passed the first test
            return True

        answer2 = True
        for index in range(len(self.persons)):
            if len(self.persons[index].banned.keys()) != 2 * len(self.busSchemas):
                # All persons have a successor where they get up/down from
                # every type of bus available
                answer2 = False
                break
        if answer2:  # Hasn't passed the second test
            return True

        answer3 = True
        for index in range(len(self.persons)):
            if self.persons[index].visited != self.persons[index].nr_destinations - 1:
                answer3 = False  # This is not a finishing state
                break
        if answer3:
            return True

        # answer4 = True
        # for personIndex in range(len(self.persons)):
        #     if not answer4:
        #         break
        #     for busIndex in range(len(self.busSchemas)):
        #         if self.persons[personIndex].status == "waiting" and \
        #                 self.persons[personIndex].location in self.busSchemas[busIndex].route \
        #                 and ((self.busSchemas[busIndex].nr, "normal") not in self.persons[personIndex].banned \
        #                      or (self.busSchemas[busIndex].nr, "reverse") not in self.persons[personIndex].banned):
        #             # The person can theoretically take this bus
        #             answer4 = False
        #             break
        #         if self.persons[personIndex].destinations[self.persons[personIndex].visited + 1] in \
        #                 self.busSchemas[busIndex].route:  # There's at least one bus that can get the person to
        #             # its next destination
        #             answer4 = False
        #             break
        # if answer4:  # Didn't pass this test
        #     return True

        return False

    def checkIfPossible(self):
        """Verifies if this is a valid state, meaning there is only one person waiting at a location

        :return: True if this state is valid, False otherwise
        """
        personsLocation = []
        for index in range(len(self.persons)):
            if self.persons[index].status == "waiting" and \
                    self.persons[index].location in personsLocation:
                # There's 2 persons at the same location! Something went wrong
                return False
            elif self.persons[index].status == "waiting":
                personsLocation.append(self.persons[index].location)
        return True

    def isFinal(self):
        """Checks if the state is final, all people finished visiting their destinations

        :return: True if all persons finished, false otherwise
        """
        if len(self.persons) == 0:
            # At some point all persons finished their route
            return True
        for index in range(len(self.persons)):
            if self.persons[index].visited != self.persons[index].nr_destinations - 1:
                return False
        # All persons have visited all their destinations
        return True

    def __str__(self):
        s = f"{self.action} Timp = {self.time} \n"
        s += f"Persoana care isi schimba actiunea: {self.person}"
        s += "\nPersoane:"
        for person in self.persons:
            s += str(person) + "\n"
        s += "\nAutobuze:"
        for bus in self.buses:
            if bus.person != None:
                s += str(bus) + "\n"
        return s

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if self.time != other.time or len(self.persons) != len(other.persons) or len(self.buses) != len(other.buses):
            return False
        for indexPerson in range(len(self.persons)):
            otherIndexPerson = other.getPerson(self.persons[indexPerson].name)
            if otherIndexPerson is None:
                return False
            if self.persons[indexPerson] != other.persons[otherIndexPerson]:
                return False
        for indexBus in range(len(self.buses)):
            otherBusIndex = other.getBus(self.buses[indexBus].nr, self.buses[indexBus].leaveTime,
                                         self.buses[indexBus].type)
            if self.buses[indexBus] != other.buses[otherBusIndex]:
                return False
        return True


class Node:
    """Node in the solution graph
    """

    def __init__(self, info, parent, cost, h, waitingTime, moneySpent, startTime):
        """__init__

        :param info: type Information
        :param parent: the parent node, None if root
        :param cost: cost of reaching this state
        :param h: an heuristic of the cost it takes to reach the final state from this state
        :param waitingTime: total waiting time
        :param moneySpent: total money spent by the persons
        :param startTime: string of start time (HH:MM)
        """
        self.info = info
        self.parent = parent
        self.cost = cost
        self.h = h
        self.waitingTime = waitingTime
        self.moneySpent = moneySpent
        self.f = self.cost + self.h
        self.startTime = startTime

    def getPath(self):
        """Makes a path from this node to it's root

        :return: list of Node
        """
        l = [self]
        node = self
        while node.parent is not None:
            l.insert(0, node.parent)
            node = node.parent
        return l

    def pathString(self):
        """Formats the node state

        :return: string
        """

        path = self.getPath()
        counter = 1  # Counting the nodes in the path

        lastCost = 0
        listString = []
        start = timeToMinutes(self.startTime)
        time = self.startTime
        lastTime = self.startTime
        personStrings = {}
        for node in path:
            if node.parent is None:  # No valuable information
                lastTime = time
                time = minutesToTime(node.info.time + start)
                continue
            time = minutesToTime(int(node.info.time + start))  # The formated node time
            if time != lastTime:  # We have all the actions at the time
                listString.append(f"{str(counter)})\n{lastTime}\n")
                # Each person has a list of actions, because they can unboard a bus and immediately board another one
                for name in sorted(personStrings.keys()):
                    for action in personStrings[name]:
                        listString.append(f"{action}\n")
                personStrings = {}
                listString.append(f"Cost pana acum {str(int(lastCost) if int(lastCost) == float(lastCost) else float(lastCost))}  \n")
                counter += 1

            if node.info.action == "finished":  # The person isn't in the list anymore
                aux = f"Omul {node.info.person.name}"
                aux += f" a coborat in statia {node.info.person.location} din autobuzul {node.info.bus.nr} si si-a terminat traseul"
                aux += f". Buget: {str(int(node.info.person.budget) if int(node.info.person.budget) == float(node.info.person.budget) else float(node.info.person.budget))}lei. Timp mers: {str(int(node.info.person.travelTime)) if int(node.info.person.travelTime) == float(node.info.person.travelTime) else float(node.info.person.travelTime)}min. Timp asteptare: {str(int(node.info.person.waitingTime) if int(node.info.person.waitingTime) == float(node.info.person.waitingTime) else float(node.info.person.waitingTime))}min"
                personStrings.update({node.info.person.name: [aux]})
            for person in node.info.persons:
                aux = f"Omul {person.name}"
                if node.info.person.name == person.name:
                    # An action took place for this person
                    if node.info.action == "up":
                        aux += f" a urcat in statia {person.location} in autobuzul {str(node.info.bus.nr)} pentru traseul " + "->".join(
                            node.info.bus.route[node.info.bus.findStation(person.location):])
                        aux += f". Buget: {str(int(person.budget) if int(person.budget) == float(person.budget) else float(person.budget))}lei. Timp mers: {str(int(person.travelTime) if int(person.travelTime) == float(person.travelTime) else float(person.travelTime))}min. Timp asteptare: {str(int(person.waitingTime) if int(person.waitingTime) == float(person.waitingTime) else float(person.waitingTime))}min"
                    elif node.info.action == "down":
                        aux += f" a coborat in statia {person.location} din autobuzul {str(node.info.bus.nr)}."
                        aux += f" Buget: {str(int(person.budget) if int(person.budget) == float(person.budget) else float(person.budget))}lei. Timp mers: {str(int(person.travelTime) if int(person.travelTime) == float(person.travelTime) else float(person.travelTime))}min. Timp asteptare: {str(int(person.waitingTime) if int(person.waitingTime) == float(person.waitingTime) else float(person.waitingTime))}min"
                    if person.name not in personStrings:
                        personStrings[person.name] = [aux]
                    else:
                        # We keep only the actions, because at the same time one person was waiting and in the next node
                        # at the same exact time the person boarded, we want to keep only the boarding action
                        personStrings[person.name] = [string for string in personStrings[person.name] \
                                                      if string.find("coborat") != -1 or string.find("urcat") != -1]
                        personStrings[person.name].append(aux)
                elif person.name not in personStrings.keys() or len([string for string in personStrings[person.name] \
                                                                     if string.find("coborat") != -1 or string.find(
                        "urcat") != -1]) == 0:
                    # Checking if the person hasn't already had an action made
                    if person.status == "waiting":
                        aux += f" asteapta in statia {person.location}. Buget: {str(int(person.budget) if int(person.budget) == float(person.budget) else float(person.budget))}lei. Timp mers: {str(int(person.travelTime) if int(person.travelTime) == float(person.travelTime) else float(person.travelTime))}min. Timp asteptare: {str(int(person.waitingTime) if int(person.waitingTime) == float(person.waitingTime) else float(person.waitingTime))}min"
                    else:
                        bus = node.info.buses[node.info.getBus(person.bus[0], person.bus[1], person.bus[2])]
                        aux += f" se deplaseaza cu autobuzul {str(bus.nr)} de la statia {bus.currentStation} la statia {bus.route[bus.routeIndex + 1]} pe traseul " + "->".join(
                            bus.route[bus.findStation(bus.currentStation):])
                        aux += f"Buget: {str(int(person.budget) if int(person.budget) == float(person.budget) else float(person.budget))}lei. Timp mers: {str(int(person.travelTime) if int(person.travelTime) == float(person.travelTime) else float(person.travelTime))}min. Timp asteptare: {str(int(person.waitingTime) if int(person.waitingTime) == float(person.waitingTime) else float(person.waitingTime))}min"
                    personStrings.update({person.name: [aux]})

            lastCost = node.cost
            lastTime = time

        # Processing the last node too
        node = path[-1]
        if node.info.action != "finished":
            # This action being the final one, definitely is of a person finishing
            print("The last action isn't a person finishing")
            exit()
        aux = f"Omul {node.info.person.name} a coborat in statia {node.info.person.location} din autobuzul {str(node.info.bus.nr)} si si-a terminat traseul"
        aux += f". Buget: {str(int(node.info.person.budget) if int(node.info.person.budget) == float(node.info.person.budget) else float(node.info.person.budget))}lei. Timp mers: {str(int(node.info.person.travelTime)) if int(node.info.person.travelTime) == float(node.info.person.travelTime) else float(node.info.person.travelTime)}min. Timp asteptare: {str(int(node.info.person.waitingTime) if int(node.info.person.waitingTime) == float(node.info.person.waitingTime) else float(node.info.person.waitingTime))}min"
        personStrings.update({node.info.person.name: [aux]})
        listString.append(f"{str(counter)})\n{minutesToTime(node.info.time + start)}\n")
        for name in sorted(personStrings.keys()):
            for action in personStrings[name]:
                listString.append(f"{action}\n")
        listString.append(f"Cost pana acum {str(int(lastCost) if int(lastCost) == float(lastCost) else float(lastCost))}  \n")
        counter += 1
        return len(path), "".join(listString)

    def isInPath(self, newNode):
        """Checks if the node is in the path from the root to this node

        :return: True if node is in path, False otherwise
        """
        node = self
        while node is not None:
            if newNode.info == node.info:
                return True
            node = node.parent

        return False

    def isFinal(self):
        """Checks if the node is final

        :return: True or False
        """
        if len(self.info.persons) == 0:
            # At some point all persons finished their route
            return True
        for index in range(len(self.info.persons)):
            if self.info.persons[index].visited != self.info.persons[index].nr_destinations - 1:
                return False
        # All persons have visited all their destinations
        return True

    def __str__(self):
        sir = ""
        sir += str(self.info)
        sir += "g:{}".format(self.cost)
        sir += " h:{}".format(self.h)
        sir += " f:{})".format(self.f)
        sir += " moneySpent: {}".format(self.moneySpent)
        sir += " timeSpent: {}".format(self.waitingTime)
        return sir


def timeToMinutes(time):
    """Transforms the time in minutes

    :param time: string, formatted HH:MM
    :return: time in minutes
    """
    t = 0
    for u in time.split(':'):
        t = 60 * t + int(u)
    return t


def minutesToTime(minutes):
    """Transforms the minutes in a time formatted HH:MM

    :param minutes: int, time in minutes
    :return: string formatted HH:MM
    """
    return '{:02d}:{:02d}'.format(*divmod(int(minutes), 60))


class Graph:
    """Models the solution graph
    """

    def __init__(self, startTime, endTime, startNode):
        """__init__

        :param startTime: time (HH:MM) the simulation starts
        :param endTime: time (HH:MM) the simulation ends
        :param startNode: root of graph
        """
        self.endTime = endTime
        self.startTime = startTime

        # This is the the time in minutes that the generation should end
        # considering that startTime is minute 0
        self.duration = timeToMinutes(endTime) - timeToMinutes(startTime)

        self.startNode = startNode
        self.startNode.info.time = 0  # Making sure that the root
        # starts at time 0

    def isFinal(self, nodCurent):
        return nodCurent.info.isFinal()

    def genereazaSuccesori(self, nodCurent, tip_euristica="euristica banala"):
        """Generates all possible children nodes from the node provided

        :param nodCurent: node for checking
        :param tip_euristica: type of heuristic
        :return: list of Node
        """
        listaSuccesori = []

        current = deepcopy(nodCurent.info)
        # So we won't modify something

        time = int(current.time)
        lastTime = time
        nextTimes = current.nextTimes
        breakFlag = False

        # Going to generate everything from that duration
        while time <= self.duration and not breakFlag:
            if current.stopGenerating():
                # There's no more actions that could happen
                break
            if not current.checkIfPossible():
                print("Something went very wrong :(")
                exit()
            possibleActions = []

            # print(f"\n\n-----------------------{time}-------------------------------")
            # First we check if we can add buses on the route
            # making sure that we don't add them if they were already added

            for busSchema in current.busSchemas:
                if time % busSchema.tplec == 0:
                    # This is a time where buses leave

                    # print("Ar trebui sa adaugam autobuze, verificam daca nu cumva le-am adaugat deja!")
                    # print(f"Nr. autobuze plecate pe traseu: {busSchema.busesOnRoute}, "
                    #      f"nr. de autobuze disparute: {busSchema.nrDisappearedBuses}")
                    # print(f"Nr. autobuze ce ar trb sa fi plecat "
                    #      f"{2 * (time / busSchema.tplec) + 2 },"
                    #      f"nr ce au plecat: {busSchema.busesOnRoute}")

                    if busSchema.busesOnRoute > 2 * (time / busSchema.tplec) + 2:
                        # print("Should now add buses!")
                        continue
                        # print(nodCurent)
                        # print(current)

                    if 2 * (time / busSchema.tplec) + 2 > busSchema.busesOnRoute:
                        # We need to add 2 buses, one from the very left station and one from the very right
                        busSchema.busesOnRoute += 2
                        # Because every action can take place only at appearance of buses or when buses reach
                        # a new station we can make a list of the times we need to check
                        if time + busSchema.tplec not in nextTimes:
                            # print(f"Actiune viitoare la timpul {time + busSchema.tplec}")
                            nextTimes.append(time + busSchema.tplec)
                        if time + busSchema.travelTime not in nextTimes:
                            # print(f"Actiune viitoare la timpul {time + busSchema.travelTime}")
                            nextTimes.append(time + busSchema.travelTime)
                        # print(f"Autobuze noi pe nr {busSchema.nr}")
                        newBus = Bus(busSchema.nr, busSchema.route, time,  # the time the bus went on route
                                     busSchema.travelTime, busSchema.ticketPrice, "normal")  # from left to right
                        current.buses.append(newBus)  # add it to the list
                        personName = current.getPersonWaitingAt(newBus.currentStation)

                        if personName is not None:
                            personIndex = current.getPerson(personName)
                            if (newBus.nr, newBus.type) not in current.persons[personIndex].banned.keys() \
                                    and current.persons[personIndex].budget - newBus.ticketPrice >= 0 \
                                    and not (current.persons[personIndex].lastAction[0] == "down" and \
                                             current.persons[personIndex].lastAction[3] == newBus.nr):
                                # The person can board the bus! So we mark it to know when we finish
                                # to add/move all buses at the time
                                # print(f"Autobuz nou, persoana nebanata in statie {personName} => POSIBILA STARE")
                                updatedPerson = deepcopy(current.persons[personIndex])
                                updatedPerson.status = "travelling"
                                updatedPerson.budget -= newBus.ticketPrice
                                # The banned buses for the person are reset
                                # and we mark the bus they're boarding, so they won't try
                                # to get back up the one they got down from
                                updatedPerson.banned = {}
                                updatedPerson.bus = (newBus.nr, newBus.leaveTime, newBus.type)

                                updatedBus = deepcopy(newBus)
                                updatedBus.person = updatedPerson.name
                                if updatedPerson.waitingTime + updatedPerson.travelTime != time:
                                    updatedPerson.waitingTime += (time - lastTime)
                                updatedPerson.lastAction = ("up", newBus.currentStation, time, newBus.nr)
                                possibleActions.append(["up", updatedPerson, updatedBus])

                                # Now we have to ban the bus for the actual person we have
                                # because we generated an action of them boarding this type of bus
                                current.persons[personIndex].banned.update({(newBus.nr, newBus.type): time})
                        # If there's no person in station or the person can't get on the bus
                        # no action is left

                        newBus = Bus(busSchema.nr, busSchema.route[::-1], time,  # the time the bus went on route
                                     busSchema.travelTime, busSchema.ticketPrice, "reverse")  # from right to left
                        # so we reverse the route
                        current.buses.append(newBus)  # add it to the list
                        personName = current.getPersonWaitingAt(newBus.currentStation)

                        if personName is not None:
                            personIndex = current.getPerson(personName)
                            if (newBus.nr, newBus.type) not in current.persons[personIndex].banned.keys() \
                                    and current.persons[personIndex].budget - newBus.ticketPrice >= 0 and \
                                    not (current.persons[personIndex].lastAction[0] == "down" and \
                                         current.persons[personIndex].lastAction[3] == newBus.nr):
                                # The person can board the bus! So we mark it to know when we finish
                                # to add/move all buses at the time
                                # print(f"Autobuz nou, persoana nebanata in statie {personName} => POSIBILA STARE")

                                updatedPerson = deepcopy(current.persons[personIndex])
                                updatedPerson.status = "travelling"
                                updatedPerson.budget -= newBus.ticketPrice
                                # The banned buses for the person are reset
                                # and we mark the bus they're boarding, so they won't try
                                # to get back up the one they got down from
                                updatedPerson.banned = {}
                                updatedPerson.bus = (newBus.nr, newBus.leaveTime, newBus.type)
                                if updatedPerson.waitingTime + updatedPerson.travelTime != time:
                                    updatedPerson.waitingTime += (time - lastTime)
                                updatedBus = deepcopy(newBus)
                                updatedBus.person = updatedPerson.name
                                updatedPerson.lastAction = ("up", newBus.currentStation, time, newBus.nr)
                                possibleActions.append(["up", updatedPerson, updatedBus])

                                # Now we have to ban the bus for the actual person we have
                                # because we generated an action of them boarding this type of bus
                                current.persons[personIndex].banned.update({(newBus.nr, newBus.type): time})
                        # If there's no person in station or the person can't get on the bus
                        # no action is left

            # Finished adding buses
            # Checking if there's any buses that are moving!

            busIndex = 0
            while busIndex < len(current.buses):
                if current.buses[busIndex].move(time):
                    # The bus reaches it's next station, move the person if there's one
                    # Add the next possible time, we know it will reach the next destination in travelTime minutes

                    if current.buses[busIndex].travelTime + time not in nextTimes:
                        nextTimes.append(current.buses[busIndex].travelTime + time)

                    if current.buses[busIndex].person is not None:
                        personIndex = current.getPerson(current.buses[busIndex].person)
                        if not current.persons[personIndex].moveAt(current.buses[busIndex].currentStation):
                            print("Something went wrong. Person should have been travelling")
                            exit()

                        # Now that the person moved, we check if they can get down the bus at this station
                        if current.getPersonWaitingAt(current.buses[busIndex].currentStation) is None:
                            # The person can get down because they'll be the only one at the station

                            # print(f"{current.buses[busIndex].person} poate sa coboare => POSIBILA STARE")
                            # If the person just got up a bus at this station, don't let him go down and up another bus
                            if not (current.persons[personIndex].lastAction[0] == "up" and
                                    current.persons[personIndex].lastAction[2] == time and
                                    current.persons[personIndex].lastAction[1] ==
                                    current.persons[personIndex].location) \
                                    and not (current.action == "finished" and current.person.location == \
                                             current.persons[personIndex].location):
                                updatedPerson = deepcopy(current.persons[personIndex])
                                updatedPerson.status = "waiting"
                                updatedPerson.bus = None
                                if updatedPerson.destinations[updatedPerson.visited + 1] == updatedPerson.location:
                                    # The person got down at the station they wanted, so we mark it as visited
                                    updatedPerson.visited += 1
                                updatedPerson.lastAction = (
                                "down", current.buses[busIndex].currentStation, time, current.buses[busIndex].nr)
                                updatedBus = deepcopy(current.buses[busIndex])
                                updatedBus.person = None
                                # Mark the bus as banned, so the person won't go down and then get up
                                # the same bus
                                updatedPerson.banned.update(
                                    {(current.buses[busIndex].nr, current.buses[busIndex].type): time})
                                if updatedPerson.waitingTime + updatedPerson.travelTime != time:
                                    updatedPerson.travelTime += (time - lastTime)
                                if updatedPerson.visited == updatedPerson.nr_destinations - 1:
                                    # The person reached it's end destination, so finished
                                    possibleActions.append(["finished", updatedPerson, updatedBus])
                                else:
                                    possibleActions.append(["down", updatedPerson, updatedBus])

                            # We have to check if the bus reached it's final station, so will disappear
                            if current.buses[busIndex].currentStation == current.buses[busIndex].route[-1]:
                                # Break the generating. We don't want the person to disappear along with the bus
                                # print(f"Bus {(current.buses[busIndex].nr, current.buses[busIndex].leaveTime, current.buses[busIndex].type)} dispare")
                                indexBusSchema = current.getBusSchema(current.buses[busIndex].nr)
                                current.buses.pop(busIndex)
                                current.busSchemas[indexBusSchema].nrDisappearedBuses += 1
                                breakFlag = True  # So we know we stop everything
                                break
                        elif current.buses[busIndex].currentStation == current.buses[busIndex].route[-1]:
                            # There's a person waiting, a person in the bus, and the bus is gonna dissapear!
                            # So we need to end generating succesors
                            breakFlag = True  # So we know we stop everything
                            break
                    else:
                        # We know for sure there's no person in the bus
                        # so we find someone to board it, but before this we need to check if the bus reached its end
                        # if so, there's no reason to have someone board so we just remove it

                        personName = current.getPersonWaitingAt(current.buses[busIndex].currentStation)

                        if current.buses[busIndex].currentStation == current.buses[busIndex].route[-1]:
                            # print(f"Bus {(current.buses[busIndex].nr, current.buses[busIndex].leaveTime, current.buses[busIndex].type)} dispare")
                            # Reached final station, no person in bus, we don't care if person is waiting
                            if personName is not None:
                                # print("Are persoana in statie")
                                personIndex = current.getPerson(personName)
                                if (current.buses[busIndex].nr, current.buses[busIndex].type) not in \
                                        current.persons[personIndex].banned.keys():
                                    current.persons[personIndex].banned.update({(
                                                                                    current.buses[busIndex].nr,
                                                                                    current.buses[
                                                                                        busIndex].type): time})
                            indexBusSchema = current.getBusSchema(current.buses[busIndex].nr)
                            current.buses.pop(busIndex)
                            current.busSchemas[indexBusSchema].nrDisappearedBuses += 1

                            continue  # Go to the next bus

                        if personName is not None:
                            personIndex = current.getPerson(personName)
                            # Generate succesor where person boards this bus
                            if (current.buses[busIndex].nr, current.buses[busIndex].type) not in \
                                    current.persons[personIndex].banned.keys() or \
                                    current.persons[personIndex].banned[
                                        (current.buses[busIndex].nr, current.buses[busIndex].type)] == time \
                                    and current.persons[personIndex].budget - current.buses[
                                busIndex].ticketPrice >= 0 and \
                                    not (current.persons[personIndex].lastAction[0] == "down" and \
                                         current.persons[personIndex].lastAction[3] == current.buses[busIndex].nr):

                                # print(f"{personName} poate sa urce => POSIBILA STARE")
                                updatedPerson = deepcopy(current.persons[personIndex])
                                updatedPerson.status = "travelling"
                                updatedPerson.budget -= current.buses[busIndex].ticketPrice
                                # The banned buses for the person are reset
                                # and we mark the bus they're boarding, so they won't try
                                # to get back up the one they got down from
                                updatedPerson.banned = {}
                                updatedPerson.bus = (current.buses[busIndex].nr, current.buses[busIndex].leaveTime,
                                                     current.buses[busIndex].type)
                                updatedPerson.lastAction = (
                                "up", current.buses[busIndex].currentStation, time, current.buses[busIndex].nr)
                                updatedBus = deepcopy(current.buses[busIndex])
                                updatedBus.person = updatedPerson.name
                                if updatedPerson.waitingTime + updatedPerson.travelTime != time:
                                    updatedPerson.waitingTime += (time - lastTime)
                                possibleActions.append(["up", updatedPerson, updatedBus])

                                # Now we have to ban the bus for the actual person we have
                                # because we generated an action of them boarding this type of bus
                                current.persons[personIndex].banned.update({
                                    (current.buses[busIndex].nr, current.buses[busIndex].type): time})
                            elif (current.buses[busIndex].nr, current.buses[busIndex].type) not in \
                                    current.persons[personIndex].banned.keys():
                                # The person didn't have money to board it. We need to ban it so won't try again
                                current.persons[personIndex].banned.update({
                                    (current.buses[busIndex].nr, current.buses[busIndex].type): time})
                busIndex += 1

            # Finished moving everything

            # Updating the persons waiting time/travelling time
            for personIndex in range(len(current.persons)):
                if current.persons[personIndex].status == "waiting":
                    if time < current.time:
                        print(nodCurent)
                        exit()
                    current.persons[personIndex].waitingTime += (time - lastTime)
                else:
                    if time < current.time:
                        print(nodCurent)
                        exit()
                    current.persons[personIndex].travelTime += (time - lastTime)

            # We see what actions took place, and update
            for actionIndex in range(len(possibleActions)):
                # print(possibleActions[actionIndex][0], possibleActions[actionIndex][1])
                # Preparing to create a new node
                moveCost = 0
                moneyCost = 0
                timeCost = 0

                if possibleActions[actionIndex][0] == "up":  # Check the type of action
                    # We need to add the cost
                    moneyCost += possibleActions[actionIndex][2].ticketPrice
                    moveCost += possibleActions[actionIndex][2].ticketPrice
                newPersons = deepcopy(current.persons)
                newBuses = deepcopy(current.buses)
                moveCost += (time - nodCurent.info.time) * len(newPersons)
                timeCost += (time - nodCurent.info.time) * len(newPersons)
                # Update the person in the list
                personIndex = current.getPerson(possibleActions[actionIndex][1].name)
                if personIndex is None:
                    print("Person should have been in list")
                    exit()
                if possibleActions[actionIndex][0] == "finished":
                    # Person finished, no need to take it in consideration anymore
                    newPersons.pop(personIndex)
                else:
                    newPersons[personIndex] = possibleActions[actionIndex][1]
                busIndex = current.getBus(possibleActions[actionIndex][2].nr, possibleActions[actionIndex][2].leaveTime,
                                          possibleActions[actionIndex][2].type)
                if busIndex is None and possibleActions[actionIndex][0] == "up":
                    print("Person boarded a bus that disapeared")
                    exit()
                elif busIndex is not None:
                    newBuses[busIndex] = possibleActions[actionIndex][2]

                possibleNodeInfo = Information(deepcopy(current.busSchemas), newPersons, newBuses, time, \
                                               action=possibleActions[actionIndex][0], nextTimes=deepcopy(nextTimes),
                                               person=possibleActions[actionIndex][1],
                                               bus=possibleActions[actionIndex][2])
                possibleNode = Node(possibleNodeInfo, nodCurent, moveCost + nodCurent.cost,
                                    self.calculeaza_h(possibleNodeInfo, tip_euristica),
                                    timeCost, moneyCost, self.startTime)

                if not nodCurent.isInPath(possibleNode):
                    listaSuccesori.append(possibleNode)

            if breakFlag:  # need to end the execution!
                break
            # Move to the next time
            if len(nextTimes) == 0:  # There's no action that can take place
                break

            nextTimes.sort()
            lastTime = time
            time = nextTimes[0]
            nextTimes = nextTimes[1:]

        # Finished seeing all possible actions that could happen
        return listaSuccesori

    def calculeaza_h(self, infoNod, tip_euristica="euristica banala"):
        """Calculates an heuristic, the cost of the state reaching final state

        :param infoNod: state checked
        :param tip_euristica: string of type, either "euristica banala", "euristica admisbila 1", "euristica admisibila 2",
         "euristica neadmisibila"
        :return: int, the supposed cost
        """
        if tip_euristica == "euristica banala":
            # There's at least one move to be made, with the minimum cost 0
            # if the node isn't final
            if not infoNod.isFinal():
                return 1
            return 0
        elif tip_euristica == "euristica admisibila 1":
            # Assuming every person takes for every remaining destination a new bus, the one with the minimum
            # ticket price, ignoring the time
            h = 0
            for personIndex in range(len(infoNod.persons)):
                if infoNod.persons[personIndex].status == "waiting":  # Assume they get on the cheapest bus
                    h += infoNod.minimumTicketPrice + infoNod.minimumTravelTime
            return h
        elif tip_euristica == "euristica admisibila 2":
            # Assuming that the person with the most destinations travels with the bus
            # with the minimum time in betweeen stations
            # and by that time every other person finished
            # each person taking at least one bus with the minimum ticket price
            max_destinations = [infoNod.persons[personIndex].nr_destinations - infoNod.persons[personIndex].visited \
                                for personIndex in range(len(infoNod.persons))]
            if len(max_destinations) == 0:
                max_destinations = 0
            else:
                max_destinations = max(max_destinations)
            h = max_destinations * infoNod.minimumTravelTime
            return h
        elif tip_euristica == "euristica admisibila 3":
            max_destinations = [infoNod.persons[personIndex].nr_destinations - infoNod.persons[personIndex].visited \
                                for personIndex in range(len(infoNod.persons))]
            if len(max_destinations) == 0:
                max_destinations = 0
            else:
                max_destinations = max(max_destinations)
            h = max_destinations * infoNod.minimumTravelTime
            for personIndex in range(len(infoNod.persons)):
                if infoNod.persons[personIndex].status == "waiting":  # Assume they get on the cheapest bus
                    h += infoNod.minimumTicketPrice
            return h
        elif tip_euristica == "euristica neadmisibila":
            # Assuming every person takes for every remaining destination a new bus, the one with the maximum
            # ticket price
            maxTicketPrice = [busSchema.ticketPrice for busSchema in infoNod.busSchemas]
            max_destinations = [infoNod.persons[personIndex].nr_destinations - infoNod.persons[personIndex].visited \
                                for personIndex in range(len(infoNod.persons))]
            maxTravelTime = [busSchema.travelTime for busSchema in infoNod.busSchemas]
            if len(max_destinations) == 0:
                max_destinations = 0
            else:
                max_destinations = max(max_destinations)
            if len(maxTicketPrice) == 0:
                maxTicketPrice = 0
            else:
                maxTicketPrice = max(maxTicketPrice)
            if len(maxTravelTime) == 0:
                maxTravelTime = 0
            else:
                maxTravelTime = max(maxTravelTime)
            h = len(infoNod.persons) * max_destinations * maxTravelTime + len(infoNod.persons) * maxTicketPrice
            return h

    def __repr__(self):
        sir = ""
        for (k, v) in self.__dict__.items():
            sir += "{} = {}\n".format(k, v)
        return (sir)


@stopit.threading_timeoutable(default="Stopped because of timeout")
def breadth_first(gr, nrSolutiiCautate, tip_euristica):
    startTime = time.time()
    c = [Node(gr.startNode.info, None, 0, gr.calculeaza_h(gr.startNode.info), 0, 0, gr.startTime)]

    solutions = []
    maxNodesMemory = 0
    nodesCalculated = 0

    while len(c) > 0:
        nodCurent = c.pop(0)

        if gr.isFinal(nodCurent):
            nrNodes, string = nodCurent.pathString()
            solution = "".join(["Solutie: \n", string, f"Lungimea drumului este: {str(nrNodes - 1)} \n",
                                f"Costul drumului este: {str(nodCurent.cost)}\n"])
            solution.join(f"Lungimea drumului este: {str(nrNodes)} \n")
            solution += "Numarul maxim de noduri in memorie: " + str(maxNodesMemory) + "\n"
            solution += "Numarul total de noduri calculate: " + str(nodesCalculated) + "\n"
            solution += "Solutia a fost gasita in " + str(time.time() - startTime) + "\n"
            solutions.append(solution)
            nrSolutiiCautate -= 1
            if nrSolutiiCautate == 0:
                return solutions
        lSuccesori = gr.genereazaSuccesori(nodCurent, tip_euristica)
        nodesCalculated += len(lSuccesori)
        c.extend(lSuccesori)
        maxNodesMemory = max(maxNodesMemory, len(c))
    return solutions


@stopit.threading_timeoutable(default="Stopped because of timeout")
def depth_first(gr, nrSolutiiCautate, tip_euristica):
    startTime = time.time()
    solutions = []

    df(gr, Node(gr.startNode.info, None, 0, gr.calculeaza_h(gr.startNode.info), 0, 0, gr.startTime), nrSolutiiCautate,
       tip_euristica,
       solutions, startTime, [0, 0])
    return solutions


def df(gr, nodCurent, nrSolutiiCautate, tip_euristica, solutions, startTime, nodeInfo):
    if nrSolutiiCautate <= 0:
        return nrSolutiiCautate

    if gr.isFinal(nodCurent):
        nrNodes, string = nodCurent.pathString()
        solution = "".join(["Solutie: \n", string, f"Lungimea drumului este: {str(nrNodes - 1)} \n",
                            f"Costul drumului este: {str(nodCurent.cost)}\n"])
        solution.join(f"Lungimea drumului este: {str(nrNodes)} \n")
        solution += "Numarul maxim de noduri in memorie: " + str(nodeInfo[0]) + "\n"
        solution += "Numarul total de noduri calculate: " + str(nodeInfo[1]) + "\n"
        solution += "Solutia a fost gasita in " + str(time.time() - startTime) + "\n"
        solutions.append(solution)
        nrSolutiiCautate -= 1
        if nrSolutiiCautate == 0:
            return nrSolutiiCautate
    lSuccesori = gr.genereazaSuccesori(nodCurent, tip_euristica)
    nodeInfo[1] += len(lSuccesori)
    nodeInfo[0] = max(nodeInfo[0], len(lSuccesori))
    for sc in lSuccesori:
        if nrSolutiiCautate != 0:
            nrSolutiiCautate = df(gr, sc, nrSolutiiCautate, tip_euristica, solutions, startTime, nodeInfo)

    return nrSolutiiCautate


@stopit.threading_timeoutable(default="Stopped because of timeout")
def dfi(gr, nodCurent, adancime, nrSolutiiCautate, tip_euristica, solutions, startTime, nodeInfo):
    if adancime == 1 and gr.isFinal(nodCurent):
        nrNodes, string = nodCurent.pathString()
        solution = "".join(["Solutie: \n", string, f"Lungimea drumului este: {str(nrNodes - 1)} \n",
                            f"Costul drumului este: {str(nodCurent.cost)}\n"])
        solution.join(f"Lungimea drumului este: {str(nrNodes)} \n")
        solution += "Numarul maxim de noduri in memorie: " + str(nodeInfo[0]) + "\n"
        solution += "Numarul total de noduri calculate: " + str(nodeInfo[1]) + "\n"
        solution += "Solutia a fost gasita in " + str(time.time() - startTime) + "\n"
        solutions.append(solution)
        nrSolutiiCautate -= 1
        if nrSolutiiCautate == 0:
            return nrSolutiiCautate
    if adancime > 1:
        lSuccesori = gr.genereazaSuccesori(nodCurent, tip_euristica)
        nodeInfo[1] += len(lSuccesori)
        nodeInfo[0] = max(nodeInfo[0], len(lSuccesori))

        for sc in lSuccesori:
            if nrSolutiiCautate != 0:
                nrSolutiiCautate = dfi(gr, sc, adancime - 1, nrSolutiiCautate, tip_euristica, solutions, startTime,
                                       nodeInfo)
    return nrSolutiiCautate


@stopit.threading_timeoutable(default="Stopped because of timeout")
def depth_first_iterativ(gr, nrSolutiiCautate, tip_euristica):
    startTime = time.time()
    solutions = []
    nodeInfo = [0, 0]  # maxNodesInMemory, totalNodes

    i = 0
    while True:
        if nrSolutiiCautate == 0:
            return solutions
        nrSolutiiCautate = dfi(gr,
                               Node(gr.startNode.info, None, 0, gr.calculeaza_h(gr.startNode.info), 0, 0, gr.startTime),
                               i, nrSolutiiCautate, tip_euristica,
                               solutions, startTime, nodeInfo)
        i += 1


@stopit.threading_timeoutable(default="Stopped because of timeout")
def a_star(gr, nrSolutiiCautate, tip_euristica):
    startTime = time.time()
    c = [Node(gr.startNode.info, None, 0, gr.calculeaza_h(gr.startNode.info), 0, 0, gr.startTime)]

    solutions = []
    maxNodesMemory = 0
    nodesCalculated = 0

    while len(c) > 0:
        nodCurent = c.pop(0)

        if gr.isFinal(nodCurent):
            nrNodes, string = nodCurent.pathString()
            solution = "".join(["Solutie: \n", string, f"Lungimea drumului este: {str(nrNodes - 1)} \n",
                                f"Costul drumului este: {str(nodCurent.cost)}\n"])
            solution.join(f"Lungimea drumului este: {str(nrNodes)} \n")
            solution += "Numarul maxim de noduri in memorie: " + str(maxNodesMemory) + "\n"
            solution += "Numarul total de noduri calculate: " + str(nodesCalculated) + "\n"
            solution += "Solutia a fost gasita in " + str(time.time() - startTime) + "\n"
            solutions.append(solution)
            nrSolutiiCautate -= 1
            if nrSolutiiCautate == 0:
                return solutions

        lSuccesori = gr.genereazaSuccesori(nodCurent, tip_euristica=tip_euristica)
        nodesCalculated += len(lSuccesori)

        for s in lSuccesori:
            i = 0
            gasit_loc = False
            for i in range(len(c)):
                if c[i].f >= s.f:
                    gasit_loc = True
                    break
            if gasit_loc:
                c.insert(i, s)
            else:
                c.append(s)
        maxNodesMemory = max(maxNodesMemory, len(c))
    return solutions  # didn't reach the nr of desired solutions


@stopit.threading_timeoutable(default="Stopped because of timeout")
def a_star_optimizat(gr, tip_euristica):
    startTime = time.time()
    l_open = [Node(gr.startNode.info, None, 0, gr.calculeaza_h(gr.startNode.info), 0, 0, gr.startTime)]

    solutions = []
    maxNodesMemory = 0
    nodesCalculated = 0

    l_closed = []
    while len(l_open) > 0:
        nodCurent = l_open.pop(0)

        l_closed.append(nodCurent)
        if gr.isFinal(nodCurent):
            nrNodes, string = nodCurent.pathString()
            solution = "".join(["Solutie: \n", string, f"Lungimea drumului este: {str(nrNodes - 1)} \n",
                                f"Costul drumului este: {str(nodCurent.cost)}\n"])
            solution.join(f"Lungimea drumului este: {str(nrNodes)} \n")
            solution += "Numarul maxim de noduri in memorie: " + str(maxNodesMemory) + "\n"
            solution += "Numarul total de noduri calculate: " + str(nodesCalculated) + "\n"
            solution += "Solutia a fost gasita in " + str(time.time() - startTime) + "\n"
            solutions.append(solution)
            return solutions

        lSuccesori = gr.genereazaSuccesori(nodCurent, tip_euristica=tip_euristica)

        nodesCalculated += len(lSuccesori)

        for s in lSuccesori:
            gasitC = False
            for nodC in l_open:
                if s.info == nodC.info:
                    gasitC = True
                    if s.f >= nodC.f:
                        lSuccesori.remove(s)
                    else:
                        l_open.remove(nodC)
                    break
            if not gasitC:
                for nodC in l_closed:
                    if s.info == nodC.info:
                        if s.f >= nodC.f:
                            lSuccesori.remove(s)
                        else:
                            l_closed.remove(nodC)
                        break
        for s in lSuccesori:
            i = 0
            gasit_loc = False
            for i in range(len(l_open)):
                if l_open[i].f > s.f or (l_open[i].f == s.f and l_open[i].cost <= s.cost):
                    gasit_loc = True
                    break
            if gasit_loc:
                l_open.insert(i, s)
            else:
                l_open.append(s)

        maxNodesMemory = max(maxNodesMemory, len(l_open) + len(l_closed))
    return solutions


@stopit.threading_timeoutable(default="Stopped because of timeout")
def ida_star(gr, nrSolutiiCautate, tip_euristica):
    startTime = time.time()
    solutions = []
    nodeInfo = [0, 0]

    nodStart = Node(gr.startNode.info, None, 0, gr.calculeaza_h(gr.startNode.info, tip_euristica), 0, 0, gr.startTime)
    limita = nodStart.f
    while True:
        nrSolutiiCautate, rez = construieste_drum(gr, nodStart, limita, nrSolutiiCautate, tip_euristica, solutions,
                                                  startTime, nodeInfo)
        if rez == "gata":
            break
        if rez == float('inf'):
            break
        limita = rez
    return solutions


def construieste_drum(gr, nodCurent, limita, nrSolutiiCautate, tip_euristica, solutions, startTime, nodeInfo):
    if nodCurent.f > limita:
        return nrSolutiiCautate, nodCurent.f
    if gr.isFinal(nodCurent):
        nrNodes, string = nodCurent.pathString()
        solution = "".join(["Solutie: \n", string, f"Lungimea drumului este: {str(nrNodes - 1)} \n",
                            f"Costul drumului este: {str(nodCurent.cost)}\n"])
        solution.join(f"Lungimea drumului este: {str(nrNodes)} \n")
        solution += "Numarul maxim de noduri in memorie: " + str(nodeInfo[0]) + "\n"
        solution += "Numarul total de noduri calculate: " + str(nodeInfo[1]) + "\n"
        solution += "Solutia a fost gasita in " + str(time.time() - startTime) + "\n"
        solutions.append(solution)
        nrSolutiiCautate -= 1
        if nrSolutiiCautate == 0:
            return 0, "gata"
    lSuccesori = gr.genereazaSuccesori(nodCurent, tip_euristica)
    nodeInfo[1] += len(lSuccesori)
    nodeInfo[0] = max(nodeInfo[0], len(lSuccesori))
    minim = float('inf')
    for s in lSuccesori:
        nrSolutiiCautate, rez = construieste_drum(gr, s, limita, nrSolutiiCautate, tip_euristica, solutions, startTime,
                                                  nodeInfo)
        if rez == "gata":
            return 0, "gata"
        if rez < minim:
            minim = rez
    return nrSolutiiCautate, minim


def transformInput(file):
    try:
        f = open(file, "r")
        line = f.readline()
        startTime = line.split()[0]
        endTime = line.split()[1]
        busSchemas = []
        persons = []
        line = f.readline()
        while line.find("oameni") == -1:
            aux = line.strip().split("lei")[0]
            busNr = aux.split(" ")[0]
            ticketPrice = float(aux.split(" ")[1])
            aux = line.strip().split("lei")[1]
            tplec = float(aux.split("min")[0])
            travelTime = float(aux.split("min")[1])
            aux = aux.split("min")[2][1:].split(",")
            busSchemas.append(BusSchema(busNr, ticketPrice, tplec, travelTime, aux))
            line = f.readline()
        nrPeople = int(line.split(" oameni")[0])
        while nrPeople > 0:
            line = f.readline()
            aux = line.strip().split("lei")[0]
            name = aux.split(" ")[0]
            budget = float(aux.split(" ")[1])
            aux = line.strip().split("lei ")[1].split(",")
            persons.append(Person(name, budget, aux))
            nrPeople -= 1
        nodInfo = Information(busSchemas, persons, [], 0)
        if not nodInfo.checkIfPossible():
            return "Doua persoane in aceeasi statie"
        nodStart = Node(nodInfo, None, 0, 0, 0, 0, startTime)
        if nodStart.isFinal():
            return "Stare intiala este si finala."
        minMoney = min([person.budget for person in persons])
        if minMoney < nodInfo.minimumTicketPrice:
            return "Nu exista solutie."
        graf = Graph(startTime, endTime, nodStart)
        if nodInfo.minimumTravelTime > graf.duration:
            return "Nu exista solutie"
        return graf
    except:
        print("Not valid input")
        return "Not valid input"


def initialize():
    if len(sys.argv) != 5:
        print("Invalid number of arguments given. ")
        sys.exit(1)
    else:
        try:
            inputDirectory = sys.argv[1]
            outputDirectory = sys.argv[2]
            nsol = int(sys.argv[3])
            timeout = int(sys.argv[4])
        except:
            print("Something went wrong.")
            sys.exit(1)
    return inputDirectory, outputDirectory, nsol, timeout


def solve():
    inputDirectory, outputDirectory, nsol, timeout = initialize()
    try:
        inputList = os.listdir(inputDirectory)
    except:
        print("Invalid input path")
        sys.exit(1)
    functionList = [breadth_first, depth_first, depth_first_iterativ, a_star, a_star_optimizat, ida_star]
    heuristicList = ["euristica banala", "euristica admisibila 1", "euristica admisibila 2", "euristica admisibila 3", \
                     "euristica neadmisibila"]
    if not os.path.exists(outputDirectory):
        os.mkdir(outputDirectory)
    for inputName in inputList:
        maybeGraph = transformInput(f"{inputDirectory}/{inputName}")
        if maybeGraph.__class__.__name__ == "str":
            f = open(f"{outputDirectory}/{inputName}_output", "w")
            f.write(maybeGraph)
            f.close()
            continue
        f = open(f"{outputDirectory}/{inputName}_output", "w")
        for function in functionList:
            f.write('=\n'.rjust(50, '='))
            f.write(f"Solutii pentru agloritmul {function.__name__}")
            f.write('\n')
            f.write('=\n'.rjust(50, '='))
            for heuristic in heuristicList:
                f.write(f"\n\nEuristica folosita: {heuristic}\n")
                f.write('_\n'.rjust(50, '_'))
                if function.__name__ == "a_star_optimizat":
                    if timeout != 0:
                        solutions = function(maybeGraph, heuristic, timeout=timeout)
                    else:
                        solutions = function(maybeGraph, heuristic)
                else:
                    if timeout != 0:
                        solutions = function(maybeGraph, nsol, heuristic, timeout=timeout)
                    else:
                        solutions = function(maybeGraph, nsol, heuristic)
                if solutions == "Stopped because of timeout":
                    f.write(solutions)
                    f.write('\n')
                else:
                    for solution in solutions:
                        f.write(solution)
                        if solution != solutions[-1]:
                            f.write('-\n'.rjust(50, '-'))
        f.close()


if __name__ == "__main__":
    cProfile.run("solve()")
