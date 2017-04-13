from .device_description_settings import \
    DeviceDescriptionSettingsWidget

class SystemBusDeviceDescriptionSettingsWidget(DeviceDescriptionSettingsWidget):
    def __init__(self, *args, **kw):
        DeviceDescriptionSettingsWidget.__init__(self, [], *args, **kw)
