import socket
import requests
import json
import xml.etree.ElementTree as ET


class Camera(object):
    def __init__(self, network_interface=None):
        """
        create camera object
        """
        self._network_interface = network_interface
        self.xml_url = self.discover()
        self.name, self.api_version, self.services = self.connect(self.xml_url)
        self.camera_endpoint_url = self.services["camera"] + "/camera"
        self.available_apis = self.do("getAvailableApiList")

        # prepare camera for rec mode
        if "startRecMode" in self.available_apis:
            self.do("startRecMode")

    def discover(self):
        """ Discover camera.

        Raises:
            ConnectionError: If the camera cannot be discovered, usually
                because you are not connected to the camera's wifi.

        Returns:
            str: The XML URL of the camera.
        """
        msg = (
            "M-SEARCH * HTTP/1.1\r\n"
            "HOST: 239.255.255.250:1900\r\n"
            'MAN: "ssdp:discover" \r\n'
            "MX: 2\r\n"
            "ST: urn:schemas-sony-com:service:ScalarWebAPI:1\r\n"
            "\r\n"
        ).encode()

        # Set up UDP socket
        if not hasattr(socket, 'SO_BINDTODEVICE'):
            socket.SO_BINDTODEVICE = 25

        socket_ = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        if self._network_interface is not None:
            socket_.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_BINDTODEVICE,
                self._network_interface.encode(),
            )
        socket_.settimeout(2)
        socket_.sendto(msg, ("239.255.255.250", 1900))

        try:
            while True:
                data, addr = socket_.recvfrom(65507)
                decoded_data = data.decode()
                # get xml url from ssdp response
                for item in decoded_data.split("\n"):
                    if "LOCATION" in item:
                        return item.strip().split(" ")[1]

        except socket.timeout:
            raise ConnectionError("You are not connected to the camera's wifi.")

    def connect(self, xml_url):
        """
        returns name, api_version, api_service_urls on success
        """
        device_xml_request = requests.get(xml_url)
        xml_file = str(device_xml_request.content.decode())
        xml = ET.fromstring(xml_file)
        name = xml.find(
            "{urn:schemas-upnp-org:device-1-0}device/{urn:schemas-upnp-org:device-1-0}friendlyName"
        ).text
        api_version = xml.find(
            "{urn:schemas-upnp-org:device-1-0}device/{urn:schemas-sony-com:av}X_ScalarWebAPI_DeviceInfo/{urn:schemas-sony-com:av}X_ScalarWebAPI_Version"
        ).text
        service_list = xml.find(
            "{urn:schemas-upnp-org:device-1-0}device/{urn:schemas-sony-com:av}X_ScalarWebAPI_DeviceInfo/{urn:schemas-sony-com:av}X_ScalarWebAPI_ServiceList"
        )
        api_service_urls = {}
        for service in service_list:
            service_type = service.find(
                "{urn:schemas-sony-com:av}X_ScalarWebAPI_ServiceType"
            ).text
            action_url = service.find(
                "{urn:schemas-sony-com:av}X_ScalarWebAPI_ActionList_URL"
            ).text
            api_service_urls[service_type] = action_url

        return name, api_version, api_service_urls

    @property
    def connected(self):
        """bool: True if the camera is connected"""
        try:
            requests.get(self.camera_endpoint_url, timeout=0.2)
            return True
        except requests.exceptions.ConnectionError:
            return False

    @property
    def info(self):
        """
        returns camera info(name, api version, supported services, available apis) in a dictionary
        """
        return {
            "name": self.name,
            "api version": self.api_version,
            "supported services": list(self.services.keys()),
            "available apis": self.available_apis,
        }

    def _post_request(self, method, param=[]):
        """
        """
        if type(param) is not list:
            param = [param]
        json_request = {"method": method, "params": param, "id": 1, "version": "1.0"}
        request = requests.post(self.camera_endpoint_url, json.dumps(json_request))
        response = json.loads(request.content)

        return response

    def do(self, method, param=[]):
        """"""
        response = self._post_request(method, param=param)

        if "error" in response:
            error = response["error"]
            error_code = error[0]
            error_message = error[-1]

            if error_code == 1:
                raise NotAvailableError(error_message)

            elif error_code == 3:
                raise IllegalArgumentError(error_message + ": {}".format(param))

            elif error_code == 12:
                raise InvalidActionError("Invalid action: " + error_message)

            elif error_code == 403:
                raise ForbiddenError(error_message)

            elif error_code == 500:
                raise OperationFailedError(error_message)

            elif error_code == 40403:
                raise LongShootingError(error_message)

            else:
                raise ValueError(f"Error {error_code}: {error_message}")

        else:
            result = response.get("result", [])
            if len(result) == 0:
                return True

            elif len(result) == 1:
                return result[0]

            else:
                return result


class NotAvailableError(Exception):
    pass


class IllegalArgumentError(Exception):
    pass


class InvalidActionError(Exception):
    pass


class ForbiddenError(Exception):
    pass


class OperationFailedError(Exception):
    pass

class LongShootingError(Exception):
    pass
