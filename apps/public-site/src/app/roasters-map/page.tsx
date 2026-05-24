"use client";

import { useState, useEffect, useRef } from "react";

// Declare google namespace for TypeScript
declare global {
  namespace google {
    namespace maps {
      export interface LatLngLiteral {
        lat: number;
        lng: number;
      }
      export interface MapsEventListener {
        remove(): void;
      }
      export class Map {
        constructor(element: HTMLElement, options?: any);
        setCenter(latlng: LatLngLiteral | LatLng): void;
        setZoom(zoom: number): void;
      }
      export class Marker {
        constructor(options?: any);
        setMap(map: Map | null): void;
        setTitle(title: string): void;
        getPosition(): LatLngLiteral | null;
        addListener(event: string, handler: (...args: any[]) => void): MapsEventListener;
      }
      export class InfoWindow {
        constructor(options?: any);
        open(options?: any): void;
        close(): void;
        setContent(content: string | Node): void;
      }
      export class LatLng {
        constructor(lat: number, lng: number);
      }
    }
  }
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const GOOGLE_MAPS_API_KEY = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || "";

interface Roaster {
  id: string;
  name: string;
  domain: string;
  homepage_url: string;
  uk_region: string | null;
  listing_count: number;
}

// Map UK regions to approximate coordinates (lat, lng)
const REGION_COORDINATES: Record<string, [number, number]> = {
  "London": [51.5074, -0.1278],
  "South West": [50.9097, -3.5244],
  "Yorkshire": [53.9582, -1.1581],
  "Midlands": [52.5090, -1.8768],
  "Scotland": [55.9533, -3.1883],
  "Wales": [52.1307, -3.7837],
  "East of England": [52.5870, 0.2418],
  "North West": [53.4808, -2.2426],
  "South East": [51.2538, 0.4747],
  "Northern Ireland": [54.6072, -6.2263],
};

interface MarkerData {
  roaster: Roaster;
  position: { lat: number; lng: number };
}

export default function RoastersMapPage() {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<google.maps.Map | null>(null);
  const markersRef = useRef<google.maps.Marker[]>([]);
  const infoWindowRef = useRef<google.maps.InfoWindow | null>(null);
  const [roasters, setRoasters] = useState<Roaster[]>([]);
  const [loading, setLoading] = useState(true);
  const [mapsLoaded, setMapsLoaded] = useState(false);

  // Load Google Maps API
  useEffect(() => {
    if (!GOOGLE_MAPS_API_KEY) {
      console.warn("Google Maps API key not configured");
      setLoading(false);
      return;
    }

    // Check if Google Maps is already loaded
    if (typeof window !== "undefined" && window.google?.maps) {
      setMapsLoaded(true);
      return;
    }

    const script = document.createElement("script");
    script.src = `https://maps.googleapis.com/maps/api/js?key=${GOOGLE_MAPS_API_KEY}`;
    script.async = true;
    script.defer = true;
    script.onload = () => setMapsLoaded(true);
    script.onerror = () => {
      console.error("Failed to load Google Maps API");
      setLoading(false);
    };
    document.head.appendChild(script);
  }, []);

  // Fetch roasters data
  useEffect(() => {
    fetch(`${API_BASE}/api/v1/roasters?page_size=200`)
      .then(r => r.json())
      .then(d => {
        const roastersWithRegion = (d.data ?? []).filter((r: Roaster) => r.uk_region);
        setRoasters(roastersWithRegion);
      })
      .catch(err => {
        console.error("Failed to fetch roasters:", err);
      })
      .finally(() => setLoading(false));
  }, []);

  // Initialize map and add markers
  useEffect(() => {
    if (!mapsLoaded || !mapRef.current || roasters.length === 0) return;

    // Initialize map centered on UK
    const map = new window.google.maps.Map(mapRef.current, {
      zoom: 6,
      center: { lat: 54.5260, lng: -3.4360 }, // Center of UK
      styles: [
        {
          elementType: "geometry",
          stylers: [{ color: "#f5f5f5" }],
        },
        {
          elementType: "labels.text.stroke",
          stylers: [{ color: "#ffffff" }],
        },
        {
          elementType: "labels.text.fill",
          stylers: [{ color: "#616161" }],
        },
      ],
    });

    mapInstanceRef.current = map;
    infoWindowRef.current = new window.google.maps.InfoWindow();

    // Clear existing markers
    markersRef.current.forEach(marker => marker.setMap(null));
    markersRef.current = [];

    // Add markers for each roaster
    roasters.forEach(roaster => {
      if (!roaster.uk_region) return;

      const coords = REGION_COORDINATES[roaster.uk_region];
      if (!coords) return;

      const marker = new window.google.maps.Marker({
        position: { lat: coords[0], lng: coords[1] },
        map: map,
        title: roaster.name,
        icon: {
          path: "M0,-28a14,14 0 1,1 28,0a14,14 0 1,1 -28,0",
          fillColor: "#d4a574",
          fillOpacity: 0.8,
          strokeColor: "#ffffff",
          strokeWeight: 2,
          scale: 1,
        },
      });

      marker.addListener("click", () => {
        const content = `
          <div style="font-family: var(--font-body); font-size: 14px;">
            <h3 style="margin: 0 0 8px 0; font-weight: 600; font-size: 16px;">${roaster.name}</h3>
            <p style="margin: 0 0 4px 0; color: #666; font-size: 12px;">${roaster.uk_region}</p>
            <p style="margin: 0 0 8px 0; color: #666; font-size: 12px;">${roaster.domain}</p>
            <p style="margin: 0; color: #999; font-size: 11px;">${roaster.listing_count} coffees indexed</p>
            <a href="/roasters/${roaster.id}" style="display: inline-block; margin-top: 8px; color: #d4a574; text-decoration: none; font-size: 12px; font-weight: 500;">View profile →</a>
          </div>
        `;
        infoWindowRef.current?.setContent(content);
        infoWindowRef.current?.open(map, marker);
      });

      markersRef.current.push(marker);
    });
  }, [mapsLoaded, roasters]);

  if (!GOOGLE_MAPS_API_KEY) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: "var(--bg)" }}>
        <div className="text-center" style={{ color: "var(--text-muted)" }}>
          <p className="text-lg mb-2">Map configuration required</p>
          <p className="text-sm">Please configure NEXT_PUBLIC_GOOGLE_MAPS_API_KEY environment variable</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: "var(--bg)" }}>
      {/* Header */}
      <div className="px-6 pt-8 pb-6 max-w-7xl mx-auto">
        <h1 className="text-4xl font-light mb-2" style={{ fontFamily: "var(--font-display)", color: "var(--text)" }}>
          Roaster Map
        </h1>
        <p style={{ color: "var(--text-muted)", fontSize: "16px" }}>
          Discover specialty coffee roasters across the UK. Click on any pin to learn more.
        </p>
      </div>

      {/* Map Container */}
      <div className="px-6 pb-12 max-w-7xl mx-auto">
        <div
          ref={mapRef}
          style={{
            width: "100%",
            height: "600px",
            borderRadius: "12px",
            border: "1px solid var(--border-light)",
            boxShadow: "0 4px 12px rgba(0, 0, 0, 0.1)",
          }}
        >
          {loading && (
            <div className="flex items-center justify-center h-full" style={{ color: "var(--text-muted)" }}>
              <div className="text-center">
                <div className="inline-block w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full animate-spin mb-4"></div>
                <p>Loading roasters map...</p>
              </div>
            </div>
          )}
        </div>

        {/* Roaster Count */}
        {!loading && (
          <div className="mt-6 text-center" style={{ color: "var(--text-faint)", fontSize: "14px" }}>
            {roasters.length === 0 ? (
              <p>No roasters with region data available</p>
            ) : (
              <p>{roasters.length} roasters pinned on the map</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
