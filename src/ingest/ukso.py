import pandas as pd
try:
    from owslib.wms import WebMapService
except ImportError:
    WebMapService = None
    print("Warning: OWSLib not installed. Please `pip install OWSLib` to query UKSO.")

def fetch_bgs_soil_properties(latitude, longitude):
    """
    Queries the UK Soil Observatory (UKSO/BGS) WMS service to extract
    soil properties (texture, bulk density) for a specific coordinate.
    """
    if WebMapService is None:
        raise ImportError("OWSLib is required to query UKSO.")
        
    # Example endpoint for UKSO soil properties (this is a placeholder URL,
    # the exact BGS WMS URL and layer names need to be verified on the UKSO portal)
    wms_url = "https://map.bgs.ac.uk/arcgis/services/UKSO/UKSO_BGS/MapServer/WMSServer"
    
    try:
        wms = WebMapService(wms_url, version='1.3.0')
        
        # Bounding box trick: create a tiny bbox around the point to use GetFeatureInfo
        delta = 0.0001
        bbox = (longitude - delta, latitude - delta, longitude + delta, latitude + delta)
        
        print("Available UKSO Layers:")
        for layer_id in list(wms.contents.keys())[:20]:
            print(f" - {layer_id}: {wms[layer_id].title}")
        print("...")
        
        # Target layers
        target_layers = ['Parent.Material.Soil.texture', 'Parent.Material.Grain.size', 'Parent.Material.Soil.texture.simple'] 
        
        results = {}
        for layer in target_layers:
            if layer in wms.contents and wms[layer].queryable:
                response = wms.getfeatureinfo(
                    layers=[layer],
                    srs='EPSG:4326',
                    bbox=bbox,
                    size=(10, 10),
                    format='image/png',
                    query_layers=[layer],
                    info_format='text/plain',
                    xy=(5, 5)
                )
                # Parse the plain text response for the value
                results[layer] = response.read().decode('utf-8')
            else:
                print(f"Layer {layer} not found or not queryable.")
                
        return results
        
    except Exception as e:
        print(f"Error querying UKSO WMS: {e}")
        return {}
