"""
This module holds the location class, which is used to provide several information about the intersection's environment.
It also can be used to download and convert a location to lanelets.
"""


class Location:
    """
    Location class which holds information about a selected region and
    provides methods to download and convert a location to lanelets
    """

    # general information
    name: str
    city_name: str
    contintent_code: str
    country_name: str
    country_code: str
    population: int

    # administrative codes
    adminCode1: str
    adminCode2: str = ""

    # coordinates
    lat: float
    lng: float
    bbox: dict

    # geonames
    geoNameID: int
    geoNameData: str

    def __init__(self, d: dict):
        self.city_name = d["asciiName"]
        self.contintent_code = d["continentCode"]
        self.country_name = d["countryName"]
        self.country_code = d["countryCode"]
        self.name = self.create_name()

        if d["population"]:
            self.population = int(d["population"])
        else:
            self.population = 0

        try:
            self.adminCode1 = d["adminCode1"]["@ISO3166-2"]
            if d["adminCode2"] is not None and "@ISO3166-2" in d["adminCode2"]:
                self.adminCode2 = str(d["adminCode2"]["@ISO3166-2"])
        except:
            print("error parsing adminCode")

        self.lat = float(d["lat"])
        self.lng = float(d["lng"])
        self.bbox = {}
        for key in d["bbox"]:
            self.bbox[key] = float(d["bbox"][key])

        self.geoNameID = d["geonameId"]
        self.geoNameData = d

    def create_name(self):
        """
        Removes whitespaces for and creates CommonRoad conform name for location

        :return: Name of location
        """

        name = self.country_code + "_" + self.city_name
        return name.replace(" ", "")
