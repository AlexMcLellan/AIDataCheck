import requests
import xml.etree.ElementTree as ET

url = "https://map.bgs.ac.uk/arcgis/services/UKSO/UKSO_BGS/MapServer/WMSServer?request=GetCapabilities&service=WMS"
print("Fetching Capabilities...")
res = requests.get(url)

root = ET.fromstring(res.content)

# The WMS namespace is usually something like {http://www.opengis.net/wms}
ns = {'wms': 'http://www.opengis.net/wms'}

layers = root.findall('.//wms:Layer', ns)
for layer in layers:
    name = layer.find('wms:Name', ns)
    title = layer.find('wms:Title', ns)
    if name is not None and title is not None:
        title_text = title.text.lower()
        if 'sand' in title_text or 'bulk density' in title_text or 'clay' in title_text or 'silt' in title_text:
            print(f"Name: {name.text} | Title: {title.text}")
