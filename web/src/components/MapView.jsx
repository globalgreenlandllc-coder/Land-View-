import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

const ESRI_TILES = "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";

function esriStyle() {
  return {
    version: 8,
    sources: {
      esri: { type: "raster", tiles: [ESRI_TILES], tileSize: 256,
        attribution: "Imagery © Esri" },
    },
    layers: [{ id: "esri", type: "raster", source: "esri" }],
  };
}

// Haversine distance (metres) between [lng,lat] points.
function distM(a, b) {
  const R = 6371000, toR = Math.PI / 180;
  const dLat = (b[1] - a[1]) * toR, dLng = (b[0] - a[0]) * toR;
  const la1 = a[1] * toR, la2 = b[1] * toR;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(la1) * Math.cos(la2) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}
// Planar shoelace area (m²) for [lng,lat] ring, projected near its centroid.
function areaM2(pts) {
  if (pts.length < 3) return 0;
  const lat0 = pts.reduce((s, p) => s + p[1], 0) / pts.length;
  const mLat = 111320, mLng = 111320 * Math.cos(lat0 * Math.PI / 180);
  const xy = pts.map(([lng, lat]) => [lng * mLng, lat * mLat]);
  let a = 0;
  for (let i = 0; i < xy.length; i++) {
    const [x1, y1] = xy[i], [x2, y2] = xy[(i + 1) % xy.length];
    a += x1 * y2 - x2 * y1;
  }
  return Math.abs(a) / 2;
}
const M2_TO_SQFT = 10.7639, M_TO_FT = 3.28084;

export default function MapView({ parcel, mapConfig }) {
  const ref = useRef(null);
  const mapRef = useRef(null);
  const [measure, setMeasure] = useState(false);
  const [pts, setPts] = useState([]);
  const measureRef = useRef(false);
  useEffect(() => { measureRef.current = measure; }, [measure]);

  // Build the map once.
  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    let style = esriStyle();
    let transformRequest;
    if (mapConfig?.provider === "mapbox" && mapConfig.token) {
      style = mapConfig.style || "mapbox://styles/mapbox/satellite-streets-v12";
      transformRequest = (url) => {
        if (url.startsWith("mapbox://")) {
          url = url.replace("mapbox://styles/", "https://api.mapbox.com/styles/v1/")
            + (url.includes("?") ? "&" : "?") + "access_token=" + mapConfig.token;
        }
        return { url };
      };
    }
    const map = new maplibregl.Map({
      container: ref.current, style, center: [parcel.lng, parcel.lat], zoom: 17,
      transformRequest, attributionControl: true,
    });
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.on("load", () => drawParcel(map));
    map.on("click", (e) => {
      if (!measureRef.current) return;
      setPts((p) => [...p, [e.lngLat.lng, e.lngLat.lat]]);
    });
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
  }, []); // eslint-disable-line

  // Redraw the parcel when it changes.
  useEffect(() => {
    const map = mapRef.current;
    if (map && map.isStyleLoaded()) drawParcel(map);
  }, [parcel]);

  function drawParcel(map) {
    const ring = parcel.boundary || [];
    const data = {
      type: "Feature",
      geometry: { type: "Polygon", coordinates: [ring] },
      properties: {},
    };
    if (map.getSource("parcel")) {
      map.getSource("parcel").setData(data);
    } else {
      map.addSource("parcel", { type: "geojson", data });
      map.addLayer({ id: "parcel-fill", type: "fill", source: "parcel",
        paint: { "fill-color": "#22c55e", "fill-opacity": 0.18 } });
      map.addLayer({ id: "parcel-line", type: "line", source: "parcel",
        paint: { "line-color": "#16a34a", "line-width": 3 } });
    }
    if (ring.length) {
      const b = ring.reduce((bb, c) => bb.extend(c),
        new maplibregl.LngLatBounds(ring[0], ring[0]));
      map.fitBounds(b, { padding: 60, duration: 600, maxZoom: 19 });
    }
  }

  // Sync the measurement overlay.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const line = { type: "Feature", geometry: { type: "LineString", coordinates: pts } };
    const verts = { type: "FeatureCollection", features: pts.map((p) => ({
      type: "Feature", geometry: { type: "Point", coordinates: p } })) };
    if (map.getSource("measure-line")) {
      map.getSource("measure-line").setData(line);
      map.getSource("measure-pts").setData(verts);
    } else {
      map.addSource("measure-line", { type: "geojson", data: line });
      map.addSource("measure-pts", { type: "geojson", data: verts });
      map.addLayer({ id: "measure-line", type: "line", source: "measure-line",
        paint: { "line-color": "#f59e0b", "line-width": 2.5, "line-dasharray": [2, 1] } });
      map.addLayer({ id: "measure-pts", type: "circle", source: "measure-pts",
        paint: { "circle-radius": 4, "circle-color": "#f59e0b",
          "circle-stroke-color": "#fff", "circle-stroke-width": 1.5 } });
    }
  }, [pts]);

  let totalM = 0;
  for (let i = 1; i < pts.length; i++) totalM += distM(pts[i - 1], pts[i]);
  const ft = totalM * M_TO_FT;
  const sqft = pts.length >= 3 ? areaM2(pts) * M2_TO_SQFT : 0;

  return (
    <div className="mapwrap">
      <div ref={ref} className="map" />
      <div className="map-tools">
        <button type="button" className={measure ? "on" : ""}
          onClick={() => { setMeasure((m) => !m); if (measure) setPts([]); }}>
          📏 {measure ? "Measuring… (click map)" : "Measure"}
        </button>
        {measure && pts.length > 0 && (
          <>
            <span className="measure-readout">
              {ft >= 0 && <b>{ft.toFixed(0)} ft</b>}
              {sqft > 0 && <> · <b>{sqft.toLocaleString(undefined, { maximumFractionDigits: 0 })} sq ft</b></>}
            </span>
            <button type="button" onClick={() => setPts([])}>Clear</button>
          </>
        )}
      </div>
    </div>
  );
}
